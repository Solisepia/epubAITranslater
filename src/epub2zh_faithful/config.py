from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

STYLE_OPTIONS = (
    "faithful_literal",
    "faithful_fluent",
    "literary_cn",
    "concise_cn",
)
DEFAULT_STYLE = "faithful_literal"
FIXED_TARGET_LANG = "zh-Hans"


@dataclass(slots=True)
class LatinMode:
    translate_normally: bool = True


@dataclass(slots=True)
class TableMode:
    preserve_numbers: bool = True
    preserve_abbreviations: bool = True


@dataclass(slots=True)
class SegmentationConfig:
    max_chars_per_segment: int = 1200
    max_chars_per_batch: int = 8000
    max_segments_per_batch: int = 20
    sentence_split_fallback: bool = True


@dataclass(slots=True)
class ContextConfig:
    use_prev_segment: bool = True
    prev_segment_chars: int = 300
    use_term_hints: bool = True


@dataclass(slots=True)
class LLMConfig:
    temperature: float = 0.0
    max_retries: int = 8
    retry_backoff_seconds: list[int] = field(default_factory=lambda: [2, 4, 8, 16, 32, 60, 60, 60])
    timeout_seconds: int = 120


@dataclass(slots=True)
class QAConfig:
    warn_ratio_limit: float = 0.005
    warn_min_cap: int = 20


@dataclass(slots=True)
class AppConfig:
    style: str = DEFAULT_STYLE
    translate_toc: bool = True
    translate_titles: bool = True
    latin_mode: LatinMode = field(default_factory=LatinMode)
    table_mode: TableMode = field(default_factory=TableMode)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    qa: QAConfig = field(default_factory=QAConfig)

    def to_normalized_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_dict(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text) or {}


def load_config(path: str | None) -> AppConfig:
    data = _load_dict(path)
    cfg = AppConfig()
    _merge_into_dataclass(cfg, data)
    cfg.style = normalize_style(cfg.style)
    return cfg


def _merge_into_dataclass(obj: Any, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if not hasattr(obj, key):
            continue
        current = getattr(obj, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _merge_into_dataclass(current, value)
        else:
            setattr(obj, key, value)


def normalize_style(style: str) -> str:
    candidate = (style or "").strip().lower()
    if candidate in STYLE_OPTIONS:
        return candidate
    return DEFAULT_STYLE
