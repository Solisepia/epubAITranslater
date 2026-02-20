from __future__ import annotations

from epub2zh_faithful.placeholder_codec import PlaceholderCounter, decode_text, encode_node_inner_xml


def test_placeholder_roundtrip() -> None:
    counter = PlaceholderCounter()
    src = "Hello <em>world</em> in 1066 and https://example.com"
    encoded = encode_node_inner_xml(src, counter)
    translated = f"你好 {encoded.source_text}"
    decoded = decode_text(translated, encoded.placeholder_map)

    assert "<em>world</em>" in decoded
    assert "1066" in decoded
    assert "https://example.com" in decoded
