from __future__ import annotations

from pathlib import Path

from .dom_utils import get_one_by_xpath, parse_xml_file, set_inner_xml, write_xml_file
from .models import NodeTask
from .placeholder_codec import decode_text


def apply_node_translations(workdir: str, node_tasks: list[NodeTask], node_translations: dict[str, str]) -> None:
    by_file: dict[str, list[NodeTask]] = {}
    for task in node_tasks:
        if task.id not in node_translations:
            continue
        by_file.setdefault(task.file_path, []).append(task)

    root = Path(workdir)
    for rel, tasks in by_file.items():
        full = root / rel
        tree = parse_xml_file(str(full))

        # Always resolve node by xpath at apply time; parent node rewrites can invalidate refs.
        for task in tasks:
            node = get_one_by_xpath(tree, task.node_selector)
            if node is None:
                continue
            translated = decode_text(node_translations[task.id], task.placeholder_map)
            set_inner_xml(node, translated)

        write_xml_file(str(full), tree)
