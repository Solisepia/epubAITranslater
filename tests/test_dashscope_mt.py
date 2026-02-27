from __future__ import annotations

from argparse import Namespace

from epub2zh_faithful.config import AppConfig
from epub2zh_faithful.llm_client import DashScopeProvider, ProviderSettings
from epub2zh_faithful.models import Segment, SegmentType, TranslationResult
from epub2zh_faithful.pipeline import run_translation


def _make_segment() -> Segment:
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


def test_dashscope_mt_revise_payload_uses_draft_results(monkeypatch) -> None:
    seg = _make_segment()
    draft = [TranslationResult(id=seg.id, translated_text="草稿译文")]
    provider = DashScopeProvider(api_key="dummy", model="qwen-mt-plus", config=AppConfig())

    captured_payloads: list[dict] = []

    def fake_call(payload: dict, expected_ids: list[str], strict_json: bool) -> list[TranslationResult]:
        captured_payloads.append(payload)
        return [TranslationResult(id=expected_ids[0], translated_text="修订译文")]

    monkeypatch.setattr(provider, "_call_with_retry", fake_call)
    out = provider.revise_segments([seg], draft, [])
    assert out[0].translated_text == "修订译文"
    assert captured_payloads[0]["segments"][0]["draft"] == "草稿译文"


def test_pipeline_dashscope_mt_defaults_to_no_revise(monkeypatch, tmp_path) -> None:
    captured: dict[str, ProviderSettings] = {}

    class DummyStore:
        def __init__(self, _path: str) -> None:
            pass

        def create_run(self, *args, **kwargs) -> None:
            return

        def record_error(self, *args, **kwargs) -> None:
            return

        def commit(self) -> None:
            return

        def close(self) -> None:
            return

    class DummyTermbase:
        @staticmethod
        def load(_path: str | None) -> "DummyTermbase":
            return DummyTermbase()

        def cache_fingerprint(self) -> str:
            return "dummy"

    def fake_build(settings: ProviderSettings, _config: AppConfig):
        captured["settings"] = settings
        raise RuntimeError("stop after provider settings capture")

    monkeypatch.setattr("epub2zh_faithful.pipeline.TMStore", DummyStore)
    monkeypatch.setattr("epub2zh_faithful.pipeline.Termbase", DummyTermbase)
    monkeypatch.setattr("epub2zh_faithful.pipeline.LLMClientFactory.build", fake_build)

    args = Namespace(
        input=str(tmp_path / "in.epub"),
        output=str(tmp_path / "out.epub"),
        provider="dashscope-mt",
        draft_provider=None,
        revise_provider=None,
        model="qwen-mt-plus",
        draft_model=None,
        revise_model=None,
        resume=False,
        cache=str(tmp_path / "cache.sqlite"),
        termbase=None,
        config=None,
        max_concurrency=1,
        keep_workdir=False,
    )

    code = run_translation(args)
    assert code == 1
    assert captured["settings"].provider == "dashscope-mt"
    assert captured["settings"].draft_provider == "dashscope-mt"
    assert captured["settings"].revise_provider == "none"
