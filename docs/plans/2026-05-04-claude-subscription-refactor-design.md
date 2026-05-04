# Claude Subscription Refactor — Design Document

**Date:** 2026-05-04
**Scope:** Full version upgrade, package modernization, refactor to use Claude Max subscription via `claude -p` subprocess, drop fact-checker, restructure pipeline architecture.
**Predecessor:** `2026-02-20-crypto-research-agent-improvement-design.md` (Claude migration + writing pipeline)

---

## Goals

1. **Switch billing from API key to Claude Max subscription** — calls go through `claude -p` (Claude Code CLI in headless mode), routing through the user's Pro/Max subscription quota at zero per-call cost.
2. **Use Opus 4.7 for writing-quality work** — outline, style card, article writer. Economically viable only under subscription.
3. **Drop the fact-checker** — it has been more harmful than helpful (false positives, voice damage on "corrections").
4. **Full refactor** — proper Python packaging, clean separation of concerns, pinned latest dependencies, Python 3.13 floor.
5. **Comprehensive test coverage** — ~5× current count, all layers, golden-file snapshots, end-to-end pipeline test.
6. **Avoid silent regressions** — typed dataclasses, dependency injection, mockable backends.

## Non-Goals

- Async/concurrent rewrite of the entire pipeline (kept synchronous for simplicity).
- Plugin architecture for new content sources.
- Resumable runs / checkpointing.
- Web UI replacing the interactive prompts.

---

## Section 1: Architecture & Layering

### Old Layout (current)

```
.
├── main.py                  (586 LOC orchestrator)
├── config.py
├── agents/                  (12 mixed: real LLM agents + utility classes)
└── utils/                   (mixed: helpers + I/O clients)
```

Issues: `sys.path.append('..')` everywhere, no proper package, fake "agents" inheriting from `ClaudeAgentBase` despite making zero LLM calls (DatabaseSearch, ArticleRetrieval, OutlineFinalizer, FeedbackProcessor, OutlineFeedback), 586-line `main.py` with deep nesting and hidden coupling.

### New Layout

```
crypto_research_agent/
├── pyproject.toml
├── README.md
│
├── src/crypto_research_agent/
│   ├── cli.py                 (argument parsing, ~50 LOC)
│   ├── config.py              (env loading, model constants, paths)
│   │
│   ├── llm/
│   │   ├── client.py          (ClaudeCodeBackend — subprocess wrapper)
│   │   ├── api_backend.py     (AnthropicAPIBackend — fallback only)
│   │   ├── router.py          (LLMRouter — primary + quota-fallback)
│   │   ├── conversation.py    (Conversation — multi-turn state)
│   │   └── errors.py          (QuotaExceeded, ClaudeCodeError, etc.)
│   │
│   ├── agents/                (only TRUE LLM agents — 6)
│   │   ├── coordinator.py
│   │   ├── analyzer.py
│   │   ├── summarizer.py
│   │   ├── outline_writer.py
│   │   ├── style_learner.py
│   │   └── article_writer.py
│   │
│   ├── services/              (formerly fake "agents" — plain services)
│   │   ├── substack.py        (DatabaseSearch + ArticleRetrieval + substack_api_client + substack_wrapper merged)
│   │   ├── youtube.py         (YouTubeAgent + youtube_api merged)
│   │   ├── docx_export.py     (was CloudConvertClient)
│   │   ├── tweet_extractor.py
│   │   └── user_content.py    (was UserContentManager)
│   │
│   ├── pipeline/              (orchestration — splits old main.py)
│   │   ├── runner.py
│   │   ├── discovery.py
│   │   ├── synthesis.py
│   │   ├── writing.py
│   │   └── docx_export_stage.py
│   │
│   ├── feedback/              (interactive prompts — no LLM)
│   │   ├── outline_review.py
│   │   ├── section_review.py
│   │   └── prompts.py         (clearer [1]/[2]/[3] UI)
│   │
│   └── utils/
│       ├── logger.py
│       ├── token_utils.py
│       ├── filters.py         (was article_filter — debug prints removed)
│       ├── paths.py           (output dir naming, sanitization)
│       ├── outline_parser.py  (was OutlineFinalizerAgent)
│       └── csv_loader.py
│
├── tests/                     (mirrors src/ structure)
│   ├── conftest.py
│   ├── fixtures/
│   ├── golden/
│   └── ... (one dir per src/ module)
│
├── input/                     (UNCHANGED — Substacks.csv, YouTubes.csv, writing_samples/)
└── output/                    (UNCHANGED — existing output dirs preserved)
```

