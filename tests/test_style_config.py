from __future__ import annotations

import textwrap

from epub2zh_faithful.config import DEFAULT_STYLE, STYLE_OPTIONS, load_config
from epub2zh_faithful.llm_client import _build_revise_payload, _build_translate_payload
from epub2zh_faithful.models import Segment, SegmentType, TranslationResult


def _mk_segment() -> Segment:
    return Segment(
        id="S000000001",
        node_task_id="NT_000001",
        chunk_index=0,
        segment_type=SegmentType.PARAGRAPH,
        file_path="item/xhtml/p-001.xhtml",
        node_selector="/*[local-name()='html'][1]",
        order_index=1,
        source_lang="en",
        target_lang="zh-Hans",
        source_text="Hello world.",
    )


def test_load_config_normalizes_style_and_ignores_removed_fields(tmp_path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        textwrap.dedent(
            """
            style: literary_cn
            poetry_mode: line_by_line
            code_mode: skip
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_file))
    assert cfg.style == "literary_cn"
    assert "literary_cn" in STYLE_OPTIONS
    assert not hasattr(cfg, "poetry_mode")
    assert not hasattr(cfg, "code_mode")


def test_load_config_invalid_style_falls_back_to_default(tmp_path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("style: not_a_style", encoding="utf-8")
    cfg = load_config(str(cfg_file))
    assert cfg.style == DEFAULT_STYLE


def test_payload_style_guide_follows_style_enum() -> None:
    seg = _mk_segment()
    draft = [TranslationResult(id=seg.id, translated_text="你好，世界。")]

    t = _build_translate_payload([seg], [], "concise_cn")
    r = _build_revise_payload([seg], draft, [], "concise_cn")

    assert t["style_guide"] == "concise_zh_hans"
    assert r["style_guide"] == "concise_revision_keep_meaning_and_placeholders"

