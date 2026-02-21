from __future__ import annotations

from pathlib import Path

import yaml

from epub2zh_faithful.termbase_generator import GenerateOptions, generate_termbase
from epub2zh_faithful.terminology import Term, Termbase, format_term_target, has_cjk_left


def test_generate_termbase_from_fixture(tmp_path: Path) -> None:
    input_epub = Path("tests/fixtures/fixture_basic.epub")
    output = tmp_path / "generated_termbase.yaml"

    stats = generate_termbase(
        input_epub=str(input_epub),
        output_path=str(output),
        options=GenerateOptions(min_freq=1, max_terms=50, include_single_word=True, merge_existing=False),
    )

    assert output.exists()
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert isinstance(payload.get("terms"), list)
    assert payload["terms"]
    assert stats["generated_terms"] > 0

    sources = {item.get("source", "") for item in payload["terms"]}
    assert "Norman Conquest" in sources


def test_generate_termbase_fill_empty_targets_with_mock(tmp_path: Path) -> None:
    input_epub = Path("tests/fixtures/fixture_basic.epub")
    output = tmp_path / "generated_termbase_filled.yaml"

    stats = generate_termbase(
        input_epub=str(input_epub),
        output_path=str(output),
        options=GenerateOptions(
            min_freq=1,
            max_terms=20,
            include_single_word=True,
            merge_existing=False,
            fill_empty_targets=True,
            fill_provider="mock",
            fill_model="gpt-5-mini",
            fill_batch_size=10,
        ),
    )

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert isinstance(payload.get("terms"), list)
    assert payload["terms"]
    assert stats["filled_targets"] > 0
    assert all(str(item.get("target", "")).strip() for item in payload["terms"])
    for item in payload["terms"]:
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        assert target.endswith(f"（{source}）")


def test_term_target_default_format_is_translation_then_source() -> None:
    raw = format_term_target("Emerald Tablet", "翠玉石板")
    assert raw == "翠玉石板（Emerald Tablet）"

    already = format_term_target("Emerald Tablet", "翠玉石板（Emerald Tablet）")
    assert already == "翠玉石板（Emerald Tablet）"

    tb = Termbase([Term(source="One Mind", target="一心")], version_id="1")
    assert tb.terms[0].target == "一心（One Mind）"
    assert has_cjk_left("One Mind", tb.terms[0].target)
    assert not has_cjk_left("Emerald Tablet", "Emerald Tablet（Emerald Tablet）")


def test_generate_termbase_clears_non_cjk_left_targets(tmp_path: Path) -> None:
    input_epub = Path("tests/fixtures/fixture_basic.epub")
    output = tmp_path / "generated_termbase_existing.yaml"
    output.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "terms": [
                    {"source": "Emerald Tablet", "target": "Emerald Tablet", "force": False, "note": "manual"},
                    {"source": "One Mind", "target": "一心（One Mind）", "force": False, "note": "manual"},
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    stats = generate_termbase(
        input_epub=str(input_epub),
        output_path=str(output),
        options=GenerateOptions(min_freq=999, max_terms=10, include_single_word=False, merge_existing=True, fill_empty_targets=False),
    )

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    terms = {item["source"]: item for item in payload["terms"]}
    assert terms["Emerald Tablet"]["target"] == ""
    assert terms["One Mind"]["target"] == "一心（One Mind）"
    assert stats["cleared_non_cjk_targets"] >= 1
