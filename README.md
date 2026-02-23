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
  - [Fact Checking System](#fact-checking-system)
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
- Integrated fact-checking against source materials
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
- **Automated Fact Checking**: Verification of content accuracy against source materials
- **Document Support**: Processing of various file formats including Word documents
- **Social Media Integration**: Extraction and analysis of Twitter/X content

## System Architecture

### Agent Components

The system employs 12 specialized agent components that work together:

1. **Coordinator Agent**: Orchestrates the research workflow, plans approach strategies, and determines essential search terms
2. **Database Search Agent**: Searches Substack databases to identify potential content sources
3. **Article Retrieval Agent**: Fetches and processes articles from identified Substack sources
4. **Analysis Agent**: Evaluates content relevance and extracts key insights
5. **YouTube Agent**: Searches, retrieves transcripts, and analyzes YouTube content
6. **Summarization Agent**: Creates concise, structured reports of analyzed content
7. **Outline Generator Agent**: Builds coherent research outlines based on findings
8. **Style Learning Agent**: Analyzes your writing samples to capture your personal style
9. **Article Writer Agent**: Generates article sections following the outline, research data, and your style
10. **Fact Checker Agent**: Verifies the factual accuracy of generated content
11. **Feedback Processor**: Manages the interactive revision process for article sections
12. **Cloud Convert Client**: Handles file format conversions for document processing

### Utility Modules

Supporting the agents are specialized utility modules:

- **CSV Handler**: Processes data files containing Substack and YouTube information
- **Article Filter**: Filters content based on keyword matching and relevance
- **Web Scraper**: Extracts content from web pages
- **User Content Manager**: Integrates user-provided research materials
- **Directory Setup**: Creates and manages file/folder structures
- **Tweet Extractor**: Retrieves and processes content from Twitter/X
- **Logger**: Centralized logging with rotating file output (`output/logs/agent.log`) and console output
- **Token Utils**: Token-accurate content truncation using tiktoken
- **Retry**: Exponential backoff decorator for Anthropic API rate limit and overload errors

### AI Services Integration

The system leverages these AI services:

- **Anthropic API**: Powers all 12 agents using Claude models
  - `claude-haiku-4-5-20251001` — cost-efficient tasks: coordination, analysis, search, summarization, fact checking
  - `claude-sonnet-4-6` — quality-critical tasks: article writing, style card generation, outline generation
- **SupaData API**: Retrieves YouTube video transcripts
- **CloudConvert API**: Handles document format conversions

## Installation

### Prerequisites

- Python 3.7 or higher
- Anthropic API key
- SupaData API key (for YouTube transcript retrieval)
- CloudConvert API key (for document processing)

### Setup Steps

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/crypto-research-agent.git
   cd crypto-research-agent
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment file for API keys:
   ```
   cp .env.template .env
   ```
   Then edit `.env` to add your API keys.

4. Prepare the content databases:
   - Ensure `Substacks.csv` is in the input directory
   - Ensure `YouTubes.csv` is in the input directory
   - Templates for both files are provided in the repo

## Usage Guide

### Basic Commands

Run the agent with your research query:

```bash
python main.py "Your crypto research query" 
```

For example:
```bash
python main.py "Bitcoin ETF inflows"
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

### Fact Checking System

All generated content undergoes automatic fact checking:

1. **Claim Identification**: Each section is analyzed for factual statements
2. **Source Verification**: Claims are compared against research sources
3. **Accuracy Assessment**: Discrepancies or unsupported claims are identified
4. **Correction Application**: Any inaccuracies are automatically corrected
5. **Verification Reporting**: Results of fact checking are reported

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
python main.py "Ethereum Layer 2 scaling" --test --youtube
```

**Search mode with Substacks only:**
```bash
python main.py "DeFi yield farming" --search --substack
```

**Full research with thesis direction:**
```bash
python main.py "NFT market trends" --thesis "Focus on the relationship between NFT sales and overall crypto market conditions"
```

**Content age filtering:**
```bash
python main.py "Crypto regulations" --max-age 30
```

## Troubleshooting

- **API Key Issues**: Ensure `ANTHROPIC_API_KEY` and other keys are correctly set in your `.env` file
- **Content Database Problems**: Verify `Substacks.csv` and `YouTubes.csv` are properly formatted
- **Style Learning Failures**: Check that writing samples are in the correct directory and format
- **Rate Limit Errors**: The system automatically retries with exponential backoff — persistent failures indicate quota exhaustion
- **Long Articles**: For articles with many sections, the stateful conversation grows with each section; if you hit context limits, reduce the number of outline sections
- **Log Inspection**: Check `output/logs/agent.log` for detailed debug output from all agents

If you encounter persistent issues, check the console output for specific error messages or review the project documentation for updates.