### Key Wins

- 12 "agents" → 6 real agents + 5 services + 4 pipeline stages
- `main.py` 586 LOC → `cli.py` (50) + `runner.py` (150) + 4 stages (~100 each)
- Proper Python package: `pip install -e .`, no more `sys.path.append('..')`
- Tests mirror source structure
- Single responsibility per file

### Concurrency

Sequential by default. `--parallel N` flag (off by default, max 3) for opt-in parallelism on Analyzer batch (the only stage with many independent calls). Conservative because subscription rate limits are real and `claude -p` startup adds local-machine load.

---

## Section 2: LLM Layer

### Backend Abstraction

```python
class LLMBackend(Protocol):
    def complete(self, prompt: str, *, model: str, system_prompt: str = "",
                 resume_session: str | None = None) -> ClaudeResponse: ...
    def complete_json(self, ...) -> dict: ...

class ClaudeCodeBackend(LLMBackend):
    """Primary. Subscription-billed via `claude -p` subprocess."""

class AnthropicAPIBackend(LLMBackend):
    """Fallback. Pay-per-token via anthropic SDK + ANTHROPIC_API_KEY."""
```

### `ClaudeCodeBackend` — subprocess invocation

Always-applied flags:

```
claude -p --bare --output-format json --allowedTools "" \
       --model <resolved-model> \
       [--append-system-prompt <system>] \
       [--resume <session-id>] \
       <prompt>
```

- `--bare`: skip hook/MCP/skills loading → faster cold starts
- `--allowedTools ""`: disable all tools → pure LLM gateway
- `--output-format json`: structured response with `result`, `session_id`, `total_cost_usd`, `usage`
- Long prompts/system passed via stdin (`subprocess.run(..., input=...)`) to avoid shell escape issues

Returns:

```python
@dataclass
class ClaudeResponse:
    text: str
    session_id: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int
```

### `Conversation` — multi-turn state

State is delegated to whichever backend is active:

- `ClaudeCodeBackend`: `--resume <session_id>` between turns (Claude Code holds state)
- `AnthropicAPIBackend`: traditional `messages=[...]` list maintained client-side

The `Conversation` class hides this — agents call `conv.send(text)` and don't know which backend is active.

### `LLMRouter` — quota-exhaustion fallback

The Max subscription quota is **shared across all models** — when it's gone, every `claude -p` call fails regardless of `--model`. So:

- Detect `QuotaExceeded` from `ClaudeCodeBackend` (non-zero exit + stderr pattern matching `usage limit|quota exceeded|rate limit` case-insensitive, OR JSON `is_error: true` with quota message)
- Pause the run, prompt the user **once**:

```
[QUOTA] Your Claude Max subscription quota is exhausted.
        The run can continue using the Anthropic API (pay-per-token).

  [1] Continue with Opus  (highest quality, ~$X/article)
  [2] Continue with Sonnet (lower cost, slight quality drop)
  [3] Abort the run

> 
```

- After choice, switch the router to `AnthropicAPIBackend` (with chosen model for premium-tier calls; Haiku-tier still uses Haiku via API). Switch is permanent for the rest of the run.

### Error Handling

