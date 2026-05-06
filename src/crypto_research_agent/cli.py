import argparse

from .config import OUTPUT_DIR
from .pipeline.runner import PipelineRunner, RunContext, SourceConfig
from .utils.paths import build_output_dir


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crypto-research",
                                description="Crypto Research Agent")
    p.add_argument("query", nargs="+", help="Research query")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--test", action="store_true",
                      help="Test mode: Haiku for everything; stops early")
    mode.add_argument("--search", action="store_true",
                      help="Search mode: discovery only, no outline/article")
    p.add_argument("--youtube", action="store_true", help="YouTube only")
    p.add_argument("--substack", action="store_true", help="Substack only")
    p.add_argument("--thesis", type=str, help="Thesis direction")
    p.add_argument("--max-age", type=int, dest="max_age",
                   help="Only include content newer than N days")
    p.add_argument("--parallel", type=int, default=1,
                   help="Parallel analyzer calls (max 3)")
    return p


def main() -> None:
    args = build_parser().parse_args()
    sources = SourceConfig(
        substack=args.substack or not args.youtube,
        youtube=args.youtube or not args.substack,
    )
    if args.youtube and args.substack:
        sources = SourceConfig(substack=True, youtube=True)
    query = " ".join(args.query)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = build_output_dir(OUTPUT_DIR, query)
    ctx = RunContext(
        query=query, thesis=args.thesis, output_dir=output_dir,
        test_mode=args.test, search_mode=args.search,
        sources=sources, max_age_days=args.max_age,
        parallel=min(args.parallel, 3),
    )
    PipelineRunner().run_with_context(ctx)


if __name__ == "__main__":
    main()
