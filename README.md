# Crypto Research Agent System

An automated research-and-writing pipeline that walks a curated list of Substack newsletters and YouTube channels, picks articles relevant to your topic and thesis, and produces a publication-ready Markdown + DOCX article in your personal writing voice. All LLM calls bill against your **Claude Max subscription** (no per-token API costs), and every step has interactive feedback so you can revise outline and section content before it's written to disk.

## Table of Contents

- [What it does](#what-it-does)
- [Quick Start (5 minutes)](#quick-start-5-minutes)
- [Authentication and Billing — IMPORTANT](#authentication-and-billing--important)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [How a run works](#how-a-run-works)
- [Interactive feedback flow](#interactive-feedback-flow)
- [Strict relevance scoring](#strict-relevance-scoring)
- [Writing style personalization](#writing-style-personalization)
- [User content integration](#user-content-integration)
- [Output files](#output-files)
- [System Architecture](#system-architecture)
- [Troubleshooting](#troubleshooting)

## What it does

Given a query (e.g. `"Bitcoin ETF"`) and optionally a thesis, the system:

1. Plans search terms via Claude
2. Walks every Substack in `input/Substacks.csv` and every YouTube channel in `input/YouTubes.csv`
3. Pre-filters articles/videos by required keywords; analyzes survivors with Claude using a strict paragraph-focus rubric (so articles that only *mention* the topic don't pass)
4. Optionally pulls in your own research notes / PDFs / CSVs from a `user_content/` directory
5. Generates a research summary + outline; you can revise both interactively
6. Learns your writing voice from samples in `input/writing_samples/` and produces a style card
7. Writes the article section-by-section in your voice; you can revise or manually edit each section before moving on
8. Exports to DOCX via CloudConvert

## Quick Start (5 minutes)

For Windows PowerShell. Adapt commands as needed for macOS/Linux.

```powershell
# 1. Clone
git clone https://github.com/0xLukasinho/CryptoResearchAgent.git
cd CryptoResearchAgent

# 2. Make sure Python 3.13+ is available (3.14 works too)
py -3.14 --version

# 3. Authenticate Claude for subscription billing — see "Auth and Billing" below
claude setup-token
# Copy the token it prints, then:
[Environment]::SetEnvironmentVariable("CLAUDE_CODE_OAUTH_TOKEN", "<token>", "User")
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")
# Open a NEW PowerShell window so the new env vars take effect.

# 4. Install (we use pipx so the CLI lives globally without needing venv activation)
py -3.14 -m pip install --user pipx
py -3.14 -m pipx ensurepath
# Open a NEW PowerShell window so pipx is on PATH.
pipx install -e C:\path\to\CryptoResearchAgent

# 5. Configure non-Claude API keys
cp .env.template .env
# Edit .env, fill in SUPADATA_API_KEY, CLOUDCONVERT_API_KEY, YOUTUBE_API_KEY.
# Do NOT set ANTHROPIC_API_KEY in .env (see warning below).

# 6. Provide writing samples (optional but recommended)
# Drop 1-3 .docx or .txt files into input/writing_samples/
# These define your voice — without them the article comes out generic.

# 7. Run a quick test
crypto-research "Bitcoin ETF" --test --substack --max-age 30
```

A `--test` run produces a real article via Haiku, finishes in ~5-10 min, and bills against your subscription (no per-token cost).

## Authentication and Billing — IMPORTANT

The pipeline routes every LLM call through `claude -p` (the Claude Code CLI), which can authenticate two ways:

| Method | Billing | Setup |
|---|---|---|
| **OAuth token** (`CLAUDE_CODE_OAUTH_TOKEN`) | Claude Max subscription (flat-rate against your plan) | `claude setup-token` |
| **API key** (`ANTHROPIC_API_KEY`) | Pay-per-token via Anthropic API | Set env var |

### ⚠️ DO NOT set `ANTHROPIC_API_KEY`

If `ANTHROPIC_API_KEY` is present in the environment, **`claude -p` prefers it over OAuth and silently routes every call through the API** — even when you have an active Claude Max subscription. This will burn pay-per-token API credits, not your subscription.

The pipeline goes to several lengths to prevent this:

1. `config.py` does not load `ANTHROPIC_API_KEY` at all
2. `PipelineRunner` does not wire any API fallback
3. `ClaudeCodeBackend` strips `ANTHROPIC_API_KEY` from the subprocess environment before invoking `claude -p` (defense in depth)

But the safest state is: **don't have `ANTHROPIC_API_KEY` set anywhere**. Specifically:

```powershell
# Check Windows User-level env vars
[Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")    # should print nothing
[Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "Machine") # should print nothing

# If either prints a value, clear it:
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")
# (And same for "Machine" if you have admin rights)
```

Also leave `ANTHROPIC_API_KEY` blank or absent in `.env`.

### Setting up the OAuth token

```powershell
claude setup-token
```

This opens a browser. Log in with the Anthropic account that has your Claude Max subscription. The CLI prints a long-lived OAuth token (`sk-ant-oat01-...`).

On Windows the token is **NOT auto-stored** in keychain. You need to set it as an env var:

```powershell
# Persistent across reboots, available to all apps you launch (incl. Python subprocess)
[Environment]::SetEnvironmentVariable("CLAUDE_CODE_OAUTH_TOKEN", "<paste token>", "User")
```

Open a **new** PowerShell window for the env var to take effect.

### Verifying it works

```
claude -p "say pong" --model claude-haiku-4-5-20251001 --output-format json
```

If it returns JSON with `"result": "pong"`, OAuth/subscription is working. If it asks you to run setup-token, the env var didn't take effect — open a fresh PowerShell window.

> Note: the JSON output will include a `total_cost_usd` field with a non-zero number. **This is misleading — it's a token-cost estimate, not your actual bill.** Subscription billing is flat-rate; that field is computed regardless of which auth path was used.

## Installation

### Prerequisites

- **Python 3.13 or higher** (3.14 works)
- **Claude Code CLI** ([install link](https://claude.com/claude-code))
- An active **Claude Max subscription** (not Claude Free)
- **Supadata API key** — for YouTube transcripts ([supadata.ai](https://supadata.ai))
- **CloudConvert API key** — for DOCX export ([cloudconvert.com](https://cloudconvert.com))
- **YouTube Data API key** — for video discovery ([Google Cloud Console](https://console.cloud.google.com/apis/credentials))
- **DO NOT** need an Anthropic API key

### Setup steps

1. **Clone**
   ```bash
   git clone https://github.com/0xLukasinho/CryptoResearchAgent.git
   cd CryptoResearchAgent
   ```

2. **Set up Claude OAuth** — see [Authentication and Billing](#authentication-and-billing--important) above.

3. **Install** via pipx (recommended — `crypto-research` becomes a global command):
   ```powershell
   py -3.14 -m pip install --user pipx
   py -3.14 -m pipx ensurepath
   pipx install -e .
   ```
   Or via pip if you'd rather develop in a venv:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure external API keys**
   ```bash
   cp .env.template .env
   ```
   Then edit `.env`:
   ```
   SUPADATA_API_KEY=...
   CLOUDCONVERT_API_KEY=...
   YOUTUBE_API_KEY=...
   ```
   Leave any reference to `ANTHROPIC_API_KEY` blank or remove the line entirely.

5. **Prepare data sources**
   - `input/Substacks.csv` — curated list of newsletters (template provided)
   - `input/YouTubes.csv` — curated list of channels (template provided)
   - `input/writing_samples/` — drop 1-3 `.docx` or `.txt` files of your own writing (optional, but recommended)
   - `input/writing_instructions.txt` — optional notes on style preferences

## Configuration

### `Substacks.csv`

Format: `Name,by,Substack URL,X URL,Status`. Use full root URLs (`https://example.substack.com`). Custom domains work. The pipeline auto-strips paths during normalization.

A bundled `scripts/check_substacks.py` lets you audit the list for dead URLs:

```bash
python scripts/check_substacks.py
```

It writes a cleaned CSV (404s removed, 403s moved to bottom marked PRIVATE) and a colored XLSX for review.

### `YouTubes.csv`

Format: `Name,Channel ID,YouTube URL`. Channel ID must start with `UC` (the YouTube Data API channel-ID format).

### Writing samples

Place 1-3 representative pieces of your own writing in `input/writing_samples/`. Supported formats: `.txt`, `.docx`. The `StyleLearner` reads these once per run and asks Claude to extract a style card (tone, vocabulary, sentence patterns, transitions, example excerpts).

If the directory is empty, the system falls back to a generic "analytical and informative" style card and the article comes out in a default voice.

## Usage

```bash
crypto-research "<your query>" [options]
```

### Command-line arguments

| Argument | Description |
|----------|-------------|
| `<query>` | The research topic, in quotes |
| `--test` | Test mode: Haiku for everything, stops analyzer after finding 2 High/Medium articles, walks at most 30 substacks. ~5-10 min. Mutually exclusive with `--search`. |
| `--search` | Search mode: discovery + analyzer + research summary only; no outline or article. Mutually exclusive with `--test`. |
| `--substack` | Substack only (skip YouTube) |
| `--youtube` | YouTube only (skip Substack) |
| `--thesis "..."` | Provide a thesis direction. Analyzer scores articles by usefulness to the thesis instead of just topic match. |
| `--max-age N` | Only consider articles/videos from the last N days. Strongly recommended (e.g. `--max-age 30`) — without it the system walks years of archived content. |
| `--parallel N` | Currently scaffolded but not wired through analyzer; defaults to 1. |

### Examples

**Quick test (recommended first run):**
```bash
crypto-research "Bitcoin ETF" --test --substack --max-age 30
```

**Full Opus run with thesis:**
```bash
crypto-research "DeFi liquidity fragmentation" --substack --max-age 30 \
  --thesis "Cross-chain bridges have made liquidity fragmentation worse, not better, by enabling silent capital migration."
```

**Discovery only (no article generation):**
```bash
crypto-research "Crypto regulation" --search --max-age 14
```

**YouTube only with thesis:**
```bash
crypto-research "Solana scaling" --youtube --max-age 30 --thesis "..."
```

## How a run works

```
[Coordinator]   query  -> SearchPlan {main_topic, required_terms}
                                                      |
                                                      v
[Discovery]     for each substack/channel: fetch posts → strip HTML → age-filter
                                                      |
                                                      v
                pre-filter: required_terms must appear in title or text
                                                      |
                                                      v
[Analyzer]      Claude rates each article High / Medium / Low against query
                (and against thesis if provided) using paragraph-focus rubric
                                                      |
                                                      v
                                  keep High and Medium only
                                                      |
                          ┌───────────────────────────┴───────────────────────┐
                          v                                                   v
                     no results                                         results found
                          |                                                   |
              [USER CONTENT prompt]                                  [USER CONTENT prompt]
              "ready" or "skip"                                       "ready" or "skip"
                          |                                                   |
                          └───────────────────────────┬───────────────────────┘
                                                      v
[Synthesis]     research_results.md (if any sources) ; outline.md
                                                      |
                                                      v
                                       [OUTLINE FEEDBACK] revise / accept / edited
                                                      |
                                                      v
[StyleLearner]  read writing_samples/  →  style_card.json
                                                      |
                                                      v
[ArticleWriter] write each section via stateful Conversation (style preserved)
                                                      |
                                                      v
                                       [SECTION FEEDBACK] revise / accept / edited
                                                      |
                                                      v
[DocxExport]    article.md  →  article.docx (CloudConvert)
                                                      |
                                                      v
                                            Run Summary printed
```

## Interactive feedback flow

After the outline is generated and after every section is written, the pipeline pauses:

```
[FEEDBACK] Section '2. Body' has been written.
Review it: output/bitcoin_etf_2026-05-08_130550/article.md

  [1] accept     proceed
  [2] revise     give the AI revision instructions
  [3] edited     I edited the file directly
>
```

Three options:

- **`accept`** (or `1`): the section is accepted as-is; pipeline moves on.
- **`revise <instructions>`** (or `2 <instructions>`): the AI rewrites this section based on your instructions. The revised version replaces the original in the file. You can revise multiple times in a row.
- **`edited`** (or `3`): you (the user) edited the file directly in your editor, then chose this. The pipeline re-reads the section from disk and persists your manual edits — they will survive any later revisions on other sections.

Closing stdin (Ctrl+D / pipe / EOF) at any prompt is treated as `accept` — useful for non-interactive runs in CI.

## Strict relevance scoring

A weak prompt produces useless filtering — articles that *mention* the topic get rated High. The Analyzer prompt is intentionally strict: Claude is asked to count paragraphs focused on the topic vs. total paragraphs, then apply explicit thresholds:

**No thesis provided:**
- **HIGH**: article is primarily about the topic. Topic in title and/or developed across ≥4 paragraphs (typically ≥40% of the body).
- **MEDIUM**: topic is a substantive recurring thread (2-3 dedicated paragraphs, or one of several major themes).
- **LOW**: topic mentioned in passing — single paragraph, supporting example, list item.
- Default to **LOW when uncertain.**

**Thesis provided:**
- **HIGH**: article directly tests, supports, contradicts, or analyzes the thesis. A researcher would cite it.
- **MEDIUM**: article touches on related dynamics that inform the thesis without being directly about it.
- **LOW**: article is largely unrelated to the thesis, even if it mentions the topic.
- Default to **LOW when uncertain.**

Only `High` and `Medium` items make it past discovery into synthesis. With this rubric, a typical run rejects 80%+ of pre-filtered candidates — which is the point.

## Writing style personalization

The `StyleLearner` reads everything in `input/writing_samples/` once per run and asks Claude to extract a style card capturing:

- **Tone** — descriptive paragraph
- **Sentence patterns** — typical structures (punchy openers, compound sentences, em-dash asides, etc.)
- **Vocabulary preferred** — terms specific to your writing (e.g. *flywheel*, *mindshare*, *TGE*)
- **Vocabulary avoided** — generic AI-cliché phrases (*"This isn't just X, it's Y"*, *"At its core"*, *"revolutionary"*)
- **Paragraph structure** — how you build paragraphs
- **Section openings** — your typical opening device
- **Transitions** — your characteristic phrases
- **Example excerpts** — 3-5 verbatim snippets from your writing

The card is saved to `output/<run>/style_card.json` and embedded in the article writer's system prompt for every generation and revision call. The article writer also maintains a single conversation thread across all sections (`--resume` session ID), so the model has full context of what it previously wrote and the style remains consistent.

If `input/writing_samples/` is empty, the StyleLearner skips the LLM call entirely and uses a generic fallback card (`StyleCard.fallback()`).

## User content integration

When the pipeline is ready for synthesis, it prompts:

```
[USER CONTENT] Add files to user_content/, then 'ready', or 'skip' to continue without.
>
```

The output directory was created at the start of the run (`output/<slug>_<timestamp>/`). If you want to inject your own materials, drop them into `<that-dir>/user_content/` while the prompt is showing, then type `ready`. Supported types:

- **Text files** (`.txt`, `.md`) — up to 1 MB
- **PDF files** (`.pdf`) — up to 10 MB, parsed via `pdfplumber`
- **CSV files** (`.csv`) — up to 5 MB, treated as raw text data

The Analyzer extracts insights from each file and the OutlineWriter integrates them into the outline alongside the discovered sources. User content is given priority in the synthesis — your notes drive the article structure when present.

For tweets, place a `tweets.txt` file with one URL per line in the user-content directory. The pipeline can extract tweet text via Playwright (handled separately by `TweetExtractor`).

## Output files

Each run creates a timestamped directory under `output/`:

```
output/<slug>_<YYYY-MM-DD_HHMMSS>/
├── research_results.md   # Summary of analyzed Substack/YouTube sources (only if any passed analyzer)
├── research_outline.md   # The outline driving the article
├── style_card.json       # Style card extracted from writing_samples/
├── article.md            # Final article in Markdown
├── article.docx          # Same article exported via CloudConvert
└── user_content/         # Your inputs from the run (if any)
```

Plus a global rotating log at `output/logs/agent.log` (DEBUG-level, all runs).

## System Architecture

The codebase lives under `src/crypto_research_agent/` and is organized in layers.

### Real Agents (`agents/`)

1. **Coordinator** — plans search terms from the query
2. **Analyzer** — strict relevance scoring per article (paragraph-focus rubric, thesis-aware); skip-on-error per-article fault isolation
3. **Summarizer** — builds the markdown research summary
4. **StyleLearner** — extracts the StyleCard from writing samples
5. **OutlineWriter** — generates and revises the outline
6. **ArticleWriter** — writes sections one at a time via a stateful Conversation; strips LLM preamble before persisting

### Services (`services/`)

- **SubstackService** — discovers + fetches posts; strips HTML before storing
- **YouTubeService** — channel discovery → playlist videos → Supadata transcripts
- **DocxExporter** — CloudConvert lifecycle for Markdown → DOCX
- **TweetExtractor** — Playwright-driven tweet text extraction
- **UserContentService** — txt/md/pdf/csv ingestion with size limits

### Pipeline Stages (`pipeline/`)

- **DiscoveryStage** — runs sources + pre-filter + Analyzer
- **SynthesisStage** — saves summary, generates outline, drives outline review
- **WritingStage** — persists style card, drives section-by-section writing + section review
- **PipelineRunner** — top-level orchestrator, owns the LLMRouter

### LLM layer (`llm/`)

- **ClaudeCodeBackend** — `claude -p` subprocess wrapper with subscription billing, env-var scrub, transient-error retry
- **LLMRouter** — single-backend wrapper (subscription-only mode)
- **Conversation** — multi-turn wrapper using `--resume` session IDs
- **AnthropicAPIBackend** — present in code but **not wired into production**; left in case someone explicitly opts in to API mode

### Utilities (`utils/`)

- **logger** — rotating file output + console
- **token_utils** — tiktoken-based truncation at sentence boundaries
- **filters** — required-term + English-language pre-filters
- **html** — BeautifulSoup-based HTML → plain text
- **paths** — slug sanitization + timestamped output dir
- **outline_parser** — Markdown → `{title, content}` sections
- **csv_loader** — typed Substack/YouTube CSV loaders

### AI Services Integration

- **Claude (subscription via `claude -p`)** — every LLM call
  - `claude-haiku-4-5-20251001` for `--test` mode and "fast" roles (Coordinator, Analyzer, Summarizer)
  - `claude-opus-4-7` for "premium" roles (StyleLearner, OutlineWriter, ArticleWriter) in non-test runs
- **Supadata API** — YouTube transcripts
- **CloudConvert API** — Markdown → DOCX
- **YouTube Data API** — channel/video discovery

## Troubleshooting

### Authentication

- **`AuthMissing: Claude Code CLI not found on PATH`**
  Install [Claude Code](https://claude.com/claude-code), confirm `claude -p "ping"` works in your shell, then retry.

- **Pipeline succeeds but I'm being charged API credits**
  `ANTHROPIC_API_KEY` is set somewhere. Check `[Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")` and `"Machine"`. Both should be empty. Also check `.env`. After clearing, open a new PowerShell window.

- **`AuthMissing` after `claude setup-token` succeeded**
  On Windows, `claude setup-token` does not auto-store the token in keychain. You must set `CLAUDE_CODE_OAUTH_TOKEN` as a Windows User-level env var (or in `.env`). Then open a new PowerShell window.

### Discovery / sources

- **Most substacks return 0 articles after age filter**
  Expected with `--max-age 30` if many newsletters publish less than monthly. Run `python scripts/check_substacks.py` to prune dead URLs from your CSV.

- **`Failed to fetch posts from <url>: 404`**
  Substack publication is gone. The audit script will mark these for removal.

- **`Failed to fetch posts from <url>: 403`**
  Private/paid Substack — accessible only with a paid subscription. The audit script moves these to the bottom of the CSV.

### Analysis / writing

- **Every article scored Low**
  Either: (a) the strict prompt is doing its job — your topic is too broad / niche / off-cycle; try a narrower query or shorter `--max-age`; (b) you're using `--test` mode and Haiku is being conservative — try without `--test` once auth is verified.

- **Style card came out as fallback**
  No writing samples in `input/writing_samples/` — drop in 1-3 `.docx` or `.txt` files. Or in test mode the LLM produced non-JSON; it's logged as a warning with the raw response prefix.

- **Article voice doesn't match my samples**
  Check `output/<run>/style_card.json` — if `tone` is `"analytical and informative"` and `example_excerpts` is empty, that's the fallback. Add more diverse samples and rerun. The article writer can only match what the StyleLearner extracted.

### Long runs

- **Run dies mid-way with a single LLM call failing**
  Should not happen as of recent fixes — the Analyzer skips per-article failures, the LLM backend retries transient errors (529/503/timeout/Windows hiccups). If it still happens, check `output/logs/agent.log` for the full traceback and file an issue.

- **Conversation context fills up**
  Article writer uses one stateful conversation per article. With many sections you may approach the model's context window. Reduce the number of outline sections via the outline-revise prompt.

### General

- **Output ends up in the wrong directory**
  `OUTPUT_DIR` is resolved relative to the package install location. With editable install (`pipx install -e` or `pip install -e`), runs land in `<repo>/output/`.

- **Inspecting a problematic run**
  Each run leaves its full state in `output/<slug>_<timestamp>/`. Plus the global `output/logs/agent.log` has DEBUG-level history of every run with timestamps.

If you encounter persistent issues, check the console output for specific error messages, then `output/logs/agent.log` for a full traceback.
