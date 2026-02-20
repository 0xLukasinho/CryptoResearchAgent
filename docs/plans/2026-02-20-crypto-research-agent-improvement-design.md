# CryptoResearchAgent Improvement Design

**Date:** 2026-02-20
**Scope:** Full Claude model migration, multi-turn article writing pipeline, style card system, medium technical refactor

---

## Problem Statement

The current system has three primary pain points:

1. **Style matching is weak** — `StyleLearningAgent` produces vague prose descriptions of the user's writing style that don't give the model enough to reliably reproduce it.
2. **Content feels shallow and poorly structured** — outline and article sections lack depth.
3. **Style degrades on revision** — each rewrite is a stateless API call with no memory of what was previously written, so the user's voice erodes with each revision pass.

Additionally, the system uses `gpt-4o-mini` for 8 of 12 agents despite the goal of using Claude throughout, and the codebase has accumulated technical debt: `print()`-based logging, ad-hoc character truncation, and inconsistent error handling.

---

## Approach

**Approach C — Writing pipeline redesign**, plus full Claude migration and medium technical refactor.

The core insight: style loss on revision is an architectural problem, not a prompting problem. It cannot be fixed by tweaking prompt wording — it requires that the model have its own prior output in context when rewriting. This means replacing the stateless per-section API calls with a single persistent conversation thread for the entire article.

---

## Section 1: Model Strategy

All OpenAI calls are replaced with Claude. Models are selected per task based on cost/quality trade-off.

### Fast Model: `claude-haiku-4-5-20251001`
Used for mechanical, high-volume, or low-stakes tasks:

| Agent | Task |
|---|---|
| CoordinatorAgent | Query parsing, keyword extraction, search planning |
| DatabaseSearchAgent | Substack URL selection from CSV |
| ArticleRetrievalAgent | Article processing and fetching |
| AnalysisAgent | Relevance scoring (runs on every article) |
| YouTubeAgent | Video search and transcript filtering |
| SummarizationAgent | Research report generation |
| FactCheckerAgent | Contradiction detection per section |

### Quality Model: `claude-sonnet-4-6`
Used for tasks that directly affect final output quality:

| Agent | Task |
|---|---|
| StyleLearningAgent | Style card generation from writing samples |
| OutlineGeneratorAgent | Structural outline decisions |
| ArticleWriterAgent | All article generation and revision |
| OutlineFeedbackProcessor | Outline revision passes |

### Configuration
Model names are centralized in `config.py` as two constants:

```python
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_QUALITY_MODEL = "claude-sonnet-4-6"
```

All agents reference these constants — never hardcoded model strings. Swapping models in future requires changing one line each.

The existing `ANTHROPIC_TEST_MODEL` remains for `--test` mode, pointing to Haiku.

---

## Section 2: Multi-Turn Article Writing Pipeline

### Current Architecture (Stateless)

```
write_section(1) → [fresh API call, no memory] → output
user_revises(1)  → [fresh API call, no memory] → output
write_section(2) → [fresh API call, no memory] → output
```

Each call is independent. The model cannot calibrate its voice against what it already wrote.

### New Architecture (Stateful Conversation)

```
init_conversation(system_prompt=style_card + outline + research_summary)
    ↓
write_section(1) → appended to conversation → output
user_revises(1)  → appended to conversation → revised output  ← model sees everything
write_section(2) → appended to conversation → output          ← model has seen section 1
...
```

One conversation thread persists for the entire article session.

### Implementation

**`anthropic_client.py`** gains a `messages` parameter on its `generate()` method, accepting an accumulated message list. When provided, it appends the new user message and sends the full history.

**`ArticleWriterAgent`** becomes a stateful class:
- `__init__`: initializes an empty `self.conversation_history = []`
- `start_article(style_card, outline, research_summary)`: builds the system prompt, sets up the initial conversation context
- `write_section(section_title, relevant_sources)`: appends a user message requesting the section, calls the API with full history, appends the assistant response to history, returns the section text
- `revise_section(feedback, section_title)`: appends the user's revision feedback as the next message, calls the API with full history — the model sees every prior section and revision when rewriting

### What This Eliminates

- The regex-based section boundary detection in `feedback_processor.py` — sections are now discrete conversation turns with exact boundaries
- Style drift between sections — the model has its prior output in context
- Style loss on revision — the model sees the whole article when rewriting

### Conversation History Management

To avoid hitting context limits on very long articles, a summarization step compresses accepted sections older than 3 turns: their full text is replaced with a condensed "Section N was written and accepted — key points: [summary]" entry. This keeps the active context focused on recent sections while preserving style continuity.

---

## Section 3: Style Learning Redesign

### Current Approach

`StyleLearningAgent` reads writing samples and produces a prose paragraph describing tone, structure, and vocabulary. This description is insufficiently structured for reliable reproduction and is not re-injected on revision passes.

### New Approach: Structured Style Card

`claude-sonnet-4-6` analyzes the user's writing samples and `writing_instructions.txt` to produce a structured JSON style card:

