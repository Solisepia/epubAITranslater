from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from epub2zh_faithful.config import AppConfig
from epub2zh_faithful.models import RunStats, Segment, SegmentType, TranslationResult
from epub2zh_faithful.pipeline import PipelineCancelled, _translate_with_cache, run_translation
from epub2zh_faithful.termbase_generator import GenerateOptions, GenerationCancelled, generate_termbase
from epub2zh_faithful.terminology import Termbase
from epub2zh_faithful.tm_store import TMStore


class DummyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def translate_segments(self, segments: list[Segment], _hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        self.calls += 1
        return [TranslationResult(id=s.id, translated_text="译文") for s in segments]

    def revise_segments(
        self,
        segments: list[Segment],
        draft_results: list[TranslationResult],
        _hits: list[dict[str, str | bool]],
    ) -> list[TranslationResult]:
        self.calls += 1
        return draft_results


def _mk_segments(n: int) -> list[Segment]:
    out: list[Segment] = []
    for i in range(n):
        out.append(
            Segment(
                id=f"S{i:09d}",
                node_task_id=f"NT_{i:06d}",
                chunk_index=0,
                segment_type=SegmentType.PARAGRAPH,
                file_path="item.xhtml",
                node_selector=f"/html/body/p[{i + 1}]",
                order_index=i + 1,
                source_lang="en",
                target_lang="zh-Hans",
                source_text=f"Segment {i}",
            )
        )
    return out


def test_translate_with_cache_cancelled_before_submit(tmp_path: Path) -> None:
    provider = DummyProvider()
    store = TMStore(str(tmp_path / "cache.sqlite"))
    cfg = AppConfig()
    cfg.segmentation.max_segments_per_batch = 1
    cfg.segmentation.max_chars_per_batch = 50

    with pytest.raises(PipelineCancelled):
        _translate_with_cache(
            segments=_mk_segments(5),
            provider=provider,
            store=store,
            termbase=Termbase([], "v1"),
            config_hash="cfg",
            prefer_revise=False,
            resume=False,
            max_concurrency=4,
            stats=RunStats(),
            config=cfg,
            should_stop_cb=lambda: True,
        )
    store.close()
    assert provider.calls == 0


def test_run_translation_returns_cancel_exit_code(tmp_path: Path) -> None:
    args = Namespace(
        input=str(tmp_path / "in.epub"),
        output=str(tmp_path / "out.epub"),
        provider="mock",
        draft_provider=None,
        revise_provider=None,
        model="mock",
        draft_model=None,
        revise_model=None,
        resume=False,
        cache=str(tmp_path / "cache.sqlite"),
        termbase=None,
        config=None,
        max_concurrency=1,
        keep_workdir=False,
    )
    code = run_translation(args, should_stop_cb=lambda: True)
    assert code == 130


def test_generate_termbase_can_be_cancelled() -> None:
    fixture = Path("tests/fixtures/fixture_basic.epub")
    with pytest.raises(GenerationCancelled):
        generate_termbase(
            input_epub=str(fixture),
            output_path="tests/out/should_not_exist.yaml",
            options=GenerateOptions(),
            should_stop_cb=lambda: True,
        )
