from __future__ import annotations

import re

from .config import AppConfig
from .models import NodeTask, Segment
from .placeholder_codec import PLACEHOLDER_TOKEN_RE, split_text_preserving_placeholders


def build_segments(node_tasks: list[NodeTask], config: AppConfig) -> list[Segment]:
    ordered = sorted(node_tasks, key=lambda t: t.order_index)
    segments: list[Segment] = []
    seg_num = 1

    prev_source = ""
    prev_trans = ""

    for task in ordered:
        chunks = split_text_preserving_placeholders(task.source_text, config.segmentation.max_chars_per_segment)
        for chunk_idx, chunk in enumerate(chunks):
            placeholders = PLACEHOLDER_TOKEN_RE.findall(chunk)
            seg = Segment(
                id=f"S{seg_num:09d}",
                node_task_id=task.id,
                chunk_index=chunk_idx,
                segment_type=task.segment_type,
                file_path=task.file_path,
                node_selector=task.node_selector,
                order_index=task.order_index,
                source_lang="en",
                target_lang=config.target_lang,
                source_text=chunk,
                placeholders=placeholders,
                context_prev_source=prev_source,
                context_prev_translated=prev_trans,
            )
            segments.append(seg)
            prev_source = chunk[-config.context.prev_segment_chars :]
            prev_trans = ""
            seg_num += 1

    return segments


def group_segments_for_batches(segments: list[Segment], max_chars: int, max_segments: int) -> list[list[Segment]]:
    batches: list[list[Segment]] = []
    current: list[Segment] = []
    current_chars = 0

    for seg in segments:
        seg_chars = len(seg.source_text)
        if current and (len(current) >= max_segments or current_chars + seg_chars > max_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(seg)
        current_chars += seg_chars

    if current:
        batches.append(current)
    return batches


def merge_segment_translations(segments: list[Segment], segment_texts: dict[str, str]) -> dict[str, str]:
    by_node: dict[str, list[tuple[int, str]]] = {}
    for seg in segments:
        text = segment_texts.get(seg.id, "")
        by_node.setdefault(seg.node_task_id, []).append((seg.chunk_index, text))

    merged: dict[str, str] = {}
    for node_task_id, parts in by_node.items():
        merged[node_task_id] = "".join(text for _, text in sorted(parts, key=lambda x: x[0]))
    return merged
