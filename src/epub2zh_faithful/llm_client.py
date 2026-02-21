from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

import requests

from .config import AppConfig
from .models import Segment, TranslationResult

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "translated_text": {"type": "string"},
                },
                "required": ["id", "translated_text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def translate_segments(self, segments: list[Segment], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        ...

    def revise_segments(self, segments: list[Segment], draft_results: list[TranslationResult], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        ...


@dataclass(slots=True)
class ProviderSettings:
    provider: str
    draft_provider: str
    revise_provider: str
    model: str
    draft_model: str | None
    revise_model: str | None


class LLMClientFactory:
    @staticmethod
    def build(settings: ProviderSettings, config: AppConfig) -> Provider:
        if settings.provider == "mixed":
            draft_name = settings.draft_provider
            revise_name = settings.revise_provider
            draft = _single_provider(draft_name, settings.draft_model or settings.model, config)
            revise = None if revise_name == "none" else _single_provider(revise_name, settings.revise_model or settings.model, config)
            return MixedProvider(draft, revise)
        if settings.provider == "mock":
            return MockProvider()
        single = _single_provider(settings.provider, settings.model, config)
        if settings.revise_provider == "none":
            return MixedProvider(single, None)
        revise = _single_provider(settings.revise_provider, settings.revise_model or settings.model, config)
        return MixedProvider(single, revise)


def _single_provider(name: str, model: str, config: AppConfig) -> Provider:
    if name == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ProviderError("OPENAI_API_KEY is required for provider=openai")
        return OpenAIProvider(api_key=key, model=model, config=config)
    if name == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise ProviderError("DEEPSEEK_API_KEY is required for provider=deepseek")
        return DeepSeekProvider(api_key=key, model=model, config=config)
    if name == "mock":
        return MockProvider()
    raise ProviderError(f"Unsupported provider: {name}")


class MixedProvider:
    def __init__(self, draft_provider: Provider, revise_provider: Provider | None) -> None:
        self.draft_provider = draft_provider
        self.revise_provider = revise_provider

    def translate_segments(self, segments: list[Segment], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        return self.draft_provider.translate_segments(segments, termbase_hits)

    def revise_segments(self, segments: list[Segment], draft_results: list[TranslationResult], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        if not self.revise_provider:
            return draft_results
        return self.revise_provider.revise_segments(segments, draft_results, termbase_hits)


class BaseChatProvider:
    def __init__(self, api_key: str, model: str, config: AppConfig, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.config = config
        self.base_url = base_url.rstrip("/")

    def translate_segments(self, segments: list[Segment], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        payload = _build_translate_payload(segments, termbase_hits)
        return self._call_with_retry(payload, expected_ids=[s.id for s in segments], strict_json=True)

    def revise_segments(self, segments: list[Segment], draft_results: list[TranslationResult], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        payload = _build_revise_payload(segments, draft_results, termbase_hits)
        return self._call_with_retry(payload, expected_ids=[s.id for s in segments], strict_json=True)

    def _call_with_retry(self, payload: dict, expected_ids: list[str], strict_json: bool) -> list[TranslationResult]:
        attempts = self.config.llm.max_retries
        backoff = self.config.llm.retry_backoff_seconds
        error_message = ""
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                return self._call_once(payload, expected_ids, strict_json=strict_json, error_feedback=error_message)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                error_message = str(exc)
                sleep_s = backoff[min(i, len(backoff) - 1)] if backoff else 1
                time.sleep(sleep_s)

        # Fallback to single-segment mode.
        if len(expected_ids) > 1:
            out: list[TranslationResult] = []
            for seg in payload["segments"]:
                single_payload = dict(payload)
                single_payload["segments"] = [seg]
                out.extend(self._call_with_retry(single_payload, [seg["id"]], strict_json=True))
            return out

        if last_exc:
            raise ProviderError(f"Provider call failed after retries: {last_exc}") from last_exc
        raise ProviderError("Provider call failed after retries")

    def _call_once(self, payload: dict, expected_ids: list[str], strict_json: bool, error_feedback: str = "") -> list[TranslationResult]:
        raise NotImplementedError


class OpenAIProvider(BaseChatProvider):
    def __init__(self, api_key: str, model: str, config: AppConfig) -> None:
        super().__init__(api_key=api_key, model=model, config=config, base_url="https://api.openai.com/v1")

    def _call_once(self, payload: dict, expected_ids: list[str], strict_json: bool, error_feedback: str = "") -> list[TranslationResult]:
        system, user = _build_messages(payload, error_feedback)
        req_base = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "translation_response",
                    "strict": True,
                    "schema": JSON_SCHEMA,
                },
            },
        }
        req_with_temperature = dict(req_base)
        req_with_temperature["temperature"] = self.config.llm.temperature

        # Some models only support default temperature. Fallback automatically.
        resp = self._post(req_with_temperature)
        if resp.status_code == 400 and _is_temperature_unsupported(resp.text):
            resp = self._post(req_base)

        if resp.status_code >= 300:
            raise ProviderError(f"OpenAI HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_results(content, expected_ids)

    def _post(self, req: dict) -> requests.Response:
        return requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=req,
            timeout=self.config.llm.timeout_seconds,
        )


class DeepSeekProvider(BaseChatProvider):
    MAX_SEGMENTS_PER_CALL = 8

    def __init__(self, api_key: str, model: str, config: AppConfig) -> None:
        super().__init__(api_key=api_key, model=model, config=config, base_url="https://api.deepseek.com/v1")

    def translate_segments(self, segments: list[Segment], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        if len(segments) <= self.MAX_SEGMENTS_PER_CALL:
            return super().translate_segments(segments, termbase_hits)

        out: list[TranslationResult] = []
        for chunk in _chunked(segments, self.MAX_SEGMENTS_PER_CALL):
            out.extend(super().translate_segments(chunk, termbase_hits))
        return out

    def revise_segments(
        self,
        segments: list[Segment],
        draft_results: list[TranslationResult],
        termbase_hits: list[dict[str, str | bool]],
    ) -> list[TranslationResult]:
        if len(segments) <= self.MAX_SEGMENTS_PER_CALL:
            return super().revise_segments(segments, draft_results, termbase_hits)

        draft_map = {item.id: item for item in draft_results}
        out: list[TranslationResult] = []
        for chunk in _chunked(segments, self.MAX_SEGMENTS_PER_CALL):
            chunk_drafts = [draft_map[s.id] for s in chunk if s.id in draft_map]
            out.extend(super().revise_segments(chunk, chunk_drafts, termbase_hits))
        return out

    def _call_once(self, payload: dict, expected_ids: list[str], strict_json: bool, error_feedback: str = "") -> list[TranslationResult]:
        system, user = _build_messages(payload, error_feedback)
        req = {
            "model": self.model,
            "temperature": self.config.llm.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=req,
            timeout=self.config.llm.timeout_seconds,
        )
        if resp.status_code >= 300:
            raise ProviderError(f"DeepSeek HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_results(content, expected_ids)


class MockProvider:
    def translate_segments(self, segments: list[Segment], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        return [TranslationResult(id=s.id, translated_text=f"[中]{s.source_text}") for s in segments]

    def revise_segments(self, segments: list[Segment], draft_results: list[TranslationResult], termbase_hits: list[dict[str, str | bool]]) -> list[TranslationResult]:
        return draft_results


def _build_messages(payload: dict, error_feedback: str) -> tuple[str, str]:
    system = (
        "你是直译忠实译者。仅输出 JSON，不要输出任何解释。"
        "不增译不漏译。占位符必须原样保留，数量一致，不可改动。"
        "除占位符与术语括号中的原文外，输出必须是简体中文，不得整句照抄原文。"
        "命中术语表时优先使用指定译法；若 target 含“译文（原文）”结构，必须完整保留该结构。"
        "命中术语表 force=true 时必须使用指定译法。"
    )
    if error_feedback:
        system += f" 上一次输出错误：{error_feedback}。请修正并仅输出 JSON。"
    user = json.dumps(payload, ensure_ascii=False)
    return system, user


def _build_translate_payload(segments: list[Segment], termbase_hits: list[dict[str, str | bool]]) -> dict:
    return {
        "task": "draft_translate",
        "style_guide": "faithful_literal_zh_hans",
        "termbase_hits": termbase_hits,
        "segments": [
            {
                "id": s.id,
                "type": s.segment_type.value,
                "text": s.source_text,
                "constraints": {
                    "do_not_translate": s.placeholders,
                },
            }
            for s in segments
        ],
        "output_schema": {"results": [{"id": "string", "translated_text": "string"}]},
    }


def _build_revise_payload(segments: list[Segment], draft_results: list[TranslationResult], termbase_hits: list[dict[str, str | bool]]) -> dict:
    draft_map = {x.id: x.translated_text for x in draft_results}
    return {
        "task": "revise_translation",
        "style_guide": "light_revision_keep_meaning_and_placeholders",
        "termbase_hits": termbase_hits,
        "segments": [
            {
                "id": s.id,
                "source": s.source_text,
                "draft": draft_map.get(s.id, ""),
                "constraints": {
                    "do_not_change_placeholders": s.placeholders,
                    "do_not_change_numbers": True,
                },
            }
            for s in segments
        ],
        "output_schema": {"results": [{"id": "string", "translated_text": "string"}]},
    }


def _parse_results(content: str, expected_ids: list[str]) -> list[TranslationResult]:
    parsed = _load_json(content)
    results = parsed.get("results")
    if not isinstance(results, list):
        raise ProviderError("JSON schema mismatch: results is not a list")

    out: list[TranslationResult] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            raise ProviderError("JSON schema mismatch: result item must be object")
        sid = str(item.get("id", ""))
        text = item.get("translated_text")
        if not sid or not isinstance(text, str):
            raise ProviderError("JSON schema mismatch: id/translated_text missing")
        if sid in seen:
            raise ProviderError(f"Duplicate id in results: {sid}")
        seen.add(sid)
        out.append(TranslationResult(id=sid, translated_text=text))

    if set(expected_ids) != seen:
        raise ProviderError("Result ids mismatch with input segments")
    return out


def _load_json(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = raw.removesuffix("```").strip()
    return json.loads(raw)


def _is_temperature_unsupported(response_text: str) -> bool:
    lower = response_text.lower()
    return "temperature" in lower and "unsupported" in lower


def _chunked(items: list[Segment], size: int) -> list[list[Segment]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
