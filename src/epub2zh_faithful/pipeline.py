from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
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


ProgressCallback = Callable[[str], None]


def run_translation(args: object, progress_cb: ProgressCallback | None = None) -> int:
    _emit(progress_cb, "Loading config and termbase...")
    config = load_config(getattr(args, "config", None))
    termbase = Termbase.load(getattr(args, "termbase", None))
    cache_path = getattr(args, "cache", None) or "cache.sqlite"
    provider_name = getattr(args, "provider")
    actual_provider = provider_name if provider_name != "dashscope-mt" else "dashscope"
    if provider_name == "mixed":
        draft_provider = getattr(args, "draft_provider", None) or "openai"
        revise_provider = getattr(args, "revise_provider", None) or "deepseek"
    else:
        draft_provider = getattr(args, "draft_provider", None) or actual_provider
        revise_provider = getattr(args, "revise_provider", None) or actual_provider

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
        )
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
        )
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

    batches = group_segments_for_batches(
        pending,
        max_chars=config.segmentation.max_chars_per_batch,
        max_segments=config.segmentation.max_segments_per_batch,
    )
    _emit(progress_cb, f"[翻译] 准备批次：{len(batches)} 批 (每批最多{config.segmentation.max_segments_per_batch} 段/{config.segmentation.max_chars_per_batch} 字符)")

    batch_outputs: dict[int, tuple[list[Segment], dict[str, str], dict[str, str]]] = {}
    failed_segments: list[tuple[Segment, str]] = []
    
    if max_concurrency > 1 and len(batches) > 1:
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_idx = {
                executor.submit(_run_provider_batch, provider, batch, _collect_batch_term_hits(batch, termbase)): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    draft_map, revise_map = future.result()
                    batch_outputs[idx] = (batches[idx], draft_map, revise_map)
                except Exception as e:
                    _emit(progress_cb, f"[错误] 批次 {idx + 1} 翻译失败：{e}")
                    for seg in batches[idx]:
                        failed_segments.append((seg, str(e)))
                _emit(progress_cb, f"[翻译] 批次完成：{idx + 1}/{len(batches)}")
    else:
        for idx, batch in enumerate(batches):
            _emit(progress_cb, f"[翻译] 批次进行中：{idx + 1}/{len(batches)}")
            try:
                draft_map, revise_map = _run_provider_batch(provider, batch, _collect_batch_term_hits(batch, termbase))
                batch_outputs[idx] = (batch, draft_map, revise_map)
            except Exception as e:
                _emit(progress_cb, f"[错误] 批次 {idx + 1} 翻译失败：{e}")
                for seg in batch:
                    failed_segments.append((seg, str(e)))
            _emit(progress_cb, f"Batch completed: {idx + 1}/{len(batches)}")

    # 检查是否有段落未翻译
    translated_ids = set()
    for idx, (batch, draft_map, revise_map) in batch_outputs.items():
        for seg in batch:
            out_text = revise_map.get(seg.id, "")
            if out_text.strip():
                translated_ids.add(seg.id)
            out[seg.id] = out_text
            source_hash = sha256_text(seg.source_text)
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
    
    # 报告并尝试重试失败的段落
    if failed_segments:
        _emit(progress_cb, f"[警告] {len(failed_segments)} 个段落翻译失败，尝试单独重试...")
        
        # 尝试单独重试失败的段落（降低并发，逐段重试）
        retry_failed: list[Segment] = [seg for seg, _ in failed_segments]
        for seg in retry_failed:
            try:
                _emit(progress_cb, f"  重试段落 {seg.id}...")
                retry_draft = post_edit(provider.translate_segments([seg], []))
                retry_revise = provider.revise_segments([seg], retry_draft, [])
                result = retry_revise[0].translated_text if retry_revise else ""
                
                if result.strip():
                    out[seg.id] = result
                    _emit(progress_cb, f"  ✓ 段落 {seg.id} 重试成功")
                else:
                    out[seg.id] = seg.source_text
                    _emit(progress_cb, f"  ✗ 段落 {seg.id} 重试仍失败，使用原文")
            except Exception as e:
                out[seg.id] = seg.source_text
                _emit(progress_cb, f"  ✗ 段落 {seg.id} 重试异常：{e}，使用原文")
    
    # 检查遗漏的段落
    missing_count = 0
    for seg in segments:
        source_hash = sha256_text(seg.source_text)
        if seg.id not in out or not out[seg.id].strip():
            missing_count += 1
            # 尝试单独翻译遗漏的段落
            try:
                _emit(progress_cb, f"  补翻段落 {seg.id}...")
                draft = post_edit(provider.translate_segments([seg], []))
                revise = provider.revise_segments([seg], draft, [])
                result = revise[0].translated_text if revise else ""
                
                if result.strip():
                    out[seg.id] = result
                    _emit(progress_cb, f"  ✓ 段落 {seg.id} 补翻成功")
                else:
                    out[seg.id] = seg.source_text
            except Exception as e:
                _emit(progress_cb, f"  ✗ 段落 {seg.id} 补翻失败：{e}，使用原文")
                out[seg.id] = seg.source_text
            
            # 记录到数据库
            store.upsert_translation(
                segment_id=seg.id,
                source_hash=source_hash,
                config_hash=config_hash,
                provider=provider.__class__.__name__,
                draft_text=out[seg.id] if out[seg.id] != seg.source_text else None,
                revise_text=out[seg.id],
            )
    
    if missing_count > 0:
        final_missing = sum(1 for seg in segments if out.get(seg.id, "") == seg.source_text)
        if final_missing > 0:
            _emit(progress_cb, f"[警告] 最终仍有 {final_missing} 个段落使用原文，请检查 API 状态或降低并发数")

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
        if not retry_targets:
            break
        retry_draft = post_edit(provider.translate_segments(retry_targets, term_hits))
        retry_revise = provider.revise_segments(retry_targets, retry_draft, term_hits)
        retry_draft_map = {item.id: item.translated_text for item in retry_draft}
        retry_revise_map = {item.id: item.translated_text for item in retry_revise}
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
        # Progress reporting must never break translation pipeline.
        return


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
) -> None:
    pending = [seg for seg in segments if _needs_problem_repair(seg, segment_translations.get(seg.id, ""))]
    if not pending:
        return

    _emit(progress_cb, f"Repair pass: targeted segments={len(pending)}")

    single_batches = [[seg] for seg in pending]
    batch_outputs: dict[int, tuple[list[Segment], dict[str, str], dict[str, str]]] = {}
    if max_concurrency > 1 and len(single_batches) > 1:
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_idx = {
                executor.submit(_run_provider_batch, provider, batch, _collect_batch_term_hits(batch, termbase)): idx
                for idx, batch in enumerate(single_batches)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                draft_map, revise_map = future.result()
                batch_outputs[idx] = (single_batches[idx], draft_map, revise_map)
    else:
        for idx, batch in enumerate(single_batches):
            draft_map, revise_map = _run_provider_batch(provider, batch, _collect_batch_term_hits(batch, termbase))
            batch_outputs[idx] = (batch, draft_map, revise_map)

    still_bad = 0
    for idx in sorted(batch_outputs.keys()):
        batch, draft_map, revise_map = batch_outputs[idx]
        seg = batch[0]
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
    _emit(progress_cb, f"Repair pass complete: unresolved={still_bad}")


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
