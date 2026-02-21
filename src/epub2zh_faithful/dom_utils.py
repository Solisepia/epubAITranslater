from __future__ import annotations

from pathlib import Path

from lxml import etree

from .utils import localname


def parse_xml_file(path: str) -> etree._ElementTree:
    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    return etree.parse(path, parser)


def write_xml_file(path: str, tree: etree._ElementTree) -> None:
    Path(path).write_bytes(
        etree.tostring(
            tree,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False,
        )
    )


def compute_xpath(node: etree._Element) -> str:
    steps: list[str] = []
    current = node
    while current is not None:
        parent = current.getparent()
        name = localname(current.tag)
        if parent is None:
            steps.append(f"/*[local-name()='{name}'][1]")
            break
        same = [c for c in parent if localname(c.tag) == name]
        idx = same.index(current) + 1
        steps.append(f"/*[local-name()='{name}'][{idx}]")
        current = parent
    return "".join(reversed(steps))


def get_one_by_xpath(tree: etree._ElementTree, xpath: str) -> etree._Element | None:
    nodes = tree.xpath(xpath)
    if not nodes:
        return None
    first = nodes[0]
    if isinstance(first, etree._Element):
        return first
    return None


def extract_inner_xml(node: etree._Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        parts.append(etree.tostring(child, encoding="unicode"))
    return "".join(parts)


def set_inner_xml(node: etree._Element, inner_xml: str) -> None:
    for child in list(node):
        node.remove(child)
    node.text = None

    try:
        wrapped = etree.fromstring(f"<root>{inner_xml}</root>")
    except etree.XMLSyntaxError:
        # Model output may contain plain-text '&' or other unescaped chars.
        # In that case treat the whole value as text instead of XML fragment.
        node.text = inner_xml
        return

    node.text = wrapped.text
    for child in list(wrapped):
        wrapped.remove(child)
        node.append(child)


def element_text(node: etree._Element) -> str:
    return "".join(node.itertext())