```json
{
  "tone": "analytical but conversational, avoids hype and superlatives",
  "sentence_patterns": "mix of short punchy sentences and longer structured ones; frequent use of em-dashes for asides",
  "vocabulary": {
    "preferred": ["on-chain", "liquidity", "thesis", "catalysts"],
    "avoided": ["revolutionary", "game-changing", "massive", "huge"]
  },
  "paragraph_structure": "opens with a claim, supports with data or direct quote, closes with implication or question",
  "section_openings": "often starts with a question or a bold declarative assertion",
  "transitions": ["That said,", "But here's the thing,", "Which brings us to", "Worth noting:"],
  "example_excerpts": [
    "...3 to 5 direct verbatim quotes from the user's writing samples...",
    "...selected to show voice at its most characteristic..."
  ]
}
```

### Usage

- Generated **once** at session start by `StyleLearningAgent`
- Cached to `output/[query]/style_card.json` alongside article output
- Serialized to a formatted string and embedded verbatim in the system prompt of the multi-turn conversation
- The `example_excerpts` field provides concrete anchors — the model can match rhythm and phrasing, not just abstract descriptors
- `writing_instructions.txt` contents are folded into the style card generation prompt as explicit overrides, preserving the existing user-facing manual control

### Style Card System Prompt Format

The style card is formatted into the conversation system prompt as:

```
## Writing Style Guide

Tone: {tone}
Sentence patterns: {sentence_patterns}
Paragraph structure: {paragraph_structure}
Section openings: {section_openings}
Preferred transitions: {transitions}
Vocabulary to use: {preferred}
Vocabulary to avoid: {avoided}

## Example Excerpts from the Author's Writing

> {excerpt_1}

> {excerpt_2}

> {excerpt_3}

Match this voice precisely. Every section you write — including rewrites — must sound like these excerpts.
```

---

## Section 4: Technical Refactoring

### Logging (`utils/logger.py`)

Replace all `print()` calls with Python's `logging` module.

- `utils/logger.py` configures a root logger with two handlers:
  - Console handler at INFO level
  - Rotating file handler writing to `output/logs/agent.log` (10 MB max, 3 backups)
- Every agent module gets: `logger = logging.getLogger(__name__)`
- Log output includes the agent name automatically: `[analysis] Scoring article: Bitcoin ETF flows...`
- Debug-level logs for API calls (model, token counts, latency)
- No behavioral changes — purely observability improvement

### Token Management (`utils/token_utils.py`)

Replace all ad-hoc character limits (e.g., `article[:8000]`) with a shared utility.

```python
def truncate_to_token_limit(text: str, model: str, limit: int) -> str:
    """Truncate text to fit within token limit for the given model."""
```

- Uses `tiktoken` for accurate token counting
- Truncates at sentence boundaries where possible, never mid-word
- All agents that currently truncate content call this function instead
- Handles the different tokenizers for Haiku vs Sonnet correctly

### Error Handling (`utils/retry.py`)

Add a `@retry_on_rate_limit` decorator using exponential backoff.

```python
@retry_on_rate_limit(max_retries=3, base_delay=1.0, max_delay=60.0)
def generate(self, prompt, ...):
    ...
```

- Catches Anthropic `RateLimitError`, `OverloadedError`, and `APITimeoutError`
- Retries with exponential backoff: 1s, 2s, 4s (with jitter)
- Logs each retry attempt at WARNING level
- Raises after `max_retries` exhausted
- Applied at the `anthropic_client.py` level — all agents get it automatically without changes

### What Is NOT Changing

- Substack/YouTube discovery pipeline
- CLI interface and arguments
- Output file structure
- Outline feedback loop (works well)
- CloudConvert DOCX export
- `ArticleFilter` keyword filtering

---

## File Change Summary

### Modified Files
- `config.py` — replace model constants, add `CLAUDE_FAST_MODEL` / `CLAUDE_QUALITY_MODEL`
- `agents/anthropic_client.py` — add `messages` parameter for conversation history
- `agents/coordinator.py` — migrate from OpenAI to Claude Haiku
- `agents/database_search.py` — migrate from OpenAI to Claude Haiku
- `agents/article_retrieval.py` — migrate from OpenAI to Claude Haiku
- `agents/analysis.py` — migrate from OpenAI to Claude Haiku
- `agents/youtube_search.py` — migrate from OpenAI to Claude Haiku
- `agents/summarization.py` — migrate from OpenAI to Claude Haiku
- `agents/style_learning.py` — rewrite to produce structured style card JSON
- `agents/outline_generator.py` — migrate to Claude Sonnet, improve prompting
- `agents/article_writer.py` — full rewrite as stateful multi-turn conversation
- `agents/fact_checker.py` — migrate from OpenAI/mixed to Claude Haiku
- `agents/feedback_processor.py` — simplify (remove regex section detection, use conversation turns)
- `agents/outline_feedback.py` — migrate to Claude Sonnet

### New Files
- `utils/logger.py` — centralized logging setup
- `utils/token_utils.py` — tiktoken-based truncation utility
- `utils/retry.py` — `@retry_on_rate_limit` decorator

### Deleted/Removed
- All OpenAI imports and `openai` API calls across all agents
- `openai` dependency from `requirements.txt` (if no longer needed anywhere)

---

## Success Criteria

1. All agents use Claude models — no OpenAI API calls in production code
2. A revised article section sounds as close to the user's voice as the first-draft sections
3. Style card JSON is generated and saved for every run
4. Article conversation history is maintained across all sections and revisions
5. No `print()` statements remain in agent or utility code
6. All content truncation goes through `truncate_to_token_limit()`
7. Rate limit errors trigger automatic retry with backoff, not crashes
