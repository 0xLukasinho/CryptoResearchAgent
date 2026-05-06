# Crypto Research Agent System

A comprehensive multi-agent AI system that automates cryptocurrency research, content analysis, and article generation using a coordinated network of specialized intelligent agents.

## Table of Contents

- [System Overview](#system-overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
  - [Agent Components](#agent-components)
  - [Utility Modules](#utility-modules)
  - [AI Services Integration](#ai-services-integration)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup Steps](#setup-steps)
- [Usage Guide](#usage-guide)
  - [Basic Commands](#basic-commands)
  - [Command Line Arguments](#command-line-arguments)
  - [Operational Modes](#operational-modes)
- [Research Workflow](#research-workflow)
  - [Content Discovery Phase](#content-discovery-phase)
  - [Analysis and Synthesis Phase](#analysis-and-synthesis-phase)
- [Article Generation](#article-generation)
  - [Writing Style Personalization](#writing-style-personalization)
  - [Interactive Feedback Loop](#interactive-feedback-loop)
- [User Content Integration](#user-content-integration)
  - [Supported File Types](#supported-file-types)
  - [Tweet Integration](#tweet-integration)
- [Output Files](#output-files)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

## System Overview

The Crypto Research Agent System is designed to automate the entire workflow of researching cryptocurrency topics, from initial information gathering to creating publication-ready articles. It employs multiple specialized AI agents working in coordination to search through hundreds of resources, identify relevant content, analyze findings, and generate comprehensive research materials that match your personal writing style.

The system's core capabilities include:

- Automated information discovery across Substacks, YouTube, and user-provided materials
- Deep content analysis and relevance evaluation
- AI-powered research outline generation
- Full article creation with personalized writing style
- Interactive feedback and revision processing

## Key Features

- **Multi-Source Research**: Comprehensive search across Substack newsletters and YouTube videos
- **Content Filtering**: Efficient pre-filtering using required keywords to optimize processing
- **Deep Analysis**: Advanced content relevance evaluation and key insight extraction
- **User Content Integration**: Seamless incorporation of your own research materials
- **Thesis Direction**: Specification of research focus for targeted outcomes
- **Flexible Execution Modes**: Multiple operational modes (full research, search-only, test)
- **Age-Based Filtering**: Option to limit results to recent content only
- **Personalized Writing**: Article generation matching your personal writing style
- **Interactive Revision**: Real-time feedback and section-by-section article refinement
- **Document Support**: Processing of various file formats including Word documents
- **Social Media Integration**: Extraction and analysis of Twitter/X content

## System Architecture

The codebase lives under `src/crypto_research_agent/` and is organized into layered components.

### Real Agents (`src/crypto_research_agent/agents/`)

1. **Coordinator**: Plans the search — determines `main_topic` and required terms from the query
2. **Analyzer**: Evaluates each Article/Video for relevance, key insights, mentioned projects, thesis alignment; runs in batches with test-mode short-circuit
3. **Summarizer**: Builds the markdown research summary from analyzed High/Medium relevance items
4. **StyleLearner**: Loads writing samples (.txt/.docx) + instructions and generates a `StyleCard` capturing tone, vocabulary, transitions, example excerpts
5. **OutlineWriter**: Generates and revises markdown research outlines, integrating user content when present
6. **ArticleWriter**: Writes article sections one at a time via a stateful Conversation, supports per-section revision

### Services (`src/crypto_research_agent/services/`)

- **SubstackService**: Discovers + fetches Substack posts with pagination and age filtering
- **YouTubeService**: Channel discovery → playlist videos → Supadata transcripts; pure scoring/filter functions
- **DocxExporter**: CloudConvert lifecycle for Markdown → DOCX
- **TweetExtractor**: Playwright-driven tweet text extraction
- **UserContentService**: txt/md/pdf/csv ingestion with per-type size limits

### Pipeline Stages (`src/crypto_research_agent/pipeline/`)

- **DiscoveryStage**: Runs Substack/YouTube services, applies required-term pre-filter, then Analyzer
- **SynthesisStage**: Saves research summary, generates outline, drives outline review loop
- **WritingStage**: Persists style card, drives section-by-section writing + section review loop
- **PipelineRunner**: Top-level orchestrator owning the LLMRouter and stage builders

### LLM Layer (`src/crypto_research_agent/llm/`)

- **ClaudeCodeBackend**: Subprocess wrapper around `claude -p` (subscription billing)
- **AnthropicAPIBackend**: SDK-based fallback used on quota exhaustion
- **LLMRouter**: One-time fallback switch on quota errors, with user prompt for Opus/Sonnet/abort
- **Conversation**: Multi-turn wrapper using `--resume` session IDs for stateful article writing

### Utilities (`src/crypto_research_agent/utils/`)

- **logger**: Rotating file output (`output/logs/agent.log`) + console
- **token_utils**: tiktoken-based content truncation at sentence boundaries
- **filters**: Required-term and English-language pre-filters
- **paths**: Slug sanitization + timestamped output dir builder
- **outline_parser**: Parses markdown outlines into `{title, content}` sections
- **csv_loader**: Typed loaders for Substack URLs and YouTube channel CSVs

### AI Services Integration

The system leverages these AI services:

- **Claude (subscription)**: All LLM calls route through `claude -p` (the Claude Code CLI), billed against your Claude Max subscription
  - `claude-haiku-4-5-20251001` — cost-efficient tasks: coordination, analysis, summarization
  - `claude-opus-4-7` — quality-critical tasks: article writing, style card generation, outline generation
- **Anthropic API (fallback)**: Activated only on quota exhaustion mid-run; you choose Opus/Sonnet/abort
- **SupaData API**: Retrieves YouTube video transcripts
- **CloudConvert API**: Markdown → DOCX export
- **YouTube Data API**: Channel/video discovery

## Installation

### Prerequisites

- Python 3.13 or higher
- [Claude Code CLI](https://claude.com/claude-code) installed and authenticated (`claude setup-token`) — Claude Max subscription billing routes through this
- SupaData API key (for YouTube transcript retrieval)
- CloudConvert API key (for DOCX export)
- YouTube Data API key (for video discovery)
- Anthropic API key — *optional* fallback when subscription quota is exhausted mid-run

### Setup Steps

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/crypto-research-agent.git
   cd crypto-research-agent
   ```

2. Authenticate the Claude CLI for subscription billing:
   ```
   claude setup-token
   ```

3. Install the package in editable mode (uses `pyproject.toml`):
   ```
   pip install -e ".[dev]"
   ```
   This also registers a `crypto-research` console script.

4. Set up your environment file:
   ```
   cp .env.template .env
   ```
   Then edit `.env` to add the external API keys (Supadata, CloudConvert, YouTube). `ANTHROPIC_API_KEY` is optional — only needed if you want quota-fallback to the pay-per-token API.

5. Prepare the content databases:
   - Ensure `Substacks.csv` is in the `input/` directory
   - Ensure `YouTubes.csv` is in the `input/` directory
   - Templates for both files are provided in the repo

## Usage Guide

### Basic Commands

Run the agent with your research query (uses the `crypto-research` console script installed via `pip install -e ".[dev]"`):

```bash
crypto-research "Your crypto research query"
```

For example:
```bash
crypto-research "Bitcoin ETF inflows"
```

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--test` | Run in test mode (limited processing) |
| `--search` | Run in search mode (no outline/article generation) |
| `--youtube` | Search YouTube content only |
| `--substack` | Search Substacks content only |
| `--thesis "your thesis"` | Specify research focus direction |
| `--max-age N` | Only include content newer than N days |

### Operational Modes

1. **Full Research Mode** (default)
   - Complete workflow from content discovery to article generation
   - Includes all analysis, outline creation, and article writing steps

2. **Search-Only Mode** (`--search`)
   - Performs content discovery and analysis
   - Stops before outline and article generation
   - Useful for preliminary research or content discovery

3. **Test Mode** (`--test`)
   - Limits processing to a small subset of sources
   - Stops after finding a few relevant items per source
   - Useful for quickly validating research queries

## Research Workflow

### Content Discovery Phase

1. **Query Analysis**: The Coordinator Agent analyzes your research query
2. **Search Planning**: Essential search terms and strategies are determined
3. **Substack Search**: If enabled, searches through Substack newsletters
   - Database lookup to identify relevant Substacks
   - Article retrieval from identified sources
   - Keyword pre-filtering to focus on relevant content
4. **YouTube Search**: If enabled, searches through YouTube content
   - Channel and video discovery based on relevance
   - Transcript retrieval for in-depth analysis
   - Video content summarization with key points
5. **User Content Processing**: Integration of your provided materials
   - Analysis of text, PDF, CSV files you provide
   - Extraction of key insights from your materials

### Analysis and Synthesis Phase

1. **Content Analysis**: All collected materials are analyzed for relevance
   - Relevance scoring (High/Medium/Low)
   - Key insight extraction
   - Relationship identification between content pieces
2. **Research Organization**: Content is categorized and structured
   - Grouping by subtopics and themes
   - Prioritization based on relevance and quality
3. **Outline Generation**: A comprehensive research outline is created
   - Main sections and subsections identification
   - Source attribution for key points
   - Logical flow structure for the research

## Article Generation

### Writing Style Personalization

The system learns your writing style and embeds it in every section it writes and revises:

1. **Style Sample Collection**:
   - Place writing samples in `input/writing_samples/` directory
   - Supports plain text (.txt) and Word documents (.docx)
   - Add multiple samples for better style learning

2. **Writing Instructions**:
   - Edit `input/writing_instructions.txt` to specify preferences
   - Define tone, structure, terminology preferences
   - Set specific stylistic guidelines

3. **Structured Style Card**: The Style Learning Agent generates a JSON style card capturing:
   - Tone and personality characteristics
   - Sentence structure patterns
   - Vocabulary to use and avoid (word lists)
   - Paragraph structure conventions
   - Characteristic transition phrases
   - Verbatim example excerpts from your writing

   The style card is saved to `output/[query]/style_card.json` and embedded directly in the article writer's system prompt for every generation and revision call.

4. **Stateful Conversation**: The Article Writer maintains a single conversation thread for the entire article. Each section and revision is added to the same thread, so the model always has full context of what it previously wrote — preventing style drift across sections and on revision.

### Interactive Feedback Loop

The system enables section-by-section feedback and revision:

1. **Section Review**: After each section is generated, you review it
2. **Feedback Options**:
   - Accept: Move to the next section
   - Revise: Provide specific revision instructions
   - Edit: Make direct changes to the file
3. **Implementation**: The system applies your feedback
4. **Iteration**: The process continues until the article is complete

Example feedback interaction:
```
[FEEDBACK] Section 'Introduction' has been written.
Please review it in the article file: output/your_query/article.md

Options:
  1. Type 'accept' to proceed to the next section
  2. Type 'revise' followed by specific instructions
  3. Edit the file directly and then type 'edited'
```

## User Content Integration

### Supported File Types

You can integrate your own materials during research:

- **Text Files**: Plain text content (.txt)
- **Word Documents**: Microsoft Word files (.docx)
- **PDF Files**: Portable Document Format (.pdf)
- **CSV Files**: Tabular data in comma-separated format (.csv)
- **Tweet Collections**: Lists of Twitter/X URLs

The system will automatically process and analyze these materials based on file type.

### Tweet Integration

You can include tweet content in your research:

1. Create a file named `tweets.txt` in the user content directory
2. Add one tweet URL per line (Twitter/X URLs)
3. The system will extract the content of each tweet
4. Extracted tweets are saved and integrated into the research

Example tweets.txt file:
```
https://twitter.com/VitalikButerin/status/1822742098520416625
https://twitter.com/haydenzadams/status/1910816676628545930
```

## Output Files

The system generates these output files in a query-specific directory:

1. **Research Summary** (`research_results.md`)
   - Analyzed content from all sources
   - Relevance scoring and key insights

2. **Research Outline** (`outline.md`)
   - Structured outline incorporating all findings
   - Section and subsection organization

3. **Style Card** (`style_card.json`)
   - Structured JSON capturing your writing style
   - Embedded in every article generation and revision call

4. **Article** (`article.md`)
   - Complete, publication-ready article
   - Written in your personal style

5. **Word Document** (`article.docx`)
   - Microsoft Word version of the article (via CloudConvert)

6. **Agent Log** (`output/logs/agent.log`)
   - Rotating log file with debug-level output from all agents

7. **Tweet Content** (in `tweets/` subdirectory)
   - Individual files containing extracted tweets

## Usage Examples

**Test mode with YouTube only:**
```bash
crypto-research "Ethereum Layer 2 scaling" --test --youtube
```

**Search mode with Substacks only:**
```bash
crypto-research "DeFi yield farming" --search --substack
```

**Full research with thesis direction:**
```bash
crypto-research "NFT market trends" --thesis "Focus on the relationship between NFT sales and overall crypto market conditions"
```

**Content age filtering:**
```bash
crypto-research "Crypto regulations" --max-age 30
```

## Troubleshooting

- **`claude` CLI not found**: Install [Claude Code](https://claude.com/claude-code) and run `claude setup-token`. Verify with `claude -p "ping"`
- **Subscription quota exhausted mid-run**: The pipeline will prompt you to continue via the Anthropic API (Opus/Sonnet) if `ANTHROPIC_API_KEY` is set, or abort
- **External API key issues**: Ensure `SUPADATA_API_KEY`, `CLOUDCONVERT_API_KEY`, `YOUTUBE_API_KEY` are set in `.env`
- **Content Database Problems**: Verify `Substacks.csv` and `YouTubes.csv` are properly formatted
- **Style Learning Failures**: Check that writing samples are in `input/writing_samples/` and are .txt or .docx
- **Long Articles**: For articles with many sections, the stateful conversation grows with each section; if you hit context limits, reduce the number of outline sections
- **Log Inspection**: Check `output/logs/agent.log` for detailed debug output

If you encounter persistent issues, check the console output for specific error messages or review the project documentation for updates.