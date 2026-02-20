from __future__ import annotations

from pathlib import Path

import yaml

from epub2zh_faithful.termbase_generator import GenerateOptions, generate_termbase


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
