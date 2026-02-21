from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Callable

import yaml

from .config import FIXED_TARGET_LANG, AppConfig
from .dom_utils import parse_xml_file
from .epub_parser import cleanup_workspace, unpack_epub
from .llm_client import LLMClientFactory, ProviderSettings
from .models import Segment, SegmentType
from .terminology import format_term_target, has_cjk_left
from .utils import has_any_class, localname

ProgressCallback = Callable[[str], None]

BLACKLIST_CONTAINERS = {"code", "pre", "kbd", "samp", "var", "script", "style", "math", "annotation", "semantics"}
NO_TRANSLATE_CLASSES = {"no-translate", "notranslate", "raw", "code"}
CONNECTORS = {"of", "the", "and", "de", "von", "van", "la", "le", "di", "da", "du"}
LEADING_ARTICLES = {"the", "a", "an"}
SINGLE_WORD_STOP = {
    "the",
    "a",
    "an",
    "in",
    "on",
    "at",
    "for",
    "to",
    "from",
    "and",
    "but",
    "or",
    "nor",
    "yet",
    "so",
    "he",
    "she",
    "it",
    "they",
    "we",
    "i",
    "this",
    "that",
    "these",
    "those",
    "chapter",
    "book",
    "part",
}
SENTENCE_SPLIT = re.compile(r"[\n\r.!?;:]+")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*|[A-Z]{2,}")
ROMAN_RE = re.compile(r"^[IVXLCDM]+$")


@dataclass(slots=True)
class GenerateOptions:
    min_freq: int = 2
    max_terms: int = 300
    include_single_word: bool = False
    merge_existing: bool = True
    fill_empty_targets: bool = False
    fill_provider: str = "openai"
    fill_model: str = "gpt-5-mini"
    fill_batch_size: int = 40


def generate_termbase(
    input_epub: str,
    output_path: str,
    options: GenerateOptions,
    progress_cb: ProgressCallback | None = None,
    llm_config: AppConfig | None = None,
) -> dict[str, int]:
    _emit(progress_cb, "Unpacking EPUB for term extraction...")
    book = unpack_epub(input_epub)

    try:
        counter: Counter[str] = Counter()
        total_text_nodes = 0

        for rel in book.xhtml_files:
            full = Path(book.workspace_dir) / rel
            tree = parse_xml_file(str(full))

            texts = tree.xpath("//text()")
            for text_node in texts:
                parent = text_node.getparent()
                if parent is None:
                    continue
                if _is_blocked(parent):
                    continue
                raw = str(text_node).strip()
                if len(raw) < 2:
                    continue
                total_text_nodes += 1
                for phrase in _extract_candidates(raw, options.include_single_word):
                    counter[phrase] += 1

        _emit(progress_cb, f"Scanned text nodes: {total_text_nodes}")

        filtered = [item for item in counter.items() if item[1] >= max(1, options.min_freq)]
        filtered.sort(key=lambda x: (-x[1], -len(x[0]), x[0]))
        selected = filtered[: max(1, options.max_terms)]

        existing_terms = _load_existing_terms(output_path) if options.merge_existing else []
        existing_sources = {str(item.get("source", "")) for item in existing_terms if item.get("source")}

        generated_terms = [
            {
                "source": phrase,
                "target": "",
                "force": False,
                "note": f"auto-generated; freq={freq}",
            }
            for phrase, freq in selected
            if phrase not in existing_sources
        ]

        payload = {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_epub": str(Path(input_epub).name),
            "settings": {
                "min_freq": options.min_freq,
                "max_terms": options.max_terms,
                "include_single_word": options.include_single_word,
                "merge_existing": options.merge_existing,
                "fill_empty_targets": options.fill_empty_targets,
                "fill_provider": options.fill_provider,
                "fill_model": options.fill_model,
                "fill_batch_size": options.fill_batch_size,
            },
            "terms": existing_terms + generated_terms,
        }

        filled_targets = 0
        rejected_non_cjk_targets = 0
        if options.fill_empty_targets:
            fill_cfg = llm_config or AppConfig()
            filled_targets, rejected_non_cjk_targets = _fill_empty_targets_with_ai(payload["terms"], options, fill_cfg, progress_cb)
        cleared_non_cjk_targets = _normalize_term_targets(payload["terms"])

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")

        _emit(
            progress_cb,
            (
                f"Generated terms: {len(generated_terms)} (total in file: {len(payload['terms'])}, "
                f"filled targets: {filled_targets}, rejected no-cjk: {rejected_non_cjk_targets}, "
                f"cleared no-cjk: {cleared_non_cjk_targets})"
            ),
        )

        return {
            "scanned_text_nodes": total_text_nodes,
            "candidate_terms": len(filtered),
            "generated_terms": len(generated_terms),
            "total_terms_in_file": len(payload["terms"]),
            "filled_targets": filled_targets,
            "rejected_non_cjk_targets": rejected_non_cjk_targets,
            "cleared_non_cjk_targets": cleared_non_cjk_targets,
        }
    finally:
        cleanup_workspace(book.workspace_dir, keep=False)


