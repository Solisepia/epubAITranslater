from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .utils import load_yaml_or_json

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass(slots=True)
class Term:
    source: str
    target: str
    force: bool = False
    note: str = ""


def format_term_target(source: str, target: str) -> str:
    source_clean = source.strip()
    target_clean = target.strip()
    if not source_clean or not target_clean:
        return target_clean
    if f"（{source_clean}）" in target_clean or f"({source_clean})" in target_clean:
        return target_clean
    return f"{target_clean}（{source_clean}）"


def extract_term_left(source: str, target: str) -> str:
    source_clean = source.strip()
    target_clean = target.strip()
    if not source_clean or not target_clean:
        return target_clean
    full_suffix = f"（{source_clean}）"
    half_suffix = f"({source_clean})"
    if target_clean.endswith(full_suffix):
        return target_clean[: -len(full_suffix)].strip()
    if target_clean.endswith(half_suffix):
        return target_clean[: -len(half_suffix)].strip()
    return target_clean


def has_cjk_left(source: str, target: str) -> bool:
    left = extract_term_left(source, target)
    return bool(CJK_RE.search(left))


class Termbase:
    def __init__(self, terms: list[Term], version_id: str) -> None:
        normalized_terms: list[Term] = []
        for term in terms:
            source = str(term.source).strip()
            target = format_term_target(source, str(term.target))
            if not source or not target or not has_cjk_left(source, target):
                continue
            normalized_terms.append(
                Term(
                    source=source,
                    target=target,
                    force=bool(term.force),
                    note=str(term.note),
                )
            )
        self.terms = sorted(normalized_terms, key=lambda t: len(t.source), reverse=True)
        self.version_id = version_id

    @classmethod
    def load(cls, path: str | None) -> "Termbase":
        if not path:
            return cls([], "empty")
        payload = load_yaml_or_json(path)
        raw_terms = payload.get("terms", [])
        terms = [
            Term(
                source=str(item.get("source", "")),
                target=str(item.get("target", "")),
                force=bool(item.get("force", False)),
                note=str(item.get("note", "")),
            )
            for item in raw_terms
            if item.get("source") and item.get("target")
        ]
        version = str(payload.get("version", "1"))
        return cls(terms, version)

    def hits_for_text(self, text: str) -> list[dict[str, str | bool]]:
        lower = text.lower()
        hits: list[dict[str, str | bool]] = []
        for term in self.terms:
            if term.source.lower() in lower:
                hits.append(
                    {
                        "source": term.source,
                        "target": term.target,
                        "force": term.force,
                        "note": term.note,
                    }
                )
        return hits

    def force_terms(self) -> list[Term]:
        return [term for term in self.terms if term.force]

    def cache_fingerprint(self) -> str:
        payload = {
            "version_id": self.version_id,
            "terms": [
                {
                    "source": term.source,
                    "target": term.target,
                    "force": term.force,
                    "note": term.note,
                }
                for term in sorted(self.terms, key=lambda t: (t.source, t.target, t.force, t.note))
            ],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
