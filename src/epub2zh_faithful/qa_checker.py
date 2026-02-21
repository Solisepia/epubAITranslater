from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urldefrag

from lxml import etree

from .config import AppConfig
from .dom_utils import parse_xml_file
from .models import BookModel, NodeTask, QAIssue, Segment, TocSnapshot
from .placeholder_codec import PLACEHOLDER_TOKEN_RE, placeholder_counts
from .terminology import Termbase
from .utils import dump_json, localname

WATCH_ATTR_PREFIXES = ("aria-",)
WATCH_ATTRS = {"id", "href", "src", "role", "epub:type"}
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
JAPANESE_KANA_RE = re.compile(r"[ぁ-ゟ゠-ヿｦ-ﾟー]")


def capture_integrity_snapshot(workdir: str, files: list[str]) -> dict[str, list[str]]:
    root = Path(workdir)
    snapshot: dict[str, list[str]] = {}
    for rel in files:
        tree = parse_xml_file(str(root / rel))
        signatures: list[str] = []
        for elem in tree.getroot().iter():
            if not isinstance(elem.tag, str):
                continue
            attrs = _watched_attrs(elem)
            if not attrs:
                continue
            signatures.append(_attr_signature(localname(elem.tag), attrs))
        snapshot[rel] = signatures
    return snapshot


def run_qa(
    workdir: str,
    config: AppConfig,
    book: BookModel,
    segments: list[Segment],
    segment_translations: dict[str, str],
    node_tasks: list[NodeTask],
    node_translations: dict[str, str],
    toc_before: TocSnapshot,
    termbase: Termbase,
    integrity_before: dict[str, list[str]],
) -> list[QAIssue]:
    issues: list[QAIssue] = []

    for segment in segments:
        translated = segment_translations.get(segment.id, "")
        if not translated.strip():
            issues.append(QAIssue(segment.id, "error", "empty_translation", "译文为空"))
            continue

        src_counts = placeholder_counts(segment.source_text)
        dst_counts = placeholder_counts(translated)
        if src_counts != dst_counts:
            issues.append(
                QAIssue(
                    segment.id,
                    "error",
                    "placeholder_mismatch",
                    f"占位符不一致：源={src_counts} 译={dst_counts}",
                    {"source": src_counts, "translated": dst_counts},
                )
            )
        unchanged_issue = _unchanged_translation_issue(segment, translated)
        if unchanged_issue is not None:
            issues.append(unchanged_issue)

    for term in termbase.force_terms():
        for segment in segments:
            if term.source.lower() in segment.source_text.lower():
                translated = segment_translations.get(segment.id, "")
                if term.target not in translated:
                    issues.append(
                        QAIssue(
                            segment.id,
                            "error",
                            "term_inconsistency",
                            f"强制术语未遵守: {term.source} -> {term.target}",
                        )
                    )

    task_map = {t.id: t for t in node_tasks}
    for task_id, translated in node_translations.items():
        task = task_map.get(task_id)
        if not task or task.poetry_line_count is None:
            continue
        out_count = max(1, translated.count("\n") + 1)
        if out_count != task.poetry_line_count:
            issues.append(
                QAIssue(
                    None,
                    "error",
                    "poetry_line_mismatch",
                    f"诗歌行数变化: expected={task.poetry_line_count}, got={out_count}",
                    {"node_task_id": task_id},
                )
            )

    issues.extend(_check_xml_parseable(workdir, book.xhtml_files))
    issues.extend(_check_links(workdir, book.xhtml_files))
    issues.extend(_check_toc_hrefs(workdir, book.toc_nav_path, book.toc_ncx_path, toc_before))
    issues.extend(_check_integrity_attrs(workdir, integrity_before))

    return issues


