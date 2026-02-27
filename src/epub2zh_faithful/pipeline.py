from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import json
import re
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import AppConfig, load_config
from .epub_parser import cleanup_workspace, unpack_epub
from .epub_writer import repack_epub
from .llm_client import LLMClientFactory, ProviderError, ProviderSettings
from .models import NodeTask, RunStats, Segment
from .post_editor import post_edit
from .qa_checker import capture_integrity_snapshot, qa_passes_gate, run_qa, write_qa_reports
from .placeholder_codec import PLACEHOLDER_TOKEN_RE, placeholder_counts
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


class PipelineCancelled(PipelineError):
    pass


ProgressCallback = Callable[[str], None]
StopCallback = Callable[[], bool]


def run_translation(args: object, progress_cb: ProgressCallback | None = None, should_stop_cb: StopCallback | None = None) -> int:
    _emit(progress_cb, "Loading config and termbase...")
    config = load_config(getattr(args, "config", None))
    termbase = Termbase.load(getattr(args, "termbase", None))
    cache_path = getattr(args, "cache", None) or "cache.sqlite"

    provider_name = getattr(args, "provider")
    if provider_name == "mixed":
        draft_provider = getattr(args, "draft_provider", None) or "openai"
        revise_provider = getattr(args, "revise_provider", None) or "deepseek"
    elif provider_name == "dashscope-mt":
        draft_provider = getattr(args, "draft_provider", None) or "dashscope-mt"
        revise_provider = getattr(args, "revise_provider", None) or "none"
    else:
        draft_provider = getattr(args, "draft_provider", None) or provider_name
        revise_provider = getattr(args, "revise_provider", None) or provider_name

    model_arg = getattr(args, "model", None)
    if model_arg is None:
        if provider_name == "dashscope":
            model_arg = "qwen-plus"
        elif provider_name == "dashscope-mt":
            model_arg = "qwen-mt-plus"
        elif provider_name == "deepseek":
            model_arg = "deepseek-chat"
        else:
            model_arg = "gpt-5-mini"

    provider_settings = ProviderSettings(
        provider=provider_name,
        draft_provider=draft_provider,
        revise_provider=revise_provider,
        model=model_arg,
        draft_model=getattr(args, "draft_model", None),
        revise_model=getattr(args, "revise_model", None),
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    output_path = Path(getattr(args, "output"))
    artifacts_dir = ensure_dir(output_path.parent / f"{output_path.stem}_artifacts")
    qa_report_path = artifacts_dir / "qa_report.json"
    qa_summary_path = artifacts_dir / "qa_summary.md"

    store = TMStore(cache_path)
    stats = RunStats()

    book = None
    workdir_keep = bool(getattr(args, "keep_workdir", False))
    try:
        _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before provider initialization")
        _emit(progress_cb, "Initializing provider...")
        provider = LLMClientFactory.build(provider_settings, config)

        _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before EPUB unpack")
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

        config_hash = _build_config_hash(config, termbase.cache_fingerprint(), provider_settings)
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
            max_concurrency=max(1, int(getattr(args, "max_concurrency", 2))),
            stats=stats,
            config=config,
            progress_cb=progress_cb,
            should_stop_cb=should_stop_cb,
        )

        _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before problematic-segment repair")
        _repair_problematic_segments(
            segments=segments,
            segment_translations=segment_translations,
            provider=provider,
            store=store,
            termbase=termbase,
            config_hash=config_hash,
            max_concurrency=max(1, int(getattr(args, "max_concurrency", 2))),
            stats=stats,
            progress_cb=progress_cb,
            should_stop_cb=should_stop_cb,
        )

        _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before writing outputs")
        _emit(
            progress_cb,
            f"Translation complete: translated={stats.translated_segments}, cached={stats.cached_segments}, llm_calls={stats.llm_calls}",
        )
        unchanged_segments = sum(
            1
            for seg in segments
            if (segment_translations.get(seg.id, "").strip() == seg.source_text.strip())
        )
        _emit(progress_cb, f"Unchanged segments: {unchanged_segments}/{len(segments)}")

        node_translations = merge_segment_translations(segments, segment_translations)

        _emit(progress_cb, "Writing translations back to XHTML/TOC...")
        apply_node_translations(
            workdir=book.workspace_dir,
            node_tasks=xhtml_tasks,
            node_translations=node_translations,
        )

        toc_translation_map = {task.id: node_translations.get(task.id, "") for task in toc_tasks}
        apply_toc_translations(book.workspace_dir, toc_translation_map, toc_tasks)

        _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before QA")
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

        _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before EPUB repack")
        _emit(progress_cb, "Repacking EPUB...")
        repack_epub(book.workspace_dir, getattr(args, "output"))
        store.commit()

        if qa_passes_gate(config, len(segments), issues):
            _emit(progress_cb, "Finished with exit code 0")
            return 0
        _emit(progress_cb, "Finished with exit code 2 (QA errors present)")
        return 2

    except PipelineCancelled as exc:
        store.record_error(run_id, "cancelled", str(exc))
        store.commit()
        _write_failure_artifacts(
            qa_report_path=qa_report_path,
            qa_summary_path=qa_summary_path,
            message=str(exc),
            stage="cancelled",
        )
        _emit(progress_cb, f"Cancelled: {exc}")
        return 130
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


