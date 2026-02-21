from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
OUT = ROOT / "tests" / "out"
TEST_CONFIG = FIX / "config.test.yaml"

FIXTURE_NAMES = [
    "fixture_basic",
    "fixture_footnotes",
    "fixture_quotes",
    "fixture_poetry",
    "fixture_tables",
    "fixture_code",
]


def _run_cli(
    input_epub: Path,
    output_epub: Path,
    cache_db: Path,
    resume: bool = False,
    config_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        sys.executable,
        "-m",
        "epub2zh_faithful.cli",
        str(input_epub),
        "-o",
        str(output_epub),
        "--provider",
        "mock",
        "--revise-provider",
        "none",
        "--cache",
        str(cache_db),
        "--config",
        str(config_path or TEST_CONFIG),
        "--max-concurrency",
        "2",
    ]
    if resume:
        cmd.append("--resume")
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _read_xhtml_from_epub(epub_path: Path) -> list[tuple[str, etree._ElementTree]]:
    trees: list[tuple[str, etree._ElementTree]] = []
    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    with zipfile.ZipFile(epub_path, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xhtml"):
                continue
            data = zf.read(name)
            root = etree.fromstring(data, parser=parser)
            trees.append((name, etree.ElementTree(root)))
    return trees


def _collect_ids_hrefs(epub_path: Path) -> tuple[set[str], set[str], int]:
    ids: set[str] = set()
    hrefs: set[str] = set()
    quote_count = 0

    for _, tree in _read_xhtml_from_epub(epub_path):
        for elem in tree.getroot().iter():
            if not isinstance(elem.tag, str):
                continue
            node_id = elem.get("id")
            if node_id:
                ids.add(node_id)
            href = elem.get("href")
            if href:
                hrefs.add(href)
            classes = (elem.get("class") or "").split()
            if "ai-quote-translation" in classes:
                quote_count += 1

    return ids, hrefs, quote_count


def _collect_code_texts(epub_path: Path) -> tuple[list[str], list[str]]:
    pre_texts: list[str] = []
    code_texts: list[str] = []
    for _, tree in _read_xhtml_from_epub(epub_path):
        for elem in tree.xpath("//*[local-name()='pre']"):
            if isinstance(elem, etree._Element):
                pre_texts.append("".join(elem.itertext()))
        for elem in tree.xpath("//*[local-name()='code']"):
            if isinstance(elem, etree._Element):
                code_texts.append("".join(elem.itertext()))
    return pre_texts, code_texts


def _text_by_id(epub_path: Path, wanted_id: str) -> str | None:
    for _, tree in _read_xhtml_from_epub(epub_path):
        nodes = tree.xpath(f"//*[@id='{wanted_id}']")
        if nodes and isinstance(nodes[0], etree._Element):
            return "".join(nodes[0].itertext())
    return None


def test_fixture_translation_end_to_end() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    for name in FIXTURE_NAMES:
        input_epub = FIX / f"{name}.epub"
        expected_path = FIX / f"{name}.expected_checks.json"
        output_epub = OUT / f"{name}.out.epub"
        cache_db = OUT / f"{name}.cache.sqlite"

        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        first = _run_cli(input_epub, output_epub, cache_db, resume=False)
        assert first.returncode == 0, f"{name} failed first run: {first.stdout}\n{first.stderr}"

        ids, hrefs, quote_count = _collect_ids_hrefs(output_epub)
        for item in expected["must_keep_ids"]:
            assert item in ids, f"{name}: missing id {item}"
        for href in expected["must_keep_hrefs"]:
            assert href in hrefs, f"{name}: missing href {href}"
        assert quote_count == expected["quote_translation_nodes"], f"{name}: quote node mismatch"

        conn = sqlite3.connect(cache_db)
        before_rows = conn.execute("select count(*) from translations").fetchone()[0]
        conn.close()

        second = _run_cli(input_epub, output_epub, cache_db, resume=True)
        assert second.returncode == 0, f"{name} failed resume run: {second.stdout}\n{second.stderr}"

        conn = sqlite3.connect(cache_db)
        after_rows = conn.execute("select count(*) from translations").fetchone()[0]
        conn.close()
        assert before_rows == after_rows, f"{name}: cache row count changed on resume"


def test_code_fixture_preserves_code_blocks() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_epub = FIX / "fixture_code.epub"
    output_epub = OUT / "fixture_code.verify.epub"
    cache_db = OUT / "fixture_code.verify.sqlite"

    first = _run_cli(input_epub, output_epub, cache_db, resume=False)
    assert first.returncode == 0, f"code fixture run failed: {first.stdout}\n{first.stderr}"

    in_pre, in_code = _collect_code_texts(input_epub)
    out_pre, out_code = _collect_code_texts(output_epub)
    assert in_pre == out_pre
    assert in_code == out_code


def test_inline_span_text_gets_translated() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_epub = FIX / "fixture_basic.epub"
    output_epub = OUT / "fixture_basic.inline_check.epub"
    cache_db = OUT / "fixture_basic.inline_check.sqlite"

    run = _run_cli(input_epub, output_epub, cache_db, resume=False)
    assert run.returncode == 0, f"inline fixture run failed: {run.stdout}\n{run.stderr}"

    src = _text_by_id(input_epub, "sp1")
    dst = _text_by_id(output_epub, "sp1")
    assert src is not None and dst is not None
    assert dst != src