| Condition | Detection | Behavior |
|---|---|---|
| Quota exhausted | Exit code + stderr pattern OR JSON `is_error` | Trigger router fallback prompt |
| Auth missing | Stderr "not authenticated" | Fail fast: "Run `claude setup-token` first" |
| `claude` CLI not on PATH | `FileNotFoundError` | Fail fast with install link |
| Network/transient | Other non-zero exits | Retry up to 2× with backoff (1s, 4s) |
| Timeout (>5 min/call) | `TimeoutExpired` | Raise `ClaudeCodeError`, no retry |

### Cost Observability

Every call's `cost_usd` and `usage` logged at DEBUG. End-of-run summary prints totals:

```
=== Run Summary ===
  Total calls:        142
  Subscription:       142
  API fallback:       0
  Approx. quota cost: $4.27 (would-be API equivalent)
  Sonnet fallbacks:   0
  Failed calls:       0
```

`total_cost_usd` from Claude Code's JSON output is what the equivalent API call **would have** cost — a useful proxy for subscription quota burn.

### Dependencies

| Package | Status | Purpose |
|---|---|---|
| `anthropic >=0.98.0` | Kept | API fallback path only |
| `claude` CLI | External | Primary backend |

No SDK is dropped — the API fallback is non-negotiable safety. But the SDK is no longer the primary path.

---

## Section 3: The 6 Real Agents

All agents drop `ClaudeAgentBase` inheritance. Each takes an injected `LLMBackend` (or `Conversation`).

### Model Tier Mapping

```python
# config.py
CLAUDE_FAST_MODEL    = "claude-haiku-4-5-20251001"
CLAUDE_PREMIUM_MODEL = "claude-opus-4-7"
CLAUDE_SONNET_MODEL  = "claude-sonnet-4-6"  # fallback choice only

def get_model_for_role(role: str, test_mode: bool) -> str:
    if test_mode:
        return CLAUDE_FAST_MODEL  # Haiku for ALL roles in test mode
    return {
        "fast":    CLAUDE_FAST_MODEL,
        "premium": CLAUDE_PREMIUM_MODEL,
    }[role]
```

| Tier | Model | Used by |
|---|---|---|
| Fast | Haiku 4.5 | Coordinator, Analyzer (50–200 calls/run), Summarizer |
| Premium | Opus 4.7 | OutlineWriter, StyleLearner, ArticleWriter |
| `--test` mode | Haiku 4.5 (everything) | functionality testing |

### 3.1 `Coordinator`

**Job:** Parse query → JSON plan with `required_terms`.

Drop unused output fields (`subtopics`, `keywords`, `search_strategy`, `competing_projects` — nothing reads them downstream). Only `main_topic` and `required_terms` survive.

### 3.2 `Analyzer`

**Job:** Score each article/video for relevance, extract key insights.

Same logic as today, accepts injected `LLMBackend`. Returns typed `AnalyzedItem` dataclass instead of dict. Keeps non-English filter. Optional `--parallel N` from CLI uses `ThreadPoolExecutor`.

### 3.3 `Summarizer`

**Job:** Combine analyzed articles + videos into research markdown.

Mostly cosmetic refactor. Sort/format helpers extracted to module-level functions for testability.

### 3.4 `OutlineWriter` (was `OutlineGeneratorAgent`)

**Job:** Generate outline + handle revisions.

Two methods: `generate(...)` and `revise(current, instructions, ...)`. Shared system prompt deduplicated (currently lives in two places). Typo "neeed" fixed. `thesis_direction` handled cleanly.

### 3.5 `StyleLearner` (was `StyleLearningAgent`)

**Job:** Read writing samples + instructions → produce structured `StyleCard`.

Returns typed `StyleCard` dataclass. File-loading I/O extracted to `services/writing_samples.py`. Generates via Opus. `format_for_prompt()` becomes a method on `StyleCard`.

