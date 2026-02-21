from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SegmentType(str, Enum):
    TITLE = "title"
    TOC = "toc"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    FOOTNOTE = "footnote"
    POETRY_LINE = "poetry_line"
    TABLE_CELL = "table_cell"
    CODE_SKIP = "code_skip"


@dataclass(slots=True)
class Segment:
    id: str
    node_task_id: str
    chunk_index: int
    segment_type: SegmentType
    file_path: str
    node_selector: str
    order_index: int
    source_lang: str
    target_lang: str
    source_text: str
    placeholders: list[str] = field(default_factory=list)
    context_prev_source: str = ""
    context_prev_translated: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TranslationResult:
    id: str
    translated_text: str
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QAIssue:
    segment_id: str | None
    severity: str
    issue_type: str
    message: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TocItem:
    href: str
    label_text: str
    file_path: str
    node_selector: str
    kind: str


@dataclass(slots=True)
class NodeTask:
    id: str
    file_path: str
    node_selector: str
    segment_type: SegmentType
    source_text: str
    placeholder_map: dict[str, str]
    order_index: int
    source_lang: str = "en"
    target_lang: str = "zh-Hans"
    poetry_line_count: int | None = None


@dataclass(slots=True)
class BookModel:
    workspace_dir: str
    rootfile_path: str
    opf_path: str
    opf_dir: str
    spine_items: list[str]
    xhtml_files: list[str]
    manifest_by_id: dict[str, dict[str, str]]
    toc_nav_path: str | None = None
    toc_ncx_path: str | None = None


@dataclass(slots=True)
class RunStats:
    total_segments: int = 0
    translated_segments: int = 0
    cached_segments: int = 0
    llm_calls: int = 0
    failed_segments: int = 0


@dataclass(slots=True)
class RunArtifacts:
    workdir: str
    cache_path: str
    qa_report_path: str
    qa_summary_path: str


@dataclass(slots=True)
class TocSnapshot:
    hrefs: list[str]


@dataclass(slots=True)
class FileParseState:
    file_path: str
    parse_ok: bool
    error: str | None = None
