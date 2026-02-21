from __future__ import annotations

from epub2zh_faithful.models import Segment, SegmentType
from epub2zh_faithful.pipeline import _needs_forced_retry
from epub2zh_faithful.qa_checker import _unchanged_translation_issue


def _make_segment(source_text: str) -> Segment:
    return Segment(
        id="S000000001",
        node_task_id="NT_000001",
        chunk_index=0,
        segment_type=SegmentType.PARAGRAPH,
        file_path="item/xhtml/p-001.xhtml",
        node_selector="/*[local-name()='html'][1]",
        order_index=1,
        source_lang="ja",
        target_lang="zh-Hans",
        source_text=source_text,
    )


def test_needs_forced_retry_for_japanese_kana_when_unchanged() -> None:
    text = "これは翻訳されるべき文章です。"
    assert _needs_forced_retry(text, text) is True


def test_needs_forced_retry_for_long_latin_when_unchanged() -> None:
    text = "This paragraph is long enough and clearly written in English so it should not stay unchanged."
    assert _needs_forced_retry(text, text) is True


def test_needs_forced_retry_ignores_placeholder_only_content() -> None:
    text = "⟦PH:000001⟧"
    assert _needs_forced_retry(text, text) is False


def test_qa_flags_unchanged_japanese_as_error() -> None:
    text = "これは翻訳されるべき文章です。"
    issue = _unchanged_translation_issue(_make_segment(text), text)
    assert issue is not None
    assert issue.severity == "error"
    assert issue.issue_type == "same_as_source"