```python
@dataclass
class StyleCard:
    tone: str
    sentence_patterns: str
    vocabulary: Vocabulary
    paragraph_structure: str
    section_openings: str
    transitions: list[str]
    example_excerpts: list[str]

    def format_for_prompt(self) -> str: ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "StyleCard": ...
    @classmethod
    def fallback(cls) -> "StyleCard": ...
```

### 3.6 `ArticleWriter`

**Job:** Write article section-by-section in user's voice, multi-turn.

Wraps a `Conversation` (hides backend choice). The `accepted_sections` list (used to rewrite article file from scratch on revision) stays — it's a clean local mechanism. The `conversation_history` list **goes away** — `Conversation.send()` handles state.

Methods: `start_article`, `write_section`, `revise_section`, `accept_revision`. All use `allow_sonnet_fallback=True` because the writer is the most quota-hungry.

### Naming Consistency

| Old | New |
|---|---|
| `CoordinatorAgent` | `Coordinator` |
| `AnalysisAgent` | `Analyzer` |
| `SummarizationAgent` | `Summarizer` |
| `OutlineGeneratorAgent` | `OutlineWriter` |
| `StyleLearningAgent` | `StyleLearner` |
| `ArticleWriterAgent` | `ArticleWriter` |

### What Disappears

- `FactCheckerAgent` — deleted entirely
- `DatabaseSearchAgent` — was just shuffling URLs; becomes a function in `services/substack.py`
- `ArticleRetrievalAgent` — was wrapping API client; merged into `services/substack.py`
- `OutlineFinalizerAgent` — markdown parser, no LLM; becomes `utils/outline_parser.py`
- `FeedbackProcessor` / `OutlineFeedbackProcessor` — moved to `feedback/`, no Claude inheritance
- `ClaudeAgentBase` — abstraction collapses; `LLMBackend.complete_json()` covers what it did
- `AnthropicClient.check_facts()` — gone with the fact-checker

---

## Section 4: Services Layer

### 4.1 `services/substack.py` — consolidates 4 files

**Merges:** `agents/database_search.py` + `agents/article_retrieval.py` + `utils/substack_api_client.py` + `utils/substack_wrapper.py` (~700 LOC) → ~400 LOC.

```python
@dataclass
class Article:
    title: str
    author: str
    date: str    # ISO normalized
    text: str
    url: str

class SubstackService:
    def __init__(self, csv_path: Path, *, request_delay: float = 0.05): ...
    def discover(self, *, max_age_days: int | None, test_mode: bool) -> Iterator[Article]: ...
    def fetch_posts(self, newsletter_url: str, *, max_articles: int,
                    max_age_days: int | None) -> list[Article]: ...
```

Cleanup:
- Drop `print()`-spam debug logging → structured `logger.debug(...)`
- Drop `last_had_age_filtering` hidden-attribute hack (return tuple instead)
- `Newsletter`/`Post` from `substack_wrapper` get inlined as private helpers
- Centralized robust date parsing

### 4.2 `services/youtube.py` — consolidates 2 files

**Merges:** `agents/youtube_search.py` + `utils/youtube_api.py` (~700 LOC) → ~450 LOC.

```python
@dataclass
class Video:
    title: str
    channel: str
    date: str
    description: str
    video_id: str
    url: str
    transcript: str | None = None
    relevance_score: Literal["High", "Medium", "Low"] = "Medium"

class YouTubeService:
    def __init__(self, api_key: str, supadata_key: str, channels_csv: Path): ...
    def search(self, *, query: str, required_terms: list[str], max_results: int,
               max_age_days: int | None, test_mode: bool, output_dir: Path) -> list[Video]: ...
```

Cleanup:
- Required-terms filter extracted to pure function `filter_by_required_terms(videos, terms)`
- Relevance scoring extracted to `score_relevance(video, query)` (currently 80 LOC inside method)
- Transcript fetching split: `fetch_transcript(video_id)` (testable) + `save_transcript(video, output_dir)` (I/O)

### 4.3 `services/docx_export.py` — was `CloudConvertClient`

