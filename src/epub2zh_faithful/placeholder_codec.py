from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from lxml import etree

from .utils import localname

INLINE_TAGS = {"a", "em", "strong", "i", "b", "sup", "sub", "span", "br", "img", "q", "cite"}
PLACEHOLDER_TOKEN_RE = re.compile(r"(⟦PH:\d{6}⟧)")
URL_RE = re.compile(r"(?:https?://\S+|mailto:\S+)")
NUMBER_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:st|nd|rd|th)?\b|\b\d+\b")
ROMAN_RE = re.compile(r"\b[IVXLCDM]{2,}\b")
ABBR_RE = re.compile(r"\b(?:c\.|fl\.|r\.)")


@dataclass(slots=True)
class EncodedContent:
    source_text: str
    placeholder_map: dict[str, str]

    @property
    def placeholders(self) -> list[str]:
        return list(self.placeholder_map.keys())


class PlaceholderCounter:
    def __init__(self, start: int = 1) -> None:
        self.value = start

    def next(self) -> str:
        token = f"⟦PH:{self.value:06d}⟧"
        self.value += 1
        return token


def extract_inner_xml(node: etree._Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        parts.append(etree.tostring(child, encoding="unicode"))
    return "".join(parts)


def encode_node_inner_xml(inner_xml: str, counter: PlaceholderCounter) -> EncodedContent:
    placeholder_map: dict[str, str] = {}
    wrapped = etree.fromstring(f"<root>{inner_xml}</root>")
    _protect_inline_nodes(wrapped, placeholder_map, counter)
    text = "".join(wrapped.itertext())
    text = _protect_literals(text, placeholder_map, counter)
    return EncodedContent(source_text=text, placeholder_map=placeholder_map)


def encode_plain_text(text: str, counter: PlaceholderCounter) -> EncodedContent:
    placeholder_map: dict[str, str] = {}
    return EncodedContent(source_text=_protect_literals(text, placeholder_map, counter), placeholder_map=placeholder_map)


def decode_text(translated_text: str, placeholder_map: dict[str, str]) -> str:
    decoded = translated_text
    for key in sorted(placeholder_map.keys(), key=len, reverse=True):
        decoded = decoded.replace(key, placeholder_map[key])
    return decoded


def placeholder_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in PLACEHOLDER_TOKEN_RE.findall(text):
        counts[token] = counts.get(token, 0) + 1
    return counts


def split_text_preserving_placeholders(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text
    sentence_sep = re.compile(r"(?<=[。！？.!?;；:：])\s+")

    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        split_point = _find_split_point(window, sentence_sep)
        if split_point <= 0:
            split_point = max_chars
        chunk = remaining[:split_point].strip()
        if not chunk:
            chunk = remaining[:max_chars]
            split_point = max_chars
        chunks.append(chunk)
        remaining = remaining[split_point:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _find_split_point(window: str, sentence_sep: re.Pattern[str]) -> int:
    candidates = [m.start() for m in sentence_sep.finditer(window)]
    if candidates:
        return candidates[-1]
    for mark in [" ", "，", ",", "；", ";", "。", "."]:
        idx = window.rfind(mark)
        if idx > 0:
            return idx + 1
    return -1


def _protect_inline_nodes(parent: etree._Element, placeholder_map: dict[str, str], counter: PlaceholderCounter) -> None:
    for child in list(parent):
        name = localname(child.tag)
        if name in INLINE_TAGS:
            token = counter.next()
            serialized = etree.tostring(child, encoding="unicode", with_tail=False)
            placeholder_map[token] = serialized
            _replace_child_with_token(parent, child, token)
        else:
            _protect_inline_nodes(child, placeholder_map, counter)


def _replace_child_with_token(parent: etree._Element, child: etree._Element, token: str) -> None:
    idx = parent.index(child)
    tail = child.tail or ""
    if idx == 0:
        parent.text = (parent.text or "") + token + tail
    else:
        prev = parent[idx - 1]
        prev.tail = (prev.tail or "") + token + tail
    parent.remove(child)


def _protect_literals(text: str, placeholder_map: dict[str, str], counter: PlaceholderCounter) -> str:
    text = _replace_non_placeholder(text, URL_RE, lambda x: _to_placeholder(x, placeholder_map, counter))
    text = _replace_non_placeholder(text, NUMBER_RE, lambda x: _to_placeholder(x, placeholder_map, counter))
    text = _replace_non_placeholder(text, ROMAN_RE, lambda x: _to_placeholder(x, placeholder_map, counter))
    text = _replace_non_placeholder(text, ABBR_RE, lambda x: _to_placeholder(x, placeholder_map, counter))
    return text


def _replace_non_placeholder(text: str, pattern: re.Pattern[str], repl: Callable[[str], str]) -> str:
    parts = PLACEHOLDER_TOKEN_RE.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = pattern.sub(lambda m: repl(m.group(0)), parts[i])
    return "".join(parts)


def _to_placeholder(raw: str, placeholder_map: dict[str, str], counter: PlaceholderCounter) -> str:
    token = counter.next()
    placeholder_map[token] = raw
    return token