def _extract_candidates(text: str, include_single_word: bool) -> list[str]:
    out: list[str] = []
    for sentence in SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        tokens = WORD_RE.findall(sentence)
        if not tokens:
            continue

        i = 0
        while i < len(tokens):
            if not _is_capital_token(tokens[i]):
                i += 1
                continue

            j = i + 1
            while j < len(tokens):
                t = tokens[j]
                if _is_capital_token(t) or t.lower() in CONNECTORS:
                    j += 1
                    continue
                break

            phrase_tokens = tokens[i:j]
            while phrase_tokens and phrase_tokens[-1].lower() in CONNECTORS:
                phrase_tokens.pop()
            while len(phrase_tokens) > 1 and phrase_tokens[0].lower() in LEADING_ARTICLES:
                phrase_tokens.pop(0)

            if not phrase_tokens:
                i = j
                continue

            if len(phrase_tokens) == 1 and not include_single_word and not phrase_tokens[0].isupper():
                i = j
                continue

            phrase = " ".join(phrase_tokens)
            if _valid_phrase(phrase):
                out.append(phrase)

            i = j

    return out


def _is_capital_token(token: str) -> bool:
    if token.isupper() and len(token) > 1:
        return True
    if len(token) >= 2 and token[0].isupper() and any(ch.isalpha() for ch in token[1:]):
        return True
    return False


def _valid_phrase(phrase: str) -> bool:
    if len(phrase) < 3:
        return False
    if ROMAN_RE.fullmatch(phrase):
        return False

    words = phrase.split()
    if len(words) == 1:
        low = words[0].lower()
        if low in SINGLE_WORD_STOP:
            return False
        if len(words[0]) < 3:
            return False

    return True


def _is_blocked(elem: object) -> bool:
    current = elem
    while current is not None:
        if not hasattr(current, "tag"):
            current = current.getparent() if hasattr(current, "getparent") else None
            continue
        tag = current.tag
        if not isinstance(tag, str):
            current = current.getparent()
            continue
        name = localname(tag)
        if name in BLACKLIST_CONTAINERS:
            return True
        if has_any_class(current.get("class"), NO_TRANSLATE_CLASSES):
            return True
        if (current.get("translate") or "").lower() == "no":
            return True
        current = current.getparent()
    return False


def _load_existing_terms(output_path: str) -> list[dict[str, object]]:
    p = Path(output_path)
    if not p.exists():
        return []
    try:
        payload = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    terms = payload.get("terms", [])
    if isinstance(terms, list):
        return [item for item in terms if isinstance(item, dict) and item.get("source")]
    return []


def _fill_empty_targets_with_ai(
    terms: list[dict[str, object]],
    options: GenerateOptions,
    config: AppConfig,
    progress_cb: ProgressCallback | None,
) -> tuple[int, int]:
    empty_terms = [item for item in terms if str(item.get("source", "")).strip() and not str(item.get("target", "")).strip()]
    if not empty_terms:
        return 0, 0

    provider_name = options.fill_provider
    if provider_name not in {"openai", "deepseek", "mock"}:
        raise ValueError(f"Unsupported fill provider: {provider_name}")

    _emit(
        progress_cb,
        f"Auto-filling empty term targets with AI: {len(empty_terms)} terms ({provider_name}/{options.fill_model})",
    )

    provider = LLMClientFactory.build(
        ProviderSettings(
            provider=provider_name,
            draft_provider=provider_name,
            revise_provider="none",
            model=options.fill_model,
            draft_model=None,
            revise_model=None,
        ),
        config,
    )

    filled = 0
    rejected_non_cjk = 0
    batch_size = max(1, int(options.fill_batch_size))
    total_batches = (len(empty_terms) + batch_size - 1) // batch_size

    for batch_idx, start in enumerate(range(0, len(empty_terms), batch_size), start=1):
        batch_terms = empty_terms[start : start + batch_size]
        segments = [_term_to_segment(start + i + 1, item) for i, item in enumerate(batch_terms)]
        results = provider.translate_segments(segments, termbase_hits=[])
        result_map = {item.id: item.translated_text.strip() for item in results}

        for seg, term in zip(segments, batch_terms):
            translated = result_map.get(seg.id, "").strip()
            if translated:
                source = str(term.get("source", "")).strip()
                formatted = format_term_target(source, translated)
                if has_cjk_left(source, formatted):
                    term["target"] = formatted
                    filled += 1
                else:
                    rejected_non_cjk += 1
                    term["target"] = ""

        _emit(progress_cb, f"Term fill batch completed: {batch_idx}/{total_batches}")

    return filled, rejected_non_cjk


def _term_to_segment(index: int, term: dict[str, object]) -> Segment:
    term_source = str(term.get("source", "")).strip()
    seg_id = f"TERM_{index:06d}"
    return Segment(
        id=seg_id,
        node_task_id=seg_id,
        chunk_index=0,
        segment_type=SegmentType.PARAGRAPH,
        file_path="termbase",
        node_selector=term_source,
        order_index=index,
        source_lang="en",
        target_lang=FIXED_TARGET_LANG,
        source_text=term_source,
    )


def _normalize_term_targets(terms: list[dict[str, object]]) -> int:
    cleared = 0
    for item in terms:
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        if not source or not target:
            continue
        formatted = format_term_target(source, target)
        if has_cjk_left(source, formatted):
            item["target"] = formatted
        else:
            item["target"] = ""
            cleared += 1
    return cleared


def _emit(progress_cb: ProgressCallback | None, message: str) -> None:
    if progress_cb is None:
        return
    try:
        progress_cb(message)
    except Exception:
        return