Light touch: rename to `DocxExporter`, replace `print()` with logger, type hints, move `__main__` test harness to a real test file.

### 4.4 `services/user_content.py` — was `UserContentManager`

```python
@dataclass
class UserContent:
    title: str
    author: str
    text: str
    url: str
    file_type: Literal["text", "pdf", "csv", "tweet"]
    key_insights: list[str]
    mentioned_projects: list[str]

class UserContentService:
    def __init__(self, analyzer: Analyzer): ...  # injected, not lazily created
    def collect(self, content_dir: Path) -> list[UserContent]: ...
```

File-type dispatch via dict not `if/elif/elif`. PDF/CSV/text processors extracted to module-level functions.

### 4.5 `services/tweet_extractor.py`

Mostly unchanged. Logger replaces prints. Returns typed `Tweet` dataclass. Playwright launch wrapped in mockable context manager. Dry-run mode for tests.

### Net Effect

~2200 LOC across 7 service files → ~1500 LOC across 5 files. Same functionality, half the complexity.

---

## Section 5: Pipeline Orchestration

Replaces 586-LOC `main.py` with focused stages.

### `cli.py` — entry point (~50 LOC)

```python
def main():
    args = parse_args()
    config = load_config(test_mode=args.test, parallel=args.parallel)
    runner = PipelineRunner(config)
    runner.run(
        query=args.query, thesis=args.thesis,
        max_age_days=args.max_age,
        sources=resolve_sources(args.youtube, args.substack),
        mode=resolve_mode(args.test, args.search),
    )
```

### `pipeline/runner.py` — top-level orchestrator (~150 LOC)

Composes the stages, manages `RunContext`, handles quota-fallback prompt.

```python
@dataclass
class RunContext:
    query: str
    thesis: str | None
    output_dir: Path
    test_mode: bool
    search_mode: bool
    sources: SourceConfig
    config: AppConfig
    llm: LLMRouter
    logger: Logger

class PipelineRunner:
    def run(self, ...):
        ctx = self._build_context(...)
        plan = Coordinator(ctx).plan(ctx.query)
        articles, videos = DiscoveryStage(ctx).run(plan)

        if not articles and not videos:
            if not self._prompt_continue_with_user_content():
                return

        if ctx.search_mode:
            SynthesisStage(ctx).save_summary(articles, videos, plan)
            return

        user_content = UserContentStage(ctx).collect()
        outline = SynthesisStage(ctx).synthesize(articles, videos, user_content, plan)
        WritingStage(ctx).write(outline, articles, videos, user_content)
        DocxExportStage(ctx).export()
        self._print_run_summary(ctx)
```

### Pipeline Stages

- **`pipeline/discovery.py`** — Substack + YouTube discovery + Analyzer batch
- **`pipeline/synthesis.py`** — Summarizer → save research_results.md → OutlineWriter.generate → review loop
- **`pipeline/writing.py`** — StyleLearner → save style_card.json → ArticleWriter conversation + section loop with revisions
- **`pipeline/docx_export_stage.py`** — final DOCX conversion

### `feedback/` — interactive prompts

Same `accept` / `revise` / `edited` commands but with clearer numeric+word UI:

```
[FEEDBACK] Section 'Introduction' has been written.
Review it: output/bitcoin_etf_2026-05-04_142301/article.md

  [1] accept     proceed to next section
  [2] revise     give the AI revision instructions
  [3] edited     I edited the file directly, accept my changes

> 2 the second paragraph is too long, tighten it
```

Numeric shortcut + word command both work.

### Quota-Exhaustion Handler (in runner)

Centralized in the runner. On `QuotaExceeded`:
1. Pause the current call.
2. Prompt user: Opus / Sonnet / Abort.
3. Set `LLMRouter`'s fallback to `AnthropicAPIBackend` with chosen model.
4. Retry the failing call on the new backend.
5. All subsequent calls go through the API for the rest of the run.

