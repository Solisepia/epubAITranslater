from __future__ import annotations

from pathlib import Path

from lxml import etree

from .dom_utils import get_one_by_xpath, parse_xml_file, set_inner_xml, write_xml_file
from .models import NodeTask, SegmentType
from .placeholder_codec import decode_text
from .utils import localname


def apply_node_translations(workdir: str, node_tasks: list[NodeTask], node_translations: dict[str, str], quote_class: str) -> None:
    by_file: dict[str, list[NodeTask]] = {}
    for task in node_tasks:
        if task.id not in node_translations:
            continue
        by_file.setdefault(task.file_path, []).append(task)

    root = Path(workdir)
    for rel, tasks in by_file.items():
        full = root / rel
        tree = parse_xml_file(str(full))

        refs: dict[str, etree._Element] = {}
        for task in tasks:
            node = get_one_by_xpath(tree, task.node_selector)
            if node is not None:
                refs[task.id] = node

        # In-place replacements first, quote insertions afterwards to avoid xpath drift.
        for task in tasks:
            if task.segment_type == SegmentType.BLOCKQUOTE_TRANSLATION:
                continue
            node = refs.get(task.id)
            if node is None:
                continue
            translated = decode_text(node_translations[task.id], task.placeholder_map)
            set_inner_xml(node, translated)

        quote_tasks = [task for task in tasks if task.segment_type == SegmentType.BLOCKQUOTE_TRANSLATION]
        quote_tasks.sort(key=lambda t: 1 if (t.quote_origin or "blockquote") == "blockquote" else 0)

        for task in quote_tasks:
            node = get_one_by_xpath(tree, task.node_selector)
            if node is None:
                continue
            translated = decode_text(node_translations[task.id], task.placeholder_map).strip()
            _insert_quote_translation(node, translated, quote_class, task.quote_origin or "blockquote")

        write_xml_file(str(full), tree)


def _insert_quote_translation(origin: etree._Element, text: str, quote_class: str, quote_origin: str) -> None:
    parent = origin.getparent()
    if parent is None:
        return
    ns_uri = etree.QName(origin.tag).namespace

    if quote_origin == "blockquote":
        new_tag = "p"
        rendered = f"【译】{text}"
    else:
        new_tag = "span"
        rendered = f"（译：{text}）"

    if ns_uri:
        node = etree.Element(f"{{{ns_uri}}}{new_tag}")
    else:
        node = etree.Element(new_tag)

    node.set("class", quote_class)
    node.set("data-ai-origin", quote_origin)
    node.text = rendered

    idx = parent.index(origin)
    parent.insert(idx + 1, node)
