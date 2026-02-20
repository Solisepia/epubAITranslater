from __future__ import annotations

from dataclasses import dataclass

from .utils import load_yaml_or_json


@dataclass(slots=True)
class Term:
    source: str
    target: str
    force: bool = False
    note: str = ""


class Termbase:
    def __init__(self, terms: list[Term], version_id: str) -> None:
        self.terms = sorted(terms, key=lambda t: len(t.source), reverse=True)
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
