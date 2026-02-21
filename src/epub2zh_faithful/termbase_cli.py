from __future__ import annotations

import argparse
import sys

from .config import load_config
from .termbase_generator import GenerateOptions, generate_termbase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="generate-termbase", description="Generate termbase candidates from EPUB")
    parser.add_argument("input", help="input epub path")
    parser.add_argument("-o", "--output", required=True, help="output termbase yaml path")
    parser.add_argument("--min-freq", type=int, default=2, help="minimum occurrence frequency")
    parser.add_argument("--max-terms", type=int, default=300, help="max generated term count")
    parser.add_argument("--include-single-word", action="store_true", help="include single-word proper nouns")
    parser.add_argument("--no-merge-existing", action="store_true", help="do not merge existing output terms")
    parser.add_argument("--fill-empty-targets", action="store_true", help="use AI to fill terms with empty target")
    parser.add_argument("--fill-provider", choices=["openai", "deepseek", "mock"], default="openai")
    parser.add_argument("--fill-model", default="gpt-5-mini")
    parser.add_argument("--fill-batch-size", type=int, default=40)
    parser.add_argument("--config", default=None, help="optional config.yaml/json for llm retry/timeout settings")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    options = GenerateOptions(
        min_freq=max(1, args.min_freq),
        max_terms=max(1, args.max_terms),
        include_single_word=bool(args.include_single_word),
        merge_existing=not bool(args.no_merge_existing),
        fill_empty_targets=bool(args.fill_empty_targets),
        fill_provider=args.fill_provider,
        fill_model=args.fill_model or "gpt-5-mini",
        fill_batch_size=max(1, args.fill_batch_size),
    )
    llm_config = load_config(args.config)

    stats = generate_termbase(
        input_epub=args.input,
        output_path=args.output,
        options=options,
        progress_cb=lambda msg: print(msg),
        llm_config=llm_config,
    )

    print(
        "Done. "
        f"scanned_text_nodes={stats['scanned_text_nodes']} "
        f"candidate_terms={stats['candidate_terms']} "
        f"generated_terms={stats['generated_terms']} "
        f"total_terms_in_file={stats['total_terms_in_file']} "
        f"filled_targets={stats['filled_targets']} "
        f"rejected_non_cjk_targets={stats.get('rejected_non_cjk_targets', 0)} "
        f"cleared_non_cjk_targets={stats.get('cleared_non_cjk_targets', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