def write_qa_reports(
    output_dir: str,
    segments: list[Segment],
    issues: list[QAIssue],
    report_path: str,
    summary_path: str,
) -> None:
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warn"]
    payload = {
        "total_segments": len(segments),
        "translated_segments": len(segments),
        "error_count": len(errors),
        "warn_count": len(warns),
        "issues": [
            {
                "segment_id": i.segment_id,
                "severity": i.severity,
                "type": i.issue_type,
                "message": i.message,
                "meta": i.meta,
            }
            for i in issues
        ],
    }
    dump_json(report_path, payload)

    top_types: dict[str, int] = {}
    for issue in issues:
        top_types[issue.issue_type] = top_types.get(issue.issue_type, 0) + 1

    lines = [
        "# QA Summary",
        "",
        f"- total_segments: {len(segments)}",
        f"- error_count: {len(errors)}",
        f"- warn_count: {len(warns)}",
        "",
        "## Top Issue Types",
    ]
    for key, count in sorted(top_types.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- {key}: {count}")

    Path(summary_path).write_text("\n".join(lines), encoding="utf-8")


def qa_passes_gate(config: AppConfig, total_segments: int, issues: list[QAIssue]) -> bool:
    errors = [x for x in issues if x.severity == "error"]
    warns = [x for x in issues if x.severity == "warn"]
    warn_cap = max(int(total_segments * config.qa.warn_ratio_limit), config.qa.warn_min_cap)
    return len(errors) == 0 and len(warns) <= warn_cap


def _check_xml_parseable(workdir: str, files: list[str]) -> list[QAIssue]:
    issues: list[QAIssue] = []
    root = Path(workdir)
    for rel in files:
        try:
            parse_xml_file(str(root / rel))
        except Exception as exc:  # noqa: BLE001
            issues.append(QAIssue(None, "error", "html_parse_fail", f"{rel}: {exc}"))
    return issues


def _check_links(workdir: str, files: list[str]) -> list[QAIssue]:
    root = Path(workdir)
    ids_map: dict[str, set[str]] = {}
    link_refs: list[tuple[str, str]] = []

    for rel in files:
        rel_norm = Path(rel).as_posix()
        tree = parse_xml_file(str(root / rel))
        ids: set[str] = set()
        for elem in tree.getroot().iter():
            if not isinstance(elem.tag, str):
                continue
            node_id = elem.get("id")
            if node_id:
                ids.add(node_id)
            href = elem.get("href")
            if href:
                link_refs.append((rel_norm, href))
        ids_map[rel_norm] = ids

    issues: list[QAIssue] = []
    for rel, href in link_refs:
        if href.startswith("http://") or href.startswith("https://") or href.startswith("mailto:"):
            continue
        file_part, frag = urldefrag(href)
        target_file = (Path(rel).parent / file_part).as_posix() if file_part else rel
        if frag:
            if target_file not in ids_map:
                issues.append(QAIssue(None, "error", "link_break", f"href target file missing: {href} from {rel}"))
                continue
            if frag not in ids_map[target_file]:
                issues.append(QAIssue(None, "error", "link_break", f"href fragment missing: {href} from {rel}"))

    return issues


def _check_toc_hrefs(workdir: str, nav_path: str | None, ncx_path: str | None, before: TocSnapshot) -> list[QAIssue]:
    after: list[str] = []
    root = Path(workdir)

    if nav_path:
        tree = parse_xml_file(str(root / nav_path))
        for elem in tree.xpath("//*[local-name()='nav']//*[local-name()='a']"):
            if isinstance(elem, etree._Element) and elem.get("href"):
                after.append(elem.get("href", ""))

    if ncx_path:
        tree = parse_xml_file(str(root / ncx_path))
        for elem in tree.xpath("//*[local-name()='navPoint']/*[local-name()='content']"):
            if isinstance(elem, etree._Element) and elem.get("src"):
                after.append(elem.get("src", ""))

    if before.hrefs != after:
        return [QAIssue(None, "error", "toc_href_mismatch", "TOC href changed unexpectedly")]
    return []


def _check_integrity_attrs(workdir: str, before: dict[str, list[str]]) -> list[QAIssue]:
    root = Path(workdir)
    issues: list[QAIssue] = []

    for rel, expected in before.items():
        tree = parse_xml_file(str(root / rel))
        now: list[str] = []
        for elem in tree.getroot().iter():
            if not isinstance(elem.tag, str):
                continue
            attrs = _watched_attrs(elem)
            if not attrs:
                continue
            now.append(_attr_signature(localname(elem.tag), attrs))

        if expected != now:
            issues.append(
                QAIssue(
                    None,
                    "error",
                    "attribute_changed",
                    f"Watched attributes changed in {rel}",
                    {"before_count": len(expected), "after_count": len(now)},
                )
            )

    return issues


def _watched_attrs(elem: etree._Element) -> dict[str, str]:
    watched: dict[str, str] = {}
    for key, value in elem.attrib.items():
        local = localname(key)
        normalized = "epub:type" if key.endswith("}type") else local
        if normalized in WATCH_ATTRS or any(normalized.startswith(prefix) for prefix in WATCH_ATTR_PREFIXES):
            watched[normalized] = value
    return watched


def _attr_signature(tag: str, attrs: dict[str, str]) -> str:
    return f"{tag}|{json.dumps(attrs, ensure_ascii=False, sort_keys=True)}"


def _unchanged_translation_issue(segment: Segment, translated: str) -> QAIssue | None:
    source = segment.source_text.strip()
    output = translated.strip()
    if not source or source != output:
        return None

    probe = PLACEHOLDER_TOKEN_RE.sub("", source).strip()
    if not probe:
        return None

    kana_count = len(JAPANESE_KANA_RE.findall(probe))
    if kana_count >= 2:
        return QAIssue(segment.id, "error", "same_as_source", "译文与原文完全一致（含日文假名）")

    latin_count = len(LATIN_LETTER_RE.findall(probe))
    if len(probe) >= 40 and latin_count >= 20:
        return QAIssue(segment.id, "error", "same_as_source", "译文与原文完全一致（长拉丁文本）")

    return None