### Run Summary at End

```
=== Run Summary: bitcoin_etf_2026-05-04_142301 ===
  Duration:           14m 22s
  Articles analyzed:  87 (12 high-relevance, 19 medium)
  Videos analyzed:    14 (3 with transcripts)
  User content:       2 PDFs, 5 tweets
  Sections written:   8 (3 revisions across 2 sections)
  
  LLM calls:          142 total
    Subscription:     142
    API fallback:     0
  Approx. quota cost: $4.27 (would-be API equivalent)
  
  Output: output/bitcoin_etf_2026-05-04_142301/
    ├── research_results.md
    ├── research_outline.md
    ├── style_card.json
    ├── article.md
    └── article.docx
```

### Output Directory Naming

Old: `output/Kaito (4)/` (spaces, parens, fragile)
New: `output/kaito_2026-05-04_142301/` (snake_case + timestamp, never collides)

Existing output directories preserved untouched.

---

## Section 6: Testing Strategy (T2)

### Infrastructure

```
tests/
├── conftest.py             # shared fixtures (FakeLLMBackend, mock servers)
├── fixtures/               # sample articles, videos, style cards, writing samples
├── golden/                 # snapshot files for stable-output assertions
├── llm/
├── agents/
├── services/
├── pipeline/
├── feedback/
└── utils/
```

**Stack:** `pytest >=8`, `pytest-mock`, `responses >=0.25` (HTTP), `freezegun` (dates). No `pytest-asyncio` — everything sync.

### Central Mocking Strategy

`FakeLLMBackend` records calls and returns scripted responses. Every test that would call an LLM uses it. Result: **zero subprocess and zero network calls in the test suite.** Runs in milliseconds, no flakiness.

```python
class FakeLLMBackend:
    def __init__(self, responses: list[str | dict]):
        self.responses = list(responses)
        self.calls: list[CallRecord] = []

    def complete(self, prompt, *, model, system_prompt="", resume_session=None):
        self.calls.append(CallRecord(prompt, model, system_prompt, resume_session))
        result = self.responses.pop(0) if self.responses else "default response"
        return ClaudeResponse(text=str(result), session_id="test-session", cost_usd=0.001, ...)
```

### Layer Coverage

| Layer | Test files | Approx. test count |
|---|---|---|
| `llm/` | 4 | ~25 |
| `agents/` | 6 | ~30 |
| `services/` | 5 | ~25 |
| `pipeline/` | 5 | ~20 |
| `feedback/` | 2 | ~10 |
| `utils/` | 5 | ~25 |
| Golden | 4 files | ~10 |
| E2E | 1 | 1 |
| Live smoke (gated) | 1 | 1 |
| **Total** | **~33 files** | **~150 tests** |

Up from ~13 files / ~30 tests today.

### Key Tests

- **Unit tests** — every refactored agent/service/util with `FakeLLMBackend` injected.
- **Golden-file tests** — `StyleCard.format_for_prompt()`, outline markdown shape, run summary text, Coordinator JSON schema. Updated via `pytest --snapshot-update` when intentional.
- **End-to-end** — `tests/pipeline/test_e2e.py` runs the whole pipeline with all external services (Substack/YouTube/CloudConvert/LLM) mocked. Catches integration regressions anywhere in the stack.
- **Quota fallback** — `tests/pipeline/test_runner_quota_fallback.py` verifies `QuotaExceeded` triggers the prompt, switches backend, and the run completes.
- **Live smoke (gated)** — `tests/integration/test_real_claude_smoke.py` runs against real `claude -p`. Gated by `RUN_LIVE_TESTS=1` env var. Local-only (no `claude` CLI in CI).

### CI Considerations

