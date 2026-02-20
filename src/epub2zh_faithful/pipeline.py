from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import AppConfig, load_config
from .epub_parser import cleanup_workspace, unpack_epub
from .epub_writer import repack_epub
from .llm_client import LLMClientFactory, ProviderError, ProviderSettings
from .models import NodeTask, RunStats, Segment
from .post_editor import post_edit
from .qa_checker import capture_integrity_snapshot, qa_passes_gate, run_qa, write_qa_reports
from .segmenter import build_segments, group_segments_for_batches, merge_segment_translations
from .terminology import Termbase
from .tm_store import TMStore
from .toc_handler import (
    apply_toc_translations,
    extract_toc_items,
    snapshot_toc_hrefs,
    toc_items_to_node_tasks,
)
from .utils import ensure_dir, sha256_text
from .xhtml_extractor import extract_node_tasks
from .xhtml_rewriter import apply_node_translations


class PipelineError(RuntimeError):
    pass


ProgressCallback = Callable[[str], None]


def run_translation(args: object, progress_cb: ProgressCallback | None = None) -> int:
    _emit(progress_cb, "Loading config and termbase...")
    config = load_config(getattr(args, "config", None))
    termbase = Termbase.load(getattr(args, "termbase", None))
    cache_path = getattr(args, "cache", None) or "cache.sqlite"
    provider_name = getattr(args, "provider")
    if provider_name == "mixed":
        draft_provider = getattr(args, "draft_provider", None) or "openai"
        revise_provider = getattr(args, "revise_provider", None) or "deepseek"
    else:
        draft_provider = getattr(args, "draft_provider", None) or provider_name
        revise_provider = getattr(args, "revise_provider", None) or provider_name

    provider_settings = ProviderSettings(
        provider=provider_name,
        draft_provider=draft_provider,
        revise_provider=revise_provider,
        model=getattr(args, "model", "gpt-5-mini"),
        draft_model=getattr(args, "draft_model", None),
        revise_model=getattr(args, "revise_model", None),
    )

    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    output_path = Path(getattr(args, "output"))
    artifacts_dir = ensure_dir(output_path.parent / f"{output_path.stem}_artifacts")
    qa_report_path = artifacts_dir / "qa_report.json"
    qa_summary_path = artifacts_dir / "qa_summary.md"

    store = TMStore(cache_path)
    stats = RunStats()

    book = None
    workdir_keep = bool(getattr(args, "keep_workdir", False))
    try:
        _emit(progress_cb, "Initializing provider...")
        provider = LLMClientFactory.build(provider_settings, config)
        _emit(progress_cb, "Unpacking EPUB...")
        book = unpack_epub(getattr(args, "input"), keep_workdir=workdir_keep)
        _emit(progress_cb, f"Workspace: {book.workspace_dir}")

        watched_files = list(book.xhtml_files)
        if book.toc_nav_path:
            watched_files.append(book.toc_nav_path)
        if book.toc_ncx_path:
            watched_files.append(book.toc_ncx_path)

        integrity_before = capture_integrity_snapshot(book.workspace_dir, watched_files)
        toc_before = snapshot_toc_hrefs(book.workspace_dir, book.toc_nav_path, book.toc_ncx_path)

        xhtml_tasks = extract_node_tasks(book, config, start_order=1)
        _emit(progress_cb, f"Extracted XHTML tasks: {len(xhtml_tasks)}")
        toc_tasks: list[NodeTask] = []
        if config.translate_toc:
            toc_items = extract_toc_items(book.workspace_dir, book.toc_nav_path, book.toc_ncx_path)
            toc_tasks = toc_items_to_node_tasks(toc_items, start_order=len(xhtml_tasks) + 1)
            _emit(progress_cb, f"Extracted TOC tasks: {len(toc_tasks)}")

        all_tasks = sorted(xhtml_tasks + toc_tasks, key=lambda x: x.order_index)
        segments = build_segments(all_tasks, config)
        stats.total_segments = len(segments)
        _emit(progress_cb, f"Built segments: {len(segments)}")

        config_hash = _build_config_hash(config, termbase.version_id, provider_settings)
        store.create_run(run_id, getattr(args, "input"), getattr(args, "output"), provider_settings.provider, config_hash)

        prefer_revise = provider_settings.revise_provider != "none"
        segment_translations = _translate_with_cache(
            segments=segments,
            provider=provider,
            store=store,
            termbase=termbase,
            config_hash=config_hash,
            prefer_revise=prefer_revise,
            resume=bool(getattr(args, "resume", False)),
            max_concurrency=max(1, int(getattr(args, "max_concurrency", 4))),
            stats=stats,
            config=config,
            progress_cb=progress_cb,
        )
        _emit(
            progress_cb,
            f"Translation complete: translated={stats.translated_segments}, cached={stats.cached_segments}, llm_calls={stats.llm_calls}",
        )

        node_translations = merge_segment_translations(segments, segment_translations)

        _emit(progress_cb, "Writing translations back to XHTML/TOC...")
        apply_node_translations(
            workdir=book.workspace_dir,
            node_tasks=xhtml_tasks,
            node_translations=node_translations,
            quote_class=config.quote_mode.translation_node_class,
        )

        toc_translation_map = {task.id: node_translations.get(task.id, "") for task in toc_tasks}
        apply_toc_translations(book.workspace_dir, toc_translation_map, toc_tasks)

        issues = run_qa(
            workdir=book.workspace_dir,
            config=config,
            book=book,
            segments=segments,
            segment_translations=segment_translations,
            node_tasks=all_tasks,
            node_translations=node_translations,
            toc_before=toc_before,
            termbase=termbase,
            integrity_before=integrity_before,
        )
        error_count = sum(1 for i in issues if i.severity == "error")
        warn_count = sum(1 for i in issues if i.severity == "warn")
        _emit(progress_cb, f"QA complete: errors={error_count}, warns={warn_count}")
        write_qa_reports(
            output_dir=str(artifacts_dir),
            segments=segments,
            issues=issues,
            report_path=str(qa_report_path),
            summary_path=str(qa_summary_path),
        )

        _emit(progress_cb, "Repacking EPUB...")
        repack_epub(book.workspace_dir, getattr(args, "output"))
        store.commit()

        if qa_passes_gate(config, len(segments), issues):
            _emit(progress_cb, "Finished with exit code 0")
            return 0
        _emit(progress_cb, "Finished with exit code 2 (QA errors present)")
        return 2

    except ProviderError as exc:
        store.record_error(run_id, "provider", str(exc))
        store.commit()
        _write_failure_artifacts(
            qa_report_path=qa_report_path,
            qa_summary_path=qa_summary_path,
            message=str(exc),
            stage="provider",
        )
        _emit(progress_cb, f"Provider error: {exc}")
        print(f"Provider error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        store.record_error(run_id, "runtime", str(exc))
        store.commit()
        _write_failure_artifacts(
            qa_report_path=qa_report_path,
            qa_summary_path=qa_summary_path,
            message=str(exc),
            stage="runtime",
        )
        _emit(progress_cb, f"Fatal error: {exc}")
        print(f"Fatal error: {exc}")
        print(traceback.format_exc())
        return 1
    finally:
        store.close()
        if book is not None:
            cleanup_workspace(book.workspace_dir, workdir_keep)


def _build_config_hash(config: AppConfig, termbase_version: str, provider_settings: ProviderSettings) -> str:
    payload = {
        "config": config.to_normalized_json(),
        "termbase_version": termbase_version,
        "provider": asdict(provider_settings),
    }
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _translate_with_cache(
    segments: list[Segment],
    provider: object,
    store: TMStore,
    termbase: Termbase,
    config_hash: str,
    prefer_revise: bool,
    resume: bool,
    max_concurrency: int,
    stats: RunStats,
    config: AppConfig,
    progress_cb: ProgressCallback | None = None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    pending: list[Segment] = []

    for seg in segments:
        source_hash = sha256_text(seg.source_text)
        store.record_segment(seg.id, seg.file_path, seg.node_selector, seg.order_index, source_hash)
        cached = store.get_cached(seg.id, source_hash, config_hash, prefer_revise=prefer_revise) if resume else None
        if resume and cached is not None:
            out[seg.id] = cached
            stats.cached_segments += 1
        else:
            pending.append(seg)
    _emit(progress_cb, f"Cache scan done: hit={stats.cached_segments}, pending={len(pending)}")

    batches = group_segments_for_batches(
        pending,
        max_chars=config.segmentation.max_chars_per_batch,
        max_segments=config.segmentation.max_segments_per_batch,
    )
    _emit(progress_cb, f"Prepared batches: {len(batches)}")

    batch_outputs: dict[int, tuple[list[Segment], dict[str, str], dict[str, str]]] = {}
    if max_concurrency > 1 and len(batches) > 1:
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_idx = {
                executor.submit(_run_provider_batch, provider, batch, _collect_batch_term_hits(batch, termbase)): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                draft_map, revise_map = future.result()
                batch_outputs[idx] = (batches[idx], draft_map, revise_map)
                _emit(progress_cb, f"Batch completed: {idx + 1}/{len(batches)}")
    else:
        for idx, batch in enumerate(batches):
            _emit(progress_cb, f"Batch running: {idx + 1}/{len(batches)}")
            draft_map, revise_map = _run_provider_batch(provider, batch, _collect_batch_term_hits(batch, termbase))
            batch_outputs[idx] = (batch, draft_map, revise_map)
            _emit(progress_cb, f"Batch completed: {idx + 1}/{len(batches)}")

    for idx in sorted(batch_outputs.keys()):
        batch, draft_map, revise_map = batch_outputs[idx]
        for seg in batch:
            source_hash = sha256_text(seg.source_text)
            out_text = revise_map.get(seg.id, "")
            out[seg.id] = out_text
            store.upsert_translation(
                segment_id=seg.id,
                source_hash=source_hash,
                config_hash=config_hash,
                provider=provider.__class__.__name__,
                draft_text=draft_map.get(seg.id),
                revise_text=out_text,
            )
            stats.translated_segments += 1

        stats.llm_calls += 1
        store.commit()

    return out


def _collect_batch_term_hits(batch: list[Segment], termbase: Termbase) -> list[dict[str, str | bool]]:
    hits: dict[str, dict[str, str | bool]] = {}
    for seg in batch:
        for hit in termbase.hits_for_text(seg.source_text):
            key = f"{hit['source']}->{hit['target']}"
            hits[key] = hit
    return list(hits.values())


def _run_provider_batch(
    provider: object,
    batch: list[Segment],
    term_hits: list[dict[str, str | bool]],
) -> tuple[dict[str, str], dict[str, str]]:
    draft = provider.translate_segments(batch, term_hits)
    draft = post_edit(draft)
    revise = provider.revise_segments(batch, draft, term_hits)
    draft_map = {item.id: item.translated_text for item in draft}
    revise_map = {item.id: item.translated_text for item in revise}
    return draft_map, revise_map


def _emit(progress_cb: ProgressCallback | None, message: str) -> None:
    if progress_cb is None:
        return
    try:
        progress_cb(message)
    except Exception:
        # Progress reporting must never break translation pipeline.
        return


def _write_failure_artifacts(qa_report_path: Path, qa_summary_path: Path, message: str, stage: str) -> None:
    report_payload = {
        "total_segments": 0,
        "translated_segments": 0,
        "error_count": 1,
        "warn_count": 0,
        "issues": [
            {
                "segment_id": None,
                "severity": "error",
                "type": "runtime_fail",
                "message": f"{stage}: {message}",
                "meta": {"stage": stage},
            }
        ],
    }
    qa_report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = "\n".join(
        [
            "# QA Summary",
            "",
            "- total_segments: 0",
            "- error_count: 1",
            "- warn_count: 0",
            "",
            "## Top Issue Types",
            f"- runtime_fail: 1 ({stage})",
            "",
            f"Message: {message}",
        ]
    )
    qa_summary_path.write_text(summary, encoding="utf-8")
