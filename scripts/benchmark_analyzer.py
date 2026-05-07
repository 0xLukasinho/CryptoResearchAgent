"""Offline benchmark: feed known articles through the Analyzer with various
queries/theses and print the relevance matrix. Validates prompt strictness
without running a full discovery pipeline.

Each test is one real `claude -p` call (Haiku). 3 articles × 3 configs = 9 calls
× ~15s = ~2 minutes total.
"""
from __future__ import annotations

import sys
from pathlib import Path

from crypto_research_agent.agents.analyzer import Analyzer
from crypto_research_agent.config import CLAUDE_FAST_MODEL
from crypto_research_agent.llm.claude_code import ClaudeCodeBackend
from crypto_research_agent.services.substack import Article


def load_article(path: Path, title: str, url: str) -> Article:
    return Article(
        title=title, author="(test fixture)", date="2026-01-01",
        text=path.read_text(encoding="utf-8"), url=url,
    )


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    fixtures = [
        load_article(
            repo / "output" / "Bittensor_dTAO_subnets" / "article.md",
            title="Bittensor dTAO subnets",
            url="file://bittensor",
        ),
        load_article(
            repo / "output" / "Ethereum_better_store_of_value (1)" / "article.md",
            title="Ethereum better store of value",
            url="file://eth-sov",
        ),
        load_article(
            repo / "output" / "bitcoin_etf_2026-05-06_165319" / "article.md",
            title="Bitcoin ETF",
            url="file://btc-etf",
        ),
    ]

    test_configs = [
        ("Bitcoin ETF", None),
        ("Bitcoin ETF",
         "Bitcoin ETF inflows are a signal that the market is recovering, "
         "if observed alongside other macro signals."),
        ("Bittensor TAO", None),
    ]

    backend = ClaudeCodeBackend()
    analyzer = Analyzer(backend, model=CLAUDE_FAST_MODEL)

    # Header
    col_widths = [44, 22, 22, 22]
    print()
    print(f"{'Article':<{col_widths[0]}}", end="")
    for topic, thesis in test_configs:
        label = f"{topic}{' +thesis' if thesis else ''}"
        print(f"{label:<{col_widths[1]}}", end="")
    print()
    print("-" * (col_widths[0] + col_widths[1] * len(test_configs)))

    # Run all calls once; store results so we don't double-bill
    results: dict[tuple[str, str, str | None], object] = {}
    for art in fixtures:
        print(f"{art.title:<{col_widths[0]}}", end="", flush=True)
        for topic, thesis in test_configs:
            try:
                r = analyzer.analyze(art, main_topic=topic, thesis=thesis)
                cell = "NON-ENGLISH" if r is None else r.relevance_score
            except Exception as e:
                r = None
                cell = f"ERROR:{type(e).__name__}"
            results[(art.title, topic, thesis)] = r
            print(f"{cell:<{col_widths[1]}}", end="", flush=True)
        print()

    # Detailed explanations (no extra LLM calls)
    print("\n=== Detailed explanations ===")
    for art in fixtures:
        for topic, thesis in test_configs:
            label = f"{art.title} -- '{topic}'" + (" +thesis" if thesis else "")
            r = results.get((art.title, topic, thesis))
            print(f"\n[{label}]")
            if r is None:
                print("  -> NON-ENGLISH or ERROR")
                continue
            print(f"  -> relevance={r.relevance_score}  thesis_alignment={r.thesis_alignment}")
            print(f"  -> {r.relevance_explanation}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