def _build_config_hash(config: AppConfig, termbase_fingerprint: str, provider_settings: ProviderSettings) -> str:
    payload = {
        "config": config.to_normalized_json(),
        "termbase_fingerprint": termbase_fingerprint,
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
    should_stop_cb: StopCallback | None = None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    pending: list[Segment] = []
    suspicious_cache = 0

    for seg in segments:
        source_hash = sha256_text(seg.source_text)
        store.record_segment(seg.id, seg.file_path, seg.node_selector, seg.order_index, source_hash)
        cached = store.get_cached(seg.id, source_hash, config_hash, prefer_revise=prefer_revise) if resume else None
        if resume and cached is not None:
            if _needs_forced_retry(seg.source_text, cached):
                pending.append(seg)
                suspicious_cache += 1
            else:
                out[seg.id] = cached
                stats.cached_segments += 1
        else:
            pending.append(seg)

    _emit(
        progress_cb,
        f"Cache scan done: hit={stats.cached_segments}, pending={len(pending)}, skipped_suspicious={suspicious_cache}",
    )
    _raise_if_cancelled(should_stop_cb, progress_cb, "Cancelled before batch translation")

    batches = group_segments_for_batches(
        pending,
        max_chars=config.segmentation.max_chars_per_batch,
        max_segments=config.segmentation.max_segments_per_batch,
    )
    _emit(
        progress_cb,
        f"Prepared batches: {len(batches)} (max_segments={config.segmentation.max_segments_per_batch}, "
        f"max_chars={config.segmentation.max_chars_per_batch})",
    )

    batch_outputs: dict[int, tuple[list[Segment], dict[str, str], dict[str, str]]] = {}
    failed_segment_ids: set[str] = set()
    cancel_requested = False

    if max_concurrency > 1 and len(batches) > 1:
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_idx: dict[Future[tuple[dict[str, str], dict[str, str]]], int] = {}
            next_batch_idx = 0
            while next_batch_idx < len(batches) or future_to_idx:
                if not cancel_requested and _is_cancelled(should_stop_cb):
                    cancel_requested = True
                    _emit(progress_cb, "Stop requested: no more new batches will be submitted")

                while (
                    not cancel_requested
                    and next_batch_idx < len(batches)
                    and len(future_to_idx) < max_concurrency
                ):
                    idx = next_batch_idx
                    batch = batches[idx]
                    future = executor.submit(
                        _run_provider_batch,
                        provider,
                        batch,
                        _collect_batch_term_hits(batch, termbase),
                        should_stop_cb,
                    )
                    future_to_idx[future] = idx
                    next_batch_idx += 1

                if not future_to_idx:
                    break

                done, _ = wait(tuple(future_to_idx.keys()), timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    idx = future_to_idx.pop(future)
                    try:
                        draft_map, revise_map = future.result()
                        batch_outputs[idx] = (batches[idx], draft_map, revise_map)
                    except PipelineCancelled:
                        cancel_requested = True
                    except Exception as exc:  # noqa: BLE001
                        _emit(progress_cb, f"Batch {idx + 1} failed: {exc}")
                        for seg in batches[idx]:
                            failed_segment_ids.add(seg.id)
                    _emit(progress_cb, f"Batch completed: {idx + 1}/{len(batches)}")
    else:
        for idx, batch in enumerate(batches):
            if _is_cancelled(should_stop_cb):
                cancel_requested = True
                _emit(progress_cb, "Stop requested: ending batch loop")
                break
            _emit(progress_cb, f"Batch running: {idx + 1}/{len(batches)}")
            try:
                draft_map, revise_map = _run_provider_batch(
                    provider,
                    batch,
                    _collect_batch_term_hits(batch, termbase),
                    should_stop_cb,
                )
                batch_outputs[idx] = (batch, draft_map, revise_map)
            except PipelineCancelled:
                cancel_requested = True
                _emit(progress_cb, "Stop requested during batch run")
                break
            except Exception as exc:  # noqa: BLE001
                _emit(progress_cb, f"Batch {idx + 1} failed: {exc}")
                for seg in batch:
                    failed_segment_ids.add(seg.id)
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

    if failed_segment_ids:
        stats.failed_segments += len(failed_segment_ids)
        _emit(
            progress_cb,
            f"Failed segments in primary pass: {len(failed_segment_ids)} (will be handled in repair phase)",
        )
    if cancel_requested:
        raise PipelineCancelled("Cancelled by user during translation")

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
    should_stop_cb: StopCallback | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    _raise_if_cancelled(should_stop_cb, None, "Cancelled before provider batch call")
    try:
        draft = provider.translate_segments(batch, term_hits)
        draft = post_edit(draft)
        _raise_if_cancelled(should_stop_cb, None, "Cancelled before revise call")
        revise = provider.revise_segments(batch, draft, term_hits)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Batch translation failed: {exc}") from exc

    draft_map = {item.id: item.translated_text for item in draft}
    revise_map = {item.id: item.translated_text for item in revise}
    for seg in batch:
        revise_map[seg.id] = _select_preferred_candidate(
            seg.source_text,
            revise_map.get(seg.id, ""),
            draft_map.get(seg.id, ""),
        )

    retry_targets = [
        seg
        for seg in batch
        if (
            _needs_forced_retry(seg.source_text, revise_map.get(seg.id, ""))
            or _has_placeholder_mismatch(seg.source_text, revise_map.get(seg.id, ""))
        )
    ]
    for _ in range(2):
        _raise_if_cancelled(should_stop_cb, None, "Cancelled during retry loop")
        if not retry_targets:
            break
        try:
            retry_draft = post_edit(provider.translate_segments(retry_targets, term_hits))
            retry_revise = provider.revise_segments(retry_targets, retry_draft, term_hits)
            retry_draft_map = {item.id: item.translated_text for item in retry_draft}
            retry_revise_map = {item.id: item.translated_text for item in retry_revise}
        except Exception:
            continue

        next_retry_targets: list[Segment] = []
        for seg in retry_targets:
            candidate = _select_preferred_candidate(
                seg.source_text,
                retry_revise_map.get(seg.id, ""),
                retry_draft_map.get(seg.id, ""),
            )
            if not candidate.strip():
                next_retry_targets.append(seg)
                continue
            if not _needs_forced_retry(seg.source_text, candidate) and not _has_placeholder_mismatch(seg.source_text, candidate):
                draft_map[seg.id] = retry_draft_map.get(seg.id, draft_map.get(seg.id, ""))
                revise_map[seg.id] = candidate
            else:
                next_retry_targets.append(seg)
        retry_targets = next_retry_targets

    return draft_map, revise_map


def _emit(progress_cb: ProgressCallback | None, message: str) -> None:
    if progress_cb is None:
        return
    try:
        progress_cb(message)
    except Exception:
        return


def _is_cancelled(should_stop_cb: StopCallback | None) -> bool:
    if should_stop_cb is None:
        return False
    try:
        return bool(should_stop_cb())
    except Exception:
        return False


def _raise_if_cancelled(
    should_stop_cb: StopCallback | None,
    progress_cb: ProgressCallback | None,
    message: str,
) -> None:
    if not _is_cancelled(should_stop_cb):
        return
    _emit(progress_cb, message)
    raise PipelineCancelled(message)


LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
JAPANESE_KANA_RE = re.compile(r"[ぁ-ゟ゠-ヿｦ-ﾟー]")


def _needs_forced_retry(source_text: str, translated_text: str) -> bool:
    source = source_text.strip()
    translated = translated_text.strip()
    if not source or source != translated:
        return False
    probe = PLACEHOLDER_TOKEN_RE.sub("", source).strip()
    if not probe:
        return False
    if JAPANESE_KANA_RE.search(probe):
        return True
    if len(probe) < 40:
        return False
    return len(LATIN_LETTER_RE.findall(probe)) >= 20


def _has_placeholder_mismatch(source_text: str, translated_text: str) -> bool:
    return placeholder_counts(source_text) != placeholder_counts(translated_text)


def _repair_missing_placeholders(source_text: str, translated_text: str) -> str:
    src_counts = placeholder_counts(source_text)
    dst_counts = placeholder_counts(translated_text)
    if src_counts == dst_counts:
        return translated_text

    missing_tokens: list[str] = []
    for token, count in src_counts.items():
        diff = count - dst_counts.get(token, 0)
        if diff > 0:
            missing_tokens.extend([token] * diff)
    if not missing_tokens:
        return translated_text

    base = translated_text.strip()
    suffix = "".join(missing_tokens)
    if not base:
        return suffix
    return f"{base} {suffix}"


def _select_preferred_candidate(source_text: str, revise_text: str, draft_text: str) -> str:
    revise = revise_text or ""
    draft = draft_text or ""

    if revise and not _has_placeholder_mismatch(source_text, revise):
        return revise
    if draft and not _has_placeholder_mismatch(source_text, draft):
        return draft
    return _repair_missing_placeholders(source_text, revise or draft)


def _needs_problem_repair(seg: Segment, translated_text: str) -> bool:
    if not translated_text.strip():
        return True
    if _has_placeholder_mismatch(seg.source_text, translated_text):
        return True
    if _needs_forced_retry(seg.source_text, translated_text):
        return True
    return False


def _repair_problematic_segments(
    segments: list[Segment],
    segment_translations: dict[str, str],
    provider: object,
    store: TMStore,
    termbase: Termbase,
    config_hash: str,
    max_concurrency: int,
    stats: RunStats,
    progress_cb: ProgressCallback | None = None,
    should_stop_cb: StopCallback | None = None,
) -> None:
    del max_concurrency

    if _is_cancelled(should_stop_cb):
        _emit(progress_cb, "Stop requested: skipping repair phase")
        return

    pending = [seg for seg in segments if _needs_problem_repair(seg, segment_translations.get(seg.id, ""))]
    if not pending:
        return

    _emit(progress_cb, f"Repair phase started for problematic segments: {len(pending)}")

    still_bad = 0
    for seg in pending:
        if _is_cancelled(should_stop_cb):
            _emit(progress_cb, "Stop requested: ending repair phase early")
            break
        batch = [seg]
        try:
            draft_map, revise_map = _run_provider_batch(
                provider,
                batch,
                _collect_batch_term_hits(batch, termbase),
                should_stop_cb,
            )
        except PipelineCancelled:
            _emit(progress_cb, "Stop requested: ending repair phase early")
            break
        except Exception as exc:  # noqa: BLE001
            _emit(progress_cb, f"Repair failed for segment {seg.id}: {exc}")
            stats.failed_segments += 1
            continue

        out_text = _select_preferred_candidate(
            seg.source_text,
            revise_map.get(seg.id, ""),
            draft_map.get(seg.id, ""),
        )
        segment_translations[seg.id] = out_text
        source_hash = sha256_text(seg.source_text)
        store.upsert_translation(
            segment_id=seg.id,
            source_hash=source_hash,
            config_hash=config_hash,
            provider=provider.__class__.__name__,
            draft_text=draft_map.get(seg.id),
            revise_text=out_text,
        )
        if _needs_problem_repair(seg, out_text):
            still_bad += 1
        stats.llm_calls += 1

    store.commit()

    if still_bad > 0:
        _emit(progress_cb, f"Repair completed with unresolved segments: {still_bad}")
    else:
        _emit(progress_cb, "Repair phase completed with all target segments fixed")


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