- Non-integration tests run in <30s on a laptop.
- `pyproject.toml` `[tool.pytest.ini_options]` configures defaults.
- Coverage target: **80%+ on src/** (excludes glue code).

---

## Dependency Updates

All packages pinned to current latest at refactor time:

| Old | New |
|---|---|
| Python (implicit 3.10) | Python `>=3.13` |
| `anthropic >=0.49.0` | `anthropic >=0.98.0` |
| `pandas >=1.3.0` | `pandas >=2.2` |
| `requests >=2.25.0` | `requests >=2.32` |
| `beautifulsoup4 >=4.9.0` | `beautifulsoup4 >=4.12` |
| `feedparser >=6.0.0` | `feedparser >=6.0` (already current) |
| `python-dotenv >=0.19.0` | `python-dotenv >=1.0` |
| `pdfplumber >=0.7.0` | `pdfplumber >=0.11` |
| `python-docx >=1.0.0` | `python-docx >=1.1` |
| `tiktoken >=0.5.0` | `tiktoken >=0.8` |
| `playwright >=1.40.0` | `playwright >=1.50` |
| `substack-api >=1.0.2` | `substack-api >=1.x` (latest) |
| `argparse >=1.4.0` | **REMOVED** (stdlib) |
| (none) | `pytest >=8` |
| (none) | `pytest-mock` |
| (none) | `responses >=0.25` |
| (none) | `freezegun` |

External requirement: **Claude Code CLI installed** + `claude setup-token` run for `CLAUDE_CODE_OAUTH_TOKEN`.

---

## Backwards Compatibility & Data Preservation

| Item | Treatment |
|---|---|
| `input/Substacks.csv` | Unchanged |
| `input/YouTubes.csv` | Unchanged |
| `input/writing_samples/` | Unchanged |
| `input/writing_instructions.txt` | Unchanged |
| Existing `output/...` directories | Untouched |
| Output file structure (`research_results.md`, `outline.md`, `style_card.json`, `article.md`, `article.docx`) | Unchanged |
| Output directory naming | **Changed** to `query_YYYY-MM-DD_HHMMSS` |
| Interactive command words (`accept`, `revise`, `edited`) | Unchanged |
| Interactive prompt UI | **Improved** — numeric shortcuts added (`1`, `2`, `3`) |
| `.env` keys (`SUPADATA_API_KEY`, `CLOUDCONVERT_API_KEY`, `YOUTUBE_API_KEY`) | Unchanged |
| `.env` keys (`ANTHROPIC_API_KEY`) | Now optional — only needed for API fallback |

---

## Compliance & Auth

Per Anthropic's Feb 2026 ToS clarification, the third-party OAuth ban targets **distributed/commercial products** wrapping Claude. **Personal local automation invoking the local `claude` CLI is allowed.** `CLAUDE_CODE_OAUTH_TOKEN` (via `claude setup-token`) is documented for "CI and scripts" — exactly this use case.

This refactor:
- Runs `claude` CLI as a subprocess from the user's own Python script, on the user's own machine, for the user's own personal use.
- Does not redistribute, sell, or wrap Claude as a product.
- Is fully compliant.

---

## Success Criteria

1. All primary LLM calls route through `claude -p` subprocess (subscription quota).
2. API fallback triggers only on quota exhaustion, with user choice.
3. `--test` mode uses Haiku for all roles.
4. Article writer uses Opus 4.7 by default.
5. All `print()` statements removed from agent and service code; structured logging only.
6. No `sys.path.append('..')` anywhere.
7. `pip install -e .` works from a clean checkout.
8. Test suite passes: ~150 tests across 6 layers, including E2E pipeline test with mocked services.
9. Run summary printed at end with cost estimate and call count.
10. Existing `input/` files work unchanged with the new code.

---

## Out of Scope (Explicit)

- Async/concurrent rewrite of full pipeline.
- Plugin architecture.
- Resumable runs.
- Web UI.
- Migration off Substack/YouTube/SupaData/CloudConvert APIs.
- Improvements to the relevance-scoring heuristics in `youtube.py` (beyond extracting them to testable functions).
- Changes to the writing samples format.
