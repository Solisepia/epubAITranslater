from __future__ import annotations

import argparse
import sys

from .pipeline import run_translation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="translate-epub", description="EPUB -> 简体中文直译忠实翻译器")
    parser.add_argument("input", help="input epub path")
    parser.add_argument("-o", "--output", required=True, help="output epub path")

    parser.add_argument("--provider", choices=["openai", "deepseek", "dashscope", "dashscope-mt", "mixed", "mock"], default="dashscope")
    parser.add_argument("--draft-provider", choices=["openai", "deepseek", "dashscope", "dashscope-mt", "mock"], default=None)
    parser.add_argument("--revise-provider", choices=["openai", "deepseek", "dashscope", "dashscope-mt", "none", "mock"], default=None)
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--draft-model", default=None)
    parser.add_argument("--revise-model", default=None)

    parser.add_argument("--resume", action="store_true", help="resume from cache")
    parser.add_argument("--cache", default="cache.sqlite", help="sqlite cache path")
    parser.add_argument("--termbase", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--max-concurrency", type=int, default=4)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="print pipeline progress logs")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = run_translation(args, progress_cb=print if args.verbose else None)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
