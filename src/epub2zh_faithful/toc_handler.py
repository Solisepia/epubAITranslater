from __future__ import annotations

from pathlib import Path

from lxml import etree

from .dom_utils import compute_xpath, element_text, get_one_by_xpath, parse_xml_file, set_inner_xml, write_xml_file
from .models import NodeTask, SegmentType, TocItem, TocSnapshot
from .placeholder_codec import PlaceholderCounter, decode_text, encode_plain_text
from .utils import OPS_NS, localname


def extract_toc_items(workdir: str, nav_path: str | None, ncx_path: str | None) -> list[TocItem]:
    items: list[TocItem] = []
    root = Path(workdir)

    if nav_path:
        tree = parse_xml_file(str(root / nav_path))
        for nav in tree.getroot().iter():
            if localname(nav.tag) != "nav":
                continue
            epub_type = _epub_type(nav)
            if "toc" not in epub_type.split():
                continue
            for anchor in nav.iter():
                if localname(anchor.tag) != "a":
                    continue
                href = anchor.get("href", "")
                label = element_text(anchor).strip()
                if not href or not label:
                    continue
                items.append(TocItem(href=href, label_text=label, file_path=nav_path, node_selector=compute_xpath(anchor), kind="nav"))

    if ncx_path:
        tree = parse_xml_file(str(root / ncx_path))
        for text_node in tree.xpath("//*[local-name()='navPoint']/*[local-name()='navLabel']/*[local-name()='text']"):
            if not isinstance(text_node, etree._Element):
                continue
            nav_point = text_node.getparent().getparent() if text_node.getparent() is not None else None
            href = ""
            if nav_point is not None:
                content_nodes = nav_point.xpath("./*[local-name()='content']")
                if content_nodes and isinstance(content_nodes[0], etree._Element):
                    href = content_nodes[0].get("src", "")
            label = (text_node.text or "").strip()
            if not label:
                continue
            items.append(TocItem(href=href, label_text=label, file_path=ncx_path, node_selector=compute_xpath(text_node), kind="ncx"))

    return items


def toc_items_to_node_tasks(items: list[TocItem], start_order: int) -> list[NodeTask]:
    tasks: list[NodeTask] = []
    order = start_order
    for idx, item in enumerate(items, start=1):
        counter = PlaceholderCounter()
        encoded = encode_plain_text(item.label_text, counter)
        tasks.append(
            NodeTask(
                id=f"NT_TOC_{idx:06d}",
                file_path=item.file_path,
                node_selector=item.node_selector,
                segment_type=SegmentType.TOC,
                source_text=encoded.source_text,
                placeholder_map=encoded.placeholder_map,
                order_index=order,
            )
        )
        order += 1
    return tasks


def apply_toc_translations(workdir: str, task_to_translation: dict[str, str], tasks: list[NodeTask]) -> None:
    by_file: dict[str, list[NodeTask]] = {}
    for task in tasks:
        by_file.setdefault(task.file_path, []).append(task)

    root = Path(workdir)
    for rel_path, file_tasks in by_file.items():
        full_path = root / rel_path
        tree = parse_xml_file(str(full_path))
        for task in file_tasks:
            translated = task_to_translation.get(task.id)
            if translated is None:
                continue
            restored = decode_text(translated, task.placeholder_map)
            node = get_one_by_xpath(tree, task.node_selector)
            if node is None:
                continue
            if localname(node.tag) == "text":
                node.text = restored
            else:
                set_inner_xml(node, restored)
        write_xml_file(str(full_path), tree)


def snapshot_toc_hrefs(workdir: str, nav_path: str | None, ncx_path: str | None) -> TocSnapshot:
    hrefs: list[str] = []
    root = Path(workdir)

    if nav_path:
        tree = parse_xml_file(str(root / nav_path))
        for anchor in tree.xpath("//*[local-name()='nav']//*[local-name()='a']"):
            if isinstance(anchor, etree._Element) and anchor.get("href"):
                hrefs.append(anchor.get("href", ""))

    if ncx_path:
        tree = parse_xml_file(str(root / ncx_path))
        for content in tree.xpath("//*[local-name()='navPoint']/*[local-name()='content']"):
            if isinstance(content, etree._Element) and content.get("src"):
                hrefs.append(content.get("src", ""))

    return TocSnapshot(hrefs=hrefs)


def _epub_type(node: etree._Element) -> str:
    if "epub:type" in node.attrib:
        return node.attrib.get("epub:type", "")
    ns_key = f"{{{OPS_NS}}}type"
    return node.attrib.get(ns_key, "")
