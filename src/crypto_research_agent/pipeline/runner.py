from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceConfig:
    substack: bool
    youtube: bool


@dataclass
class RunContext:
    query: str
    thesis: str | None
    output_dir: Path
    test_mode: bool
    search_mode: bool
    sources: SourceConfig
    max_age_days: int | None
    parallel: int = 1


class PipelineRunner:
    """Top-level orchestrator. Composes pipeline stages, owns LLMRouter."""
    # Filled in by later tasks (G2..G6).
    pass
