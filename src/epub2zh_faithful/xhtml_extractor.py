from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from .config import AppConfig
from .dom_utils import compute_xpath, element_text, extract_inner_xml, parse_xml_file
from .models import BookModel, NodeTask, SegmentType
from .placeholder_codec import PlaceholderCounter, encode_node_inner_xml, encode_plain_text
from .utils import OPS_NS, has_any_class, localname

BLOCK_WHITELIST = {
    "title",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "blockquote",
    "dd",
    "dt",
    "figcaption",
    "caption",
    "td",
    "th",
    "q",
    "cite",
}
BLACKLIST_CONTAINERS = {"code", "pre", "kbd", "samp", "var", "script", "style", "math", "annotation", "semantics"}
NO_TRANSLATE_CLASSES = {"no-translate", "notranslate", "raw", "code"}
POETRY_CLASS_RE = re.compile(r"\b(poem|poetry|verse|stanza)\b", re.IGNORECASE)


def extract_node_tasks(book: BookModel, config: AppConfig, start_order: int = 1) -> list[NodeTask]:
    root = Path(book.workspace_dir)
    tasks: list[NodeTask] = []
    order = start_order
    task_seq = 1

    for rel_path in book.xhtml_files:
        tree = parse_xml_file(str(root / rel_path))
        quote_nodes = _collect_quote_nodes(tree)
        preserve_quote_original = bool(config.quote_mode.preserve_original)
        add_quote_translation = bool(config.quote_mode.add_translation)

        for node in tree.getroot().iter():
            if not isinstance(node.tag, str):
                continue
            tag = localname(node.tag)
            if tag not in BLOCK_WHITELIST:
                continue
            if _should_skip(node):
                continue

            node_xpath = compute_xpath(node)
            is_quote_container = node_xpath in quote_nodes and tag in {"blockquote", "q", "cite"}
            if is_quote_container and preserve_quote_original and add_quote_translation:
                task = _build_quote_task(node, rel_path, node_xpath, order, task_seq)
                if task is not None:
                    tasks.append(task)
                    order += 1
                    task_seq += 1
                continue

            if is_quote_container and preserve_quote_original and not add_quote_translation:
                continue

            if _inside_quote(node, quote_nodes):
                continue

            if tag == "title" and not config.translate_titles:
                continue
            task = _build_normal_task(node, rel_path, node_xpath, order, task_seq)
            if task is None:
                continue
            tasks.append(task)
            order += 1
            task_seq += 1

    return tasks


def _build_normal_task(node: etree._Element, rel_path: str, xpath: str, order: int, seq: int) -> NodeTask | None:
    counter = PlaceholderCounter()
    try:
        encoded = encode_node_inner_xml(extract_inner_xml(node), counter)
    except etree.XMLSyntaxError:
        encoded = encode_plain_text(element_text(node), counter)

    source = encoded.source_text.strip()
    if not source:
        return None

    segment_type = _map_segment_type(node)
    poetry_line_count = None
    if _is_poetry(node):
        segment_type = SegmentType.POETRY_LINE
        poetry_line_count = _line_count(source)

    if _is_footnote_node(node):
        segment_type = SegmentType.FOOTNOTE

    return NodeTask(
        id=f"NT_{seq:06d}",
        file_path=rel_path,
        node_selector=xpath,
        segment_type=segment_type,
        source_text=source,
        placeholder_map=encoded.placeholder_map,
        order_index=order,
        poetry_line_count=poetry_line_count,
    )


def _build_quote_task(node: etree._Element, rel_path: str, xpath: str, order: int, seq: int) -> NodeTask | None:
    text = _extract_text_preserve_breaks(node).strip()
    if not text:
        return None
    counter = PlaceholderCounter()
    encoded = encode_plain_text(text, counter)

    origin = localname(node.tag)
    return NodeTask(
        id=f"NT_{seq:06d}",
        file_path=rel_path,
        node_selector=xpath,
        segment_type=SegmentType.BLOCKQUOTE_TRANSLATION,
        source_text=encoded.source_text,
        placeholder_map=encoded.placeholder_map,
        order_index=order,
        quote_origin=origin,
        quote_prefix="【译】" if origin == "blockquote" else "（译：",
    )


def _map_segment_type(node: etree._Element) -> SegmentType:
    tag = localname(node.tag)
    if tag == "title":
        return SegmentType.TITLE
    if tag.startswith("h") and tag[1:].isdigit():
        return SegmentType.HEADING
    if tag == "li":
        return SegmentType.LIST_ITEM
    if tag in {"td", "th"}:
        return SegmentType.TABLE_CELL
    return SegmentType.PARAGRAPH


def _should_skip(node: etree._Element) -> bool:
    current: etree._Element | None = node
    while current is not None:
        if not isinstance(current.tag, str):
            current = current.getparent()
            continue
        tag = localname(current.tag)
        if tag in BLACKLIST_CONTAINERS:
            return True
        if has_any_class(current.get("class"), NO_TRANSLATE_CLASSES):
            return True
        if (current.get("translate") or "").lower() == "no":
            return True
        current = current.getparent()
    return False


def _collect_quote_nodes(tree: etree._ElementTree) -> set[str]:
    xpaths: set[str] = set()
    for node in tree.xpath("//*[local-name()='blockquote' or local-name()='q' or local-name()='cite']"):
        if isinstance(node, etree._Element):
            xpaths.add(compute_xpath(node))
    return xpaths


def _inside_quote(node: etree._Element, quote_nodes: set[str]) -> bool:
    current = node.getparent()
    while current is not None:
        if compute_xpath(current) in quote_nodes:
            return True
        current = current.getparent()
    return False


def _extract_text_preserve_breaks(node: etree._Element) -> str:
    parts: list[str] = []

    def walk(elem: etree._Element) -> None:
        if elem.text:
            parts.append(elem.text)
        for child in elem:
            if localname(child.tag) == "br":
                parts.append("\n")
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(node)
    return "".join(parts)


def _is_poetry(node: etree._Element) -> bool:
    classes = node.get("class") or ""
    return bool(POETRY_CLASS_RE.search(classes))


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _is_footnote_node(node: etree._Element) -> bool:
    current: etree._Element | None = node
    while current is not None:
        etype = current.attrib.get("epub:type") or current.attrib.get(f"{{{OPS_NS}}}type") or ""
        if "footnote" in etype.split():
            return True
        current = current.getparent()
    return False
