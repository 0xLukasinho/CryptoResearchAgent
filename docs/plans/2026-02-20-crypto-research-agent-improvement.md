# CryptoResearchAgent Improvement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all agents from OpenAI to Claude (Haiku for research, Sonnet for writing), build a stateful multi-turn article writing pipeline that eliminates style drift, and implement a structured JSON style card embedded in every generation and revision call.

**Architecture:** Replace 8 OpenAI agents with `ClaudeAgentBase` (Haiku); rewrite `ArticleWriterAgent` as a single persistent conversation thread so the model always has its own prior output in context when writing or revising; generate a structured JSON style card once per session and embed it verbatim in every system prompt; replace regex section boundary detection with discrete conversation turns; add centralized logging, token utils, and retry decorator.

**Tech Stack:** Python 3.x, `anthropic>=0.49.0`, `tiktoken`, Python `logging`, existing agent architecture. No new external dependencies.

---

## Task 1: Create utils/logger.py

**Files:**
- Create: `utils/logger.py`
- Create: `tests/utils/test_logger.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_logger.py
import logging
import sys
sys.path.insert(0, '.')
from utils.logger import get_logger

def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"

def test_get_logger_has_handlers():
    get_logger("test_handlers")
    root = logging.getLogger()
    assert len(root.handlers) > 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/utils/test_logger.py -v`
Expected: `ModuleNotFoundError: No module named 'utils.logger'`

**Step 3: Write implementation**

```python
# utils/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configure root logger with console and rotating file handlers."""
    root = logging.getLogger()
    if root.handlers:
        return  # Already configured

    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    root.addHandler(console)

    os.makedirs("output/logs", exist_ok=True)
    file_handler = RotatingFileHandler(
        "output/logs/agent.log", maxBytes=10 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger, setting up logging if not already done."""
    setup_logging()
    return logging.getLogger(name)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/utils/test_logger.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add utils/logger.py tests/utils/test_logger.py tests/__init__.py tests/utils/__init__.py tests/agents/__init__.py
git commit -m "feat: add centralized logging utility"
```

---

## Task 2: Create utils/token_utils.py

**Files:**
- Create: `utils/token_utils.py`
- Create: `tests/utils/test_token_utils.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_token_utils.py
import sys
sys.path.insert(0, '.')
from utils.token_utils import truncate_to_token_limit

def test_short_text_unchanged():
    text = "Hello world. This is a short sentence."
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 1000)
    assert result == text

def test_long_text_gets_truncated():
    text = "This is a sentence. " * 500
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 100)
    assert len(result) < len(text)

def test_truncated_text_fits_limit():
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    text = "word " * 2000
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 200)
    assert len(enc.encode(result)) <= 200
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/utils/test_token_utils.py -v`
Expected: `ModuleNotFoundError: No module named 'utils.token_utils'`

**Step 3: Write implementation**

```python
# utils/token_utils.py
import tiktoken

# Claude models use the same tokenizer as GPT-4
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def truncate_to_token_limit(text: str, model: str, limit: int) -> str:
    """
    Truncate text to fit within a token limit, preferring sentence boundaries.

    Args:
        text: Text to truncate
        model: Model name (reserved for future model-specific tokenizers)
        limit: Maximum number of tokens

    Returns:
        Truncated text that fits within the token limit
    """
    tokens = _TOKENIZER.encode(text)
    if len(tokens) <= limit:
        return text

    truncated = _TOKENIZER.decode(tokens[:limit])

    # Try to end at a sentence boundary in the latter 30% of the text
    for delimiter in ('. ', '.\n', '? ', '! '):
        pos = truncated.rfind(delimiter)
        if pos > len(truncated) * 0.7:
            return truncated[:pos + 1]

    return truncated
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/utils/test_token_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add utils/token_utils.py tests/utils/test_token_utils.py
git commit -m "feat: add tiktoken-based token truncation utility"
```

---

## Task 3: Create utils/retry.py

**Files:**
- Create: `utils/retry.py`
- Create: `tests/utils/test_retry.py`

**Step 1: Write the failing test**

```python
# tests/utils/test_retry.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock
import anthropic
from utils.retry import retry_on_rate_limit


def test_succeeds_on_first_try():
    call_count = [0]

    @retry_on_rate_limit(max_retries=3, base_delay=0.01)
    def my_func():
        call_count[0] += 1
        return "success"

    assert my_func() == "success"
    assert call_count[0] == 1


def test_retries_on_rate_limit_error():
    call_count = [0]

    @retry_on_rate_limit(max_retries=3, base_delay=0.01)
    def my_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise anthropic.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429, headers={}),
                body={}
            )
        return "success"

    assert my_func() == "success"
    assert call_count[0] == 3


def test_raises_after_max_retries():
    call_count = [0]

    @retry_on_rate_limit(max_retries=2, base_delay=0.01)
    def my_func():
        call_count[0] += 1
        raise anthropic.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429, headers={}),
            body={}
        )

    try:
        my_func()
        assert False, "Should have raised"
    except anthropic.RateLimitError:
        pass
    assert call_count[0] == 3  # 1 initial + 2 retries
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/utils/test_retry.py -v`
Expected: `ModuleNotFoundError: No module named 'utils.retry'`

**Step 3: Write implementation**

```python
# utils/retry.py
import time
import random
import functools
import anthropic
from utils.logger import get_logger

logger = get_logger("retry")


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """
    Decorator that retries a function on Anthropic API rate limit or overload errors.
    Uses exponential backoff with jitter.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APITimeoutError) as e:
                    last_exc = e
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    logger.warning(
                        f"API error on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/utils/test_retry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add utils/retry.py tests/utils/test_retry.py
git commit -m "feat: add exponential backoff retry decorator for Anthropic API errors"
```

---

## Task 4: Update config.py — replace OpenAI constants with Claude model constants

**Files:**
- Modify: `config.py`

**Step 1: Read current config.py** (already done — it's at the project root)

**Step 2: Apply these changes to config.py**

Remove these lines:
```python
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
FACT_CHECKING_MODEL = "gpt-4o-mini"
MODEL = "gpt-4o-mini"
```

Replace the Anthropic model lines (lines 17–18) with:
```python
# Claude model constants — change these to upgrade all agents at once
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"    # Cost-efficient: coordination, analysis, search
CLAUDE_QUALITY_MODEL = "claude-sonnet-4-6"          # High quality: writing, outlines, style

# Keep ANTHROPIC_MODEL pointing to quality model for backward compat with AnthropicClient
ANTHROPIC_MODEL = CLAUDE_QUALITY_MODEL
ANTHROPIC_TEST_MODEL = CLAUDE_FAST_MODEL  # Test mode uses fast model
```

Also update these two lines:
```python
# Before:
OUTLINE_MODEL = ANTHROPIC_MODEL
OUTLINE_TEST_MODEL = ANTHROPIC_TEST_MODEL

# After (no change needed — they derive from ANTHROPIC_MODEL which now points to CLAUDE_QUALITY_MODEL)
# But add explicit constants for clarity:
OUTLINE_MODEL = CLAUDE_QUALITY_MODEL
OUTLINE_TEST_MODEL = CLAUDE_FAST_MODEL
```

**Step 3: Verify config loads without error**

Run: `python -c "from config import CLAUDE_FAST_MODEL, CLAUDE_QUALITY_MODEL; print(CLAUDE_FAST_MODEL, CLAUDE_QUALITY_MODEL)"`
Expected: `claude-haiku-4-5-20251001 claude-sonnet-4-6`

**Step 4: Commit**

```bash
git add config.py
git commit -m "feat: replace OpenAI model constants with CLAUDE_FAST_MODEL and CLAUDE_QUALITY_MODEL"
```

---

## Task 5: Update anthropic_client.py — add generate_with_history() and logging

**Files:**
- Modify: `agents/anthropic_client.py`
- Create: `tests/agents/test_anthropic_client.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_anthropic_client.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock, patch


def make_mock_response(text="test response"):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


def test_generate_with_history_passes_full_message_list():
    with patch('agents.anthropic_client.anthropic') as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_response("reply")

        from agents.anthropic_client import AnthropicClient
        client = AnthropicClient()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        result = client.generate_with_history(messages, system_prompt="Be helpful")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"] == messages
        assert call_kwargs["system"] == "Be helpful"
        assert result == "reply"


def test_generate_with_history_uses_quality_model_by_default():
    with patch('agents.anthropic_client.anthropic') as mock_anthropic:
        from config import CLAUDE_QUALITY_MODEL
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_response()

        from agents.anthropic_client import AnthropicClient
        client = AnthropicClient()
        client.generate_with_history([{"role": "user", "content": "test"}])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == CLAUDE_QUALITY_MODEL
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_anthropic_client.py -v`
Expected: `AttributeError: 'AnthropicClient' object has no attribute 'generate_with_history'`

**Step 3: Add generate_with_history() to AnthropicClient**

At the top of `agents/anthropic_client.py`, add after the existing imports:
```python
from utils.logger import get_logger
logger = get_logger(__name__)
```

Replace all `print(...)` calls in the file with `logger.info(...)` or `logger.error(...)`.

Add this method after `generate_content()` (after line 58):
```python
def generate_with_history(self, messages, system_prompt="", max_tokens=4000, model_override=None):
    """
    Generate content using a full conversation history (multi-turn).

    Args:
        messages (list): List of {"role": "user"/"assistant", "content": str} dicts
        system_prompt (str): System instructions for Claude
        max_tokens (int): Maximum tokens to generate
        model_override (str): Override the default model for this call

    Returns:
        str: Generated content from Claude
    """
    model_to_use = model_override if model_override else self.model
    try:
        message = self.client.messages.create(
            model=model_to_use,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages
        )
        return message.content[0].text
    except Exception as e:
        logger.error(f"Error generating content with history: {e}")
        return f"Error: {str(e)}"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/test_anthropic_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/anthropic_client.py tests/agents/test_anthropic_client.py
git commit -m "feat: add generate_with_history() to AnthropicClient for stateful conversations"
```

---

## Task 6: Create agents/claude_agent_base.py — shared base for Haiku agents

**Files:**
- Create: `agents/claude_agent_base.py`
- Create: `tests/agents/test_claude_agent_base.py`

This base class replaces the OpenAI boilerplate in 8 agents. All migrated agents inherit from it.

**Step 1: Write the failing test**

```python
# tests/agents/test_claude_agent_base.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock, patch


def test_complete_json_parses_valid_json():
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = '{"key": "value", "num": 42}'

        from agents.claude_agent_base import ClaudeAgentBase
        agent = ClaudeAgentBase()
        result = agent.complete_json("prompt", "system")
        assert result == {"key": "value", "num": 42}


def test_complete_json_extracts_json_from_messy_response():
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = 'Here is the JSON:\n{"key": "value"}\nDone.'

        from agents.claude_agent_base import ClaudeAgentBase
        agent = ClaudeAgentBase()
        result = agent.complete_json("prompt", "system")
        assert result == {"key": "value"}


def test_complete_json_returns_empty_dict_on_failure():
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = "This is not JSON at all."

        from agents.claude_agent_base import ClaudeAgentBase
        agent = ClaudeAgentBase()
        result = agent.complete_json("prompt", "system")
        assert result == {}
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_claude_agent_base.py -v`
Expected: `ModuleNotFoundError: No module named 'agents.claude_agent_base'`

**Step 3: Write implementation**

```python
# agents/claude_agent_base.py
import json
import re
import sys
sys.path.append('..')
from agents.anthropic_client import AnthropicClient
from config import CLAUDE_FAST_MODEL
from utils.logger import get_logger
from utils.retry import retry_on_rate_limit


class ClaudeAgentBase:
    """
    Base class for agents using Claude Haiku for cost-efficient tasks.
    Provides JSON completion, retry handling, and structured logging.
    Subclasses can override self.model to use a different model.
    """

    def __init__(self, test_mode=False):
        self.client = AnthropicClient(test_mode=test_mode)
        self.model = CLAUDE_FAST_MODEL
        self.logger = get_logger(self.__class__.__name__)

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def complete(self, prompt: str, system_prompt: str = "", max_tokens: int = 2000) -> str:
        """Generate a text response."""
        return self.client.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            model_override=self.model
        )

    def complete_json(self, prompt: str, system_prompt: str = "", max_tokens: int = 2000) -> dict:
        """
        Generate a JSON response, parsing and returning as a dict.
        Appends a strict JSON-only instruction to the system prompt.
        """
        json_system = (
            system_prompt
            + "\n\nYou MUST respond with valid JSON only. "
            "No explanation, no markdown fences, no commentary. Just the raw JSON object."
        )
        response = self.complete(prompt, json_system, max_tokens)

        # Direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Extract JSON object from mixed response
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        self.logger.error(f"Failed to parse JSON response: {response[:200]}")
        return {}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/test_claude_agent_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/claude_agent_base.py tests/agents/test_claude_agent_base.py
git commit -m "feat: add ClaudeAgentBase for shared Haiku agent boilerplate"
```

---

## Task 7: Migrate CoordinatorAgent to Claude

**Files:**
- Modify: `agents/coordinator.py`
- Create: `tests/agents/test_coordinator.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_coordinator.py
import sys
sys.path.insert(0, '.')
import inspect


def test_coordinator_has_no_openai():
    import agents.coordinator as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source


def test_coordinator_ask_returns_json_string():
    from unittest.mock import MagicMock, patch
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = '{"main_topic": "Bitcoin", "keywords": ["Bitcoin"], "required_terms": ["Bitcoin"], "subtopics": [], "search_strategy": "test", "competing_projects": []}'

        from agents.coordinator import CoordinatorAgent
        agent = CoordinatorAgent()
        result = agent.ask("Bitcoin ETF")
        assert result is not None
        assert "Bitcoin" in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_coordinator.py::test_coordinator_has_no_openai -v`
Expected: FAIL

**Step 3: Rewrite coordinator.py**

```python
# agents/coordinator.py
import json
import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase


class CoordinatorAgent(ClaudeAgentBase):

    def ask(self, query: str) -> str:
        """
        Process the user's research query and return a structured JSON plan string.

        Returns JSON with: main_topic, subtopics, keywords, search_strategy,
        required_terms, competing_projects
        """
        system = """You are the Coordinator Agent orchestrating a crypto research workflow.
Analyze the user's research request and extract key information.

You MUST respond with valid JSON containing:
- main_topic: The primary cryptocurrency or blockchain topic
- subtopics: List of related subtopics to explore
- keywords: List of important keywords for searching
- search_strategy: Brief explanation of search approach
- required_terms: Terms STRICTLY from the user's query — never add extras not in the query
- competing_projects: Major competing projects that would be OFF-TOPIC if they are the main subject"""

        result = self.complete_json(query, system, max_tokens=1000)
        return json.dumps(result)

    def synthesize_final_results(self, analysis_results: str) -> str:
        """Synthesize final results from all agents into a readable report."""
        prompt = f"""Based on the crypto research results, create a final comprehensive report.

Analysis Results:
{analysis_results}

Format the report with:
1. An executive summary of key findings
2. A categorized list of the most relevant articles
3. Brief highlights of the most important insights
4. Suggestions for further research"""

        system = "You are the Coordinator Agent synthesizing research results into a clear, actionable report."
        return self.complete(prompt, system, max_tokens=2000)
```

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_coordinator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/coordinator.py tests/agents/test_coordinator.py
git commit -m "feat: migrate CoordinatorAgent from OpenAI to Claude Haiku"
```

---

## Task 8: Migrate AnalysisAgent to Claude

**Files:**
- Modify: `agents/analysis.py`
- Create: `tests/agents/test_analysis.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_analysis.py
import sys
sys.path.insert(0, '.')
import inspect


def test_analysis_has_no_openai():
    import agents.analysis as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source


def test_analyze_article_returns_dict_with_expected_keys():
    from unittest.mock import MagicMock, patch
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = '''{
            "relevance_score": "High",
            "relevance_explanation": "Very relevant",
            "key_insights": ["Insight 1"],
            "mentioned_projects": ["Bitcoin"],
            "thesis_alignment": "Not Applicable",
            "thesis_alignment_explanation": "No thesis"
        }'''

        from agents.analysis import AnalysisAgent
        agent = AnalysisAgent()
        article = {
            "title": "Bitcoin ETF News", "text": "Bitcoin ETF approved by SEC...",
            "author": "Author", "date": "2024-01-01", "url": "http://example.com"
        }
        result = agent.analyze_article(article, '{"main_topic": "Bitcoin"}')
        assert result is not None
        assert result['relevance_score'] == 'High'
        assert result['title'] == 'Bitcoin ETF News'
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_analysis.py::test_analysis_has_no_openai -v`
Expected: FAIL

**Step 3: Rewrite analysis.py**

```python
# agents/analysis.py
import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase
from utils.token_utils import truncate_to_token_limit
from config import CLAUDE_FAST_MODEL


class AnalysisAgent(ClaudeAgentBase):

    def analyze_article(self, article: dict, search_plan: str, thesis_direction: str = None) -> dict:
        """Analyze a single article for relevance and key insights."""
        title = article.get('title', 'Unknown Title')
        date = article.get('date', 'Unknown Date')
        author = article.get('author', 'Unknown Author')
        text = article.get('text', '')
        url = article.get('url', '')

        # Use token-accurate truncation instead of hardcoded char count
        text_sample = truncate_to_token_limit(text, CLAUDE_FAST_MODEL, 1500)
        thesis_info = f"\nThesis Direction: {thesis_direction}" if thesis_direction else ""

        prompt = f"""Analyze this crypto article for relevance.

Search Plan: {search_plan}{thesis_info}

Article:
Title: {title}
Author: {author}
Date: {date}
URL: {url}

Text:
{text_sample}

CRITICAL: First check if the article is in English.
- If NOT in English, return ONLY: {{"non_english": true, "language_detected": "language name"}}
- If in English, return JSON with keys: relevance_score (High/Medium/Low), relevance_explanation, key_insights (list of strings), mentioned_projects (list), thesis_alignment (High/Medium/Low/Not Applicable), thesis_alignment_explanation

Relevance scoring: High = article is directly about the topic with substantial info. Medium = topic is present but not main focus. Low = only mentioned in passing or primarily about competing projects."""

        system = "You are an Article Analysis Agent evaluating crypto content. Respond with valid JSON only."
        result = self.complete_json(prompt, system, max_tokens=800)

        if not result:
            return {
                'title': title, 'author': author, 'date': date, 'url': url,
                'relevance_score': 'Error', 'relevance_explanation': 'Analysis failed',
                'key_insights': [], 'mentioned_projects': [],
                'thesis_alignment': 'Error', 'thesis_alignment_explanation': 'Analysis failed'
            }

        if result.get('non_english'):
            self.logger.info(f"Discarding non-English article: '{title}' ({result.get('language_detected', 'unknown')})")
            return None

        result.update({'title': title, 'author': author, 'date': date, 'url': url})

        # When thesis provided, use thesis alignment as the relevance score
        if thesis_direction and result.get('thesis_alignment') not in ('Not Applicable', 'Error', None):
            result['relevance_score'] = result['thesis_alignment']

        return result

    def analyze_articles(self, articles: list, search_plan: str, thesis_direction: str = None, test_mode: bool = False) -> list:
        """Analyze multiple articles for relevance."""
        analyzed = []
        relevant_count = 0

        for i, article in enumerate(articles):
            self.logger.info(f"Analyzing article {i+1}/{len(articles)}: {article.get('title', 'Unknown')}")
            result = self.analyze_article(article, search_plan, thesis_direction)

            if result is not None:
                analyzed.append(result)
                if test_mode and result.get('relevance_score') in ('High', 'Medium'):
                    relevant_count += 1
                    if relevant_count >= 2:
                        self.logger.info(f"Test mode: found {relevant_count} relevant articles, stopping early")
                        break

        return analyzed
```

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/analysis.py tests/agents/test_analysis.py
git commit -m "feat: migrate AnalysisAgent from OpenAI to Claude Haiku, use token_utils for truncation"
```

---

## Task 9: Migrate DatabaseSearchAgent, ArticleRetrievalAgent, SummarizationAgent, FactCheckerAgent

These four agents all share the same OpenAI migration pattern. Read each file before editing to preserve exact method signatures that `main.py` calls.

**Files:**
- Modify: `agents/database_search.py`
- Modify: `agents/article_retrieval.py`
- Modify: `agents/summarization.py`
- Modify: `agents/fact_checker.py`
- Create: `tests/agents/test_batch_migration.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_batch_migration.py
import sys
sys.path.insert(0, '.')
import inspect
import importlib


def _has_no_openai(module_path):
    mod = importlib.import_module(module_path)
    source = inspect.getsource(mod)
    return 'from openai' not in source and 'OpenAI(' not in source


def test_database_search_uses_claude():
    assert _has_no_openai('agents.database_search')

def test_article_retrieval_uses_claude():
    assert _has_no_openai('agents.article_retrieval')

def test_summarization_uses_claude():
    assert _has_no_openai('agents.summarization')

def test_fact_checker_uses_claude():
    assert _has_no_openai('agents.fact_checker')
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_batch_migration.py -v`
Expected: 4 FAIL

**Step 3: Migration pattern to apply to each file**

For each of the four files, apply this pattern:

1. **Read the file first** to understand its method signatures
2. Remove `from openai import OpenAI` and `from config import OPENAI_API_KEY, MODEL`
3. Add `from agents.claude_agent_base import ClaudeAgentBase`
4. Change `class X:` to `class X(ClaudeAgentBase):`
5. Remove `self.client = OpenAI(api_key=OPENAI_API_KEY)` and `self.model = MODEL` from `__init__`
6. Replace `self.client.chat.completions.create(model=self.model, messages=msgs, response_format={"type": "json_object"})` calls with `self.complete_json(prompt, system_prompt)` — extract `prompt` from the user message and `system_prompt` from the system message in `msgs`
7. Replace `self.client.chat.completions.create(model=self.model, messages=msgs)` with `self.complete(prompt, system_prompt)`
8. Replace all `print(...)` with `self.logger.info(...)`

**For `fact_checker.py` specifically:**
- It currently calls `anthropic_client.check_facts()` from `AnthropicClient`
- After migration, make `FactCheckerAgent` inherit `ClaudeAgentBase` and call `self.complete_json()` directly
- Preserve the `check_section()` and `suggest_corrections()` method signatures (called by `main.py`)
- The `check_section()` logic is essentially the same as `AnthropicClient.check_facts()` — consolidate into the agent

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_batch_migration.py -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add agents/database_search.py agents/article_retrieval.py agents/summarization.py agents/fact_checker.py tests/agents/test_batch_migration.py
git commit -m "feat: migrate DatabaseSearch, ArticleRetrieval, Summarization, FactChecker to Claude Haiku"
```

---

## Task 10: Migrate YouTubeAgent to Claude

**Files:**
- Modify: `agents/youtube_search.py`
- Create: `tests/agents/test_youtube_migration.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_youtube_migration.py
import sys
sys.path.insert(0, '.')
import inspect


def test_youtube_agent_has_no_openai():
    import agents.youtube_search as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_youtube_migration.py -v`
Expected: FAIL

**Step 3: Migrate youtube_search.py**

Read `agents/youtube_search.py` first. Apply the same migration pattern from Task 9. Preserve all method signatures.

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_youtube_migration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/youtube_search.py tests/agents/test_youtube_migration.py
git commit -m "feat: migrate YouTubeAgent from OpenAI to Claude Haiku"
```

---

## Task 11: Migrate OutlineGeneratorAgent to use Claude quality model constants

**Files:**
- Modify: `agents/outline_generator.py`
- Modify: `agents/outline_feedback.py`
- Create: `tests/agents/test_outline_migration.py`

Note: `outline_generator.py` already uses `AnthropicClient` — it just has a dead OpenAI import and uses old model constant names.

**Step 1: Write the failing test**

```python
# tests/agents/test_outline_migration.py
import sys
sys.path.insert(0, '.')
import inspect


def test_outline_generator_has_no_openai_import():
    import agents.outline_generator as mod
    source = inspect.getsource(mod)
    assert 'from openai import OpenAI' not in source


def test_outline_generator_uses_quality_model_constant():
    import agents.outline_generator as mod
    source = inspect.getsource(mod)
    assert 'CLAUDE_QUALITY_MODEL' in source


def test_outline_feedback_has_no_openai():
    import agents.outline_feedback as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agents/test_outline_migration.py -v`
Expected: FAIL

**Step 3: Update outline_generator.py**

- Remove `from openai import OpenAI` (line 1 — it was never used, a leftover)
- Remove `from config import OPENAI_API_KEY, OUTLINE_MODEL, OUTLINE_TEST_MODEL` and replace with `from config import CLAUDE_QUALITY_MODEL, CLAUDE_FAST_MODEL`
- Update `__init__`: `self.model = CLAUDE_FAST_MODEL if test_mode else CLAUDE_QUALITY_MODEL`
- Add `from utils.logger import get_logger` and `logger = get_logger(__name__)`
- Replace all `print(...)` with `logger.info(...)`
- Update the `generate_content` call to pass `model_override=self.model`

**Step 4: Update outline_feedback.py**

Read `agents/outline_feedback.py` first. It uses OpenAI. Apply the ClaudeAgentBase migration pattern, but **override the model to use `CLAUDE_QUALITY_MODEL`** in `__init__`:

```python
from agents.claude_agent_base import ClaudeAgentBase
from config import CLAUDE_QUALITY_MODEL

class OutlineFeedbackProcessor(ClaudeAgentBase):
    def __init__(self, test_mode=False):
        super().__init__(test_mode)
        self.model = CLAUDE_QUALITY_MODEL  # Outline revisions need quality model
```

**Step 5: Run tests**

Run: `python -m pytest tests/agents/test_outline_migration.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add agents/outline_generator.py agents/outline_feedback.py tests/agents/test_outline_migration.py
git commit -m "feat: migrate OutlineGenerator and OutlineFeedback to Claude quality model constants"
```

---

## Task 12: Rewrite StyleLearningAgent — generate structured style card

**Files:**
- Modify: `agents/style_learning.py`
- Create: `tests/agents/test_style_learning.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_style_learning.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock, patch
import json


def test_generate_style_card_returns_dict_with_required_keys():
    with patch('agents.anthropic_client.anthropic') as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        style_card_json = json.dumps({
            "tone": "analytical",
            "sentence_patterns": "mix of short and long",
            "vocabulary": {"preferred": ["on-chain"], "avoided": ["massive"]},
            "paragraph_structure": "claim, evidence, implication",
            "section_openings": "questions or bold assertions",
            "transitions": ["That said,"],
            "example_excerpts": ["Example excerpt one."]
        })
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=style_card_json)]
        )

        from agents.style_learning import StyleLearningAgent
        agent = StyleLearningAgent()
        style_materials = {
            'samples': [{'filename': 'sample.txt', 'content': 'My writing sample here.'}],
            'instructions': 'Be concise.'
        }
        card = agent.generate_style_card(style_materials)

        assert isinstance(card, dict)
        assert 'tone' in card
        assert 'example_excerpts' in card
        assert isinstance(card['example_excerpts'], list)


def test_format_style_card_for_prompt_returns_formatted_string():
    from agents.style_learning import StyleLearningAgent
    agent = StyleLearningAgent()
    card = {
        "tone": "analytical but conversational",
        "sentence_patterns": "short and punchy",
        "vocabulary": {"preferred": ["on-chain"], "avoided": ["massive"]},
        "paragraph_structure": "claim then evidence",
        "section_openings": "bold assertions",
        "transitions": ["That said,"],
        "example_excerpts": ["Sample excerpt here. This shows the voice."]
    }
    result = agent.format_style_card_for_prompt(card)
    assert "analytical but conversational" in result
    assert "Sample excerpt here." in result
    assert "## Writing Style Guide" in result
    assert "Vocabulary to avoid" in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_style_learning.py -v`
Expected: `AttributeError: 'StyleLearningAgent' object has no attribute 'generate_style_card'`

**Step 3: Add generate_style_card() and format_style_card_for_prompt() to StyleLearningAgent**

At the top of `agents/style_learning.py`, add these imports after the existing ones:
```python
import json
import re
from agents.anthropic_client import AnthropicClient
from config import CLAUDE_QUALITY_MODEL
from utils.logger import get_logger
from utils.token_utils import truncate_to_token_limit
```

Update `__init__` to add:
```python
self.anthropic_client = AnthropicClient()
self.logger = get_logger(__name__)
```

Replace all `print(...)` with `self.logger.info(...)`.

Add these two methods to the class:

```python
def generate_style_card(self, style_materials: dict) -> dict:
    """
    Generate a structured JSON style card from writing samples and instructions.
    Called once per session; result is cached and embedded in every generation prompt.

    Args:
        style_materials: dict with 'samples' (list of {filename, content}) and
                         'instructions' (str or None from writing_instructions.txt)

    Returns:
        dict with keys: tone, sentence_patterns, vocabulary, paragraph_structure,
                        section_openings, transitions, example_excerpts
    """
    samples = style_materials.get('samples', [])
    instructions = style_materials.get('instructions', '')

    samples_text = ""
    for sample in samples:
        content = truncate_to_token_limit(sample.get('content', ''), CLAUDE_QUALITY_MODEL, 3000)
        samples_text += f"\n--- {sample.get('filename', 'sample')} ---\n{content}\n"

    instructions_section = (
        f"\nExplicit writing instructions from the author:\n{instructions}"
        if instructions else ""
    )

    prompt = f"""Analyze these writing samples and produce a structured style card that captures the author's voice precisely.

{samples_text}{instructions_section}

Return a JSON object with exactly these keys:
- "tone": string describing overall tone (e.g. "analytical but conversational, avoids hype")
- "sentence_patterns": string describing sentence structure patterns
- "vocabulary": object with "preferred" (list of characteristic words/phrases) and "avoided" (list of words to avoid)
- "paragraph_structure": string describing how paragraphs are typically structured
- "section_openings": string describing how sections typically begin
- "transitions": list of characteristic transition phrases used by this author
- "example_excerpts": list of 3-5 verbatim excerpts that best represent the author's voice at its most characteristic

Focus on what makes this voice distinctive and reproducible."""

    system = (
        "You are a writing style analyst. Extract precise, actionable style characteristics "
        "from writing samples. Respond with valid JSON only."
    )

    response = self.anthropic_client.generate_content(
        prompt=prompt,
        system_prompt=system,
        max_tokens=2000,
        model_override=CLAUDE_QUALITY_MODEL
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    self.logger.error("Failed to parse style card JSON, using fallback")
    return {
        "tone": "analytical and informative",
        "sentence_patterns": "clear and direct",
        "vocabulary": {"preferred": [], "avoided": []},
        "paragraph_structure": "structured with clear points",
        "section_openings": "direct assertions",
        "transitions": [],
        "example_excerpts": []
    }


def format_style_card_for_prompt(self, style_card: dict) -> str:
    """
    Format a style card dict into a string for embedding in system prompts.

    Args:
        style_card: dict from generate_style_card()

    Returns:
        str: Formatted style guide ready for system prompt injection
    """
    vocab = style_card.get('vocabulary', {})
    preferred = ', '.join(vocab.get('preferred', [])) or 'none specified'
    avoided = ', '.join(vocab.get('avoided', [])) or 'none specified'
    transitions = ', '.join(f'"{t}"' for t in style_card.get('transitions', [])) or 'none specified'

    excerpts_text = ""
    for excerpt in style_card.get('example_excerpts', []):
        excerpts_text += f"\n> {excerpt}\n"

    return f"""## Writing Style Guide

**Tone:** {style_card.get('tone', '')}
**Sentence patterns:** {style_card.get('sentence_patterns', '')}
**Paragraph structure:** {style_card.get('paragraph_structure', '')}
**Section openings:** {style_card.get('section_openings', '')}
**Preferred transitions:** {transitions}
**Vocabulary to use:** {preferred}
**Vocabulary to avoid:** {avoided}

## Example Excerpts from the Author's Writing
{excerpts_text}
Match this voice precisely. Every section you write — including rewrites — must sound like these excerpts."""
```

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_style_learning.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/style_learning.py tests/agents/test_style_learning.py
git commit -m "feat: add generate_style_card() and format_style_card_for_prompt() to StyleLearningAgent"
```

---

## Task 13: Rewrite ArticleWriterAgent as stateful multi-turn conversation

This is the core task. The writer becomes a stateful object with a persistent conversation thread.

**Files:**
- Modify: `agents/article_writer.py`
- Create: `tests/agents/test_article_writer.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_article_writer.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock
import os
import tempfile


def make_mock_client(section_response="## Section\n\nContent here."):
    mock = MagicMock()
    mock.generate_with_history.return_value = section_response
    mock.generate_content.return_value = "Understood. Ready to begin."
    return mock


def test_start_article_creates_file_with_title():
    mock_client = make_mock_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        result = agent.start_article(
            title="Bitcoin ETF Analysis",
            query_output_dir=tmpdir,
            style_card_str="## Writing Style Guide\nTone: analytical",
            outline="## Section 1\n## Section 2",
            research_summary="Summary here"
        )
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "Bitcoin ETF Analysis" in content


def test_start_article_initializes_conversation_history():
    mock_client = make_mock_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Summary")
        assert len(agent.conversation_history) >= 2  # initial user message + ack


def test_write_section_appends_to_conversation():
    mock_client = make_mock_client("## Introduction\n\nThis is the intro.")
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Research")
        initial_len = len(agent.conversation_history)

        agent.write_section({'title': 'Introduction', 'content': 'Cover basics'}, {})
        assert len(agent.conversation_history) == initial_len + 2  # user msg + assistant response


def test_revise_section_appends_to_existing_conversation():
    mock_client = make_mock_client("## Introduction\n\nRevised content.")
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Research")
        agent.write_section({'title': 'Introduction', 'content': 'Cover basics'}, {})
        after_write = len(agent.conversation_history)

        agent.revise_section('Introduction', 'Make it shorter', '## Introduction\n\nOriginal.')
        assert len(agent.conversation_history) == after_write + 2


def test_accept_revision_rewrites_article_file():
    mock_client = make_mock_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Research")
        agent.write_section({'title': 'Intro', 'content': 'outline'}, {})

        agent.accept_revision('Intro', '## Intro\n\nRevised and improved.')
        with open(agent.article_file) as f:
            content = f.read()
        assert 'Revised and improved.' in content
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agents/test_article_writer.py -v`
Expected: Multiple failures

**Step 3: Rewrite article_writer.py**

```python
# agents/article_writer.py
import os
import sys
import time
sys.path.append('..')
from config import ARTICLE_FILENAME, CLAUDE_QUALITY_MODEL
from utils.logger import get_logger
from utils.retry import retry_on_rate_limit

logger = get_logger(__name__)


class ArticleWriterAgent:
    """
    Stateful agent that writes a full article in a single Claude conversation thread.
    All sections and revisions happen within the same conversation, so the model
    always has full context of what it has already written when generating or revising.
    """

    def __init__(self, anthropic_client):
        self.anthropic_client = anthropic_client
        self.article_title = ""
        self.article_file = None
        self.conversation_history = []
        self.system_prompt = ""
        # Track accepted sections for clean file reconstruction on revision
        self.accepted_sections = []  # list of {'title': str, 'content': str}

    def start_article(self, title: str, query_output_dir: str, style_card_str: str,
                      outline: str, research_summary: str) -> str:
        """
        Initialize the article conversation with full context.
        Must be called before write_section().

        Args:
            title: Article title
            query_output_dir: Directory to save the article file
            style_card_str: Formatted style card from StyleLearningAgent.format_style_card_for_prompt()
            outline: Full article outline text
            research_summary: Condensed research summary from SummarizationAgent

        Returns:
            str: Path to the created article file
        """
        self.article_title = title
        self.article_file = os.path.join(query_output_dir, ARTICLE_FILENAME)

        self.system_prompt = f"""You are a respected crypto analyst writing a research article.

{style_card_str}

CRITICAL: Every section you write and every revision you make MUST match the writing style above.
The example excerpts show exactly how the author writes — match their rhythm, vocabulary, and tone precisely.
Do not use generic AI writing patterns. Write as this specific author writes."""

        initial_message = f"""I'm writing a cryptocurrency research article titled "{title}".

## Article Outline
{outline}

## Research Summary
{research_summary}

I'll ask you to write each section one at a time. For each section I'll provide the outline details and relevant source materials. Write only the requested section — not the entire article.

Please confirm you're ready to begin and briefly acknowledge the writing style you'll be matching."""

        self.conversation_history = [{"role": "user", "content": initial_message}]

        # Prime the conversation — this acknowledgment locks in the style context
        ack = self.anthropic_client.generate_with_history(
            messages=self.conversation_history,
            system_prompt=self.system_prompt,
            max_tokens=200,
            model_override=CLAUDE_QUALITY_MODEL
        )
        self.conversation_history.append({"role": "assistant", "content": ack})
        logger.info(f"Article conversation initialized for: {title}")

        with open(self.article_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")

        return self.article_file

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def write_section(self, section_info: dict, relevant_sources: dict) -> str:
        """
        Write a section using the ongoing conversation thread.
        The model has full context of all prior sections when writing.

        Args:
            section_info: dict with 'title' and 'content' (outline for this section)
            relevant_sources: dict of sources organized by priority tier

        Returns:
            str: Generated section content (Markdown)
        """
        sources_text = self._format_sources(relevant_sources)

        user_message = f"""Please write the "{section_info['title']}" section now.

## Section Outline
{section_info['content']}

## Relevant Sources for This Section
{sources_text}

Write the section in Markdown, starting with ## {section_info['title']}
Write only this section. Do not write other sections."""

        self.conversation_history.append({"role": "user", "content": user_message})

        logger.info(f"Generating section: {section_info['title']}")
        start = time.time()

        section_content = self.anthropic_client.generate_with_history(
            messages=self.conversation_history,
            system_prompt=self.system_prompt,
            max_tokens=4000,
            model_override=CLAUDE_QUALITY_MODEL
        )

        self.conversation_history.append({"role": "assistant", "content": section_content})
        logger.info(f"Section '{section_info['title']}' generated in {time.time() - start:.2f}s")

        # Append to file
        with open(self.article_file, 'a', encoding='utf-8') as f:
            f.write(section_content + "\n\n")

        # Track for revision reconstruction
        self.accepted_sections.append({'title': section_info['title'], 'content': section_content})

        return section_content

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def revise_section(self, section_title: str, revision_instructions: str,
                       current_content: str) -> str:
        """
        Revise a section within the ongoing conversation.
        The model sees the entire article written so far when rewriting.

        Args:
            section_title: Title of the section to revise
            revision_instructions: User's feedback
            current_content: The current version of the section

        Returns:
            str: Revised section content (Markdown)
        """
        user_message = f"""Please revise the "{section_title}" section based on this feedback:

{revision_instructions}

Current version of this section:
{current_content}

Rewrite the entire section incorporating the feedback. Start with ## {section_title}
Maintain the same writing style and voice. Do not change other sections."""

        self.conversation_history.append({"role": "user", "content": user_message})

        logger.info(f"Revising section: {section_title}")
        start = time.time()

        revised = self.anthropic_client.generate_with_history(
            messages=self.conversation_history,
            system_prompt=self.system_prompt,
            max_tokens=4000,
            model_override=CLAUDE_QUALITY_MODEL
        )

        self.conversation_history.append({"role": "assistant", "content": revised})
        logger.info(f"Revision of '{section_title}' generated in {time.time() - start:.2f}s")

        return revised

    def accept_revision(self, section_title: str, revised_content: str):
        """
        Accept a revision and rewrite the article file from the accepted sections list.
        No regex needed — sections are tracked as discrete objects.

        Args:
            section_title: Title of the section that was revised
            revised_content: The accepted revised content
        """
        for section in self.accepted_sections:
            if section['title'] == section_title:
                section['content'] = revised_content
                break

        # Rewrite entire file from accepted sections list
        with open(self.article_file, 'w', encoding='utf-8') as f:
            f.write(f"# {self.article_title}\n\n")
            for section in self.accepted_sections:
                f.write(section['content'] + "\n\n")

        logger.info(f"Article file updated with revision to: {section_title}")

    def retrieve_relevant_sources(self, section_title: str, article_results: list,
                                   video_results: list, user_content: list,
                                   user_content_only: bool = False) -> dict:
        """Gather research materials relevant to a specific section."""
        keywords = [w for w in section_title.lower().split() if len(w) > 3]
        sources = {
            "User Content": list(user_content),
            "YouTube": [],
            "High Relevance Articles": [],
            "Medium Relevance Articles": []
        }

        if not user_content_only:
            for video in video_results:
                title = video.get('title', '').lower()
                key_points = ' '.join(video.get('key_points', [])).lower()
                if video.get('relevance_score') == 'High' or any(k in title or k in key_points for k in keywords):
                    sources["YouTube"].append({
                        'title': video.get('title', 'Untitled Video'),
                        'text': (
                            f"Video by {video.get('channel', 'Unknown')} ({video.get('date', 'Unknown date')})\n"
                            f"Key points: {' '.join(video.get('key_points', []))}\n"
                            f"URL: {video.get('url', '')}"
                        ),
                        'relevance': video.get('relevance_score', 'Unknown')
                    })

            for article in article_results:
                title = article.get('title', '').lower()
                text = article.get('text', '').lower()
                if article.get('relevance_score') == 'High' or any(k in title or k in text for k in keywords):
                    sources["High Relevance Articles"].append({
                        'title': article.get('title', 'Untitled'),
                        'text': article.get('text', ''),
                        'url': article.get('url', ''),
                        'relevance': article.get('relevance_score', 'Unknown')
                    })
                elif article.get('relevance_score') == 'Medium':
                    sources["Medium Relevance Articles"].append({
                        'title': article.get('title', 'Untitled'),
                        'text': article.get('text', ''),
                        'url': article.get('url', ''),
                        'relevance': article.get('relevance_score', 'Unknown')
                    })

        total = sum(len(v) for v in sources.values())
        logger.info(f"Found {total} relevant sources for section '{section_title}'")
        return sources

    def read_current_article(self) -> str:
        """Read the current state of the article file."""
        if not self.article_file or not os.path.exists(self.article_file):
            return ""
        with open(self.article_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _format_sources(self, sources: dict) -> str:
        """Format sources dict into a prompt-ready string."""
        if not sources:
            return "No specific sources for this section."
        text = ""
        for priority, source_list in sources.items():
            if source_list:
                text += f"\n### {priority}\n"
                for i, source in enumerate(source_list):
                    text += f"\n**Source {i+1}: {source.get('title', 'Untitled')}**\n"
                    text += source.get('text', '') + "\n"
                    if source.get('url'):
                        text += f"URL: {source.get('url')}\n"
        return text or "No specific sources for this section."
```

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_article_writer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/article_writer.py tests/agents/test_article_writer.py
git commit -m "feat: rewrite ArticleWriterAgent as stateful multi-turn conversation"
```

---

## Task 14: Simplify FeedbackProcessor — remove regex boundary detection

**Files:**
- Modify: `agents/feedback_processor.py`
- Create: `tests/agents/test_feedback_processor.py`

**Step 1: Write the failing test**

```python
# tests/agents/test_feedback_processor.py
import sys
sys.path.insert(0, '.')
import inspect


def test_feedback_processor_has_no_regex_boundary_detection():
    """The new FeedbackProcessor must not use regex to find section boundaries."""
    import agents.feedback_processor as mod
    source = inspect.getsource(mod)
    assert 'find_section_boundaries' not in source


def test_process_revision_calls_article_writer_revise_section():
    from unittest.mock import MagicMock
    from agents.feedback_processor import FeedbackProcessor

    mock_writer = MagicMock()
    mock_writer.revise_section.return_value = "## Section\n\nRevised content."
    mock_fact_checker = MagicMock()
    mock_fact_checker.check_section.return_value = {'accurate': True}

    processor = FeedbackProcessor()
    feedback = {'action': 'revise', 'details': 'Make it shorter'}
    result = processor.process_revision_request(
        feedback=feedback,
        article_writer=mock_writer,
        section_info={'title': 'Introduction', 'content': 'outline', 'current_content': 'old content'},
        research_data={},
        style_materials={},
        fact_checker=mock_fact_checker
    )

    mock_writer.revise_section.assert_called_once_with(
        section_title='Introduction',
        revision_instructions='Make it shorter',
        current_content='old content'
    )
    assert result == "## Section\n\nRevised content."
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/test_feedback_processor.py -v`
Expected: FAIL

**Step 3: Rewrite feedback_processor.py**

```python
# agents/feedback_processor.py
import os
import sys
sys.path.append('..')
from utils.logger import get_logger

logger = get_logger(__name__)


class FeedbackProcessor:
    """
    Manages user feedback on article sections and coordinates revisions.
    Sections are tracked as discrete conversation turns in ArticleWriterAgent —
    no regex boundary detection needed.
    """

    def present_section(self, section_title: str, article_file: str):
        """Notify the user that a section is ready for review."""
        logger.info(f"Section '{section_title}' ready for review")
        print(f"\n[FEEDBACK] Section '{section_title}' has been written.")
        print(f"Please review it in: {article_file}")
        print("\nOptions:")
        print("  1. Type 'accept' to proceed to the next section")
        print("  2. Type 'revise [instructions]' to have the AI rewrite the section")
        print("  3. Edit the file directly and type 'edited' to confirm your changes")

    def prompt_for_feedback(self) -> dict:
        """Ask user if section is acceptable or needs revision."""
        while True:
            user_input = input("\n> ").strip()
            if user_input.lower() == 'accept':
                return {'action': 'accept', 'details': None}
            elif user_input.lower() == 'edited':
                return {'action': 'edited', 'details': None}
            elif user_input.lower().startswith('revise '):
                instructions = user_input[7:].strip()
                if not instructions:
                    print("Please provide revision instructions after 'revise'.")
                    continue
                return {'action': 'revise', 'details': instructions}
            else:
                print("Invalid input. Please type 'accept', 'edited', or 'revise [instructions]'.")

    def check_for_file_edits(self, article_file: str, last_known_content: str):
        """Check if the user has made manual edits to the article file."""
        with open(article_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        return current_content != last_known_content, current_content

    def process_revision_request(self, feedback: dict, article_writer, section_info: dict,
                                  research_data: dict, style_materials: dict, fact_checker) -> str:
        """
        Process a revision request by delegating to article_writer.revise_section().
        The writer's conversation history provides full style and article context automatically.

        Args:
            feedback: dict with 'action' and 'details' (revision instructions)
            article_writer: ArticleWriterAgent instance holding conversation history
            section_info: dict with 'title', 'content', 'current_content'
            research_data: used only for fact-checking after revision
            style_materials: unused — style is embedded in the conversation system prompt
            fact_checker: FactCheckerAgent instance

        Returns:
            str: Revised section content
        """
        revision_instructions = feedback.get('details', '')
        current_content = section_info.get('current_content', '')
        section_title = section_info['title']

        logger.info(f"Generating revision for section '{section_title}'")
        revised_content = article_writer.revise_section(
            section_title=section_title,
            revision_instructions=revision_instructions,
            current_content=current_content
        )

        logger.info("Fact checking revised content")
        check_results = fact_checker.check_section(
            section_content=revised_content,
            sources=research_data
        )

        if not check_results.get('accurate', False):
            logger.info("Applying factual corrections to revised content")
            revised_content = fact_checker.suggest_corrections(
                section_content=revised_content,
                check_results=check_results
            )

        return revised_content
```

**Step 4: Run tests**

Run: `python -m pytest tests/agents/test_feedback_processor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agents/feedback_processor.py tests/agents/test_feedback_processor.py
git commit -m "feat: simplify FeedbackProcessor — remove regex boundary detection, delegate to conversation-based revision"
```

---

## Task 15: Update main.py to wire the new style card and conversation pipeline

**Files:**
- Modify: `main.py`

**Step 1: Read main.py lines 427–610** to confirm exact line numbers before editing (already read above — reference lines 427–610).

**Step 2: Replace the style materials section (around line 435–444)**

Find:
```python
# Get raw style materials
style_materials = style_learning.get_raw_style_materials()

# Verify style samples are correctly loaded
if style_materials and 'samples' in style_materials:
    print(f"[MAIN] Verifying style samples: {len(style_materials['samples'])} samples loaded")
    for sample in style_materials['samples']:
        print(f"[MAIN] Sample file: {sample.get('filename', 'Unknown')}, size: {len(sample.get('content', ''))} chars")
else:
    print("[MAIN] Warning: No style samples were loaded")
```

Replace with:
```python
# Get raw style materials
style_materials = style_learning.get_raw_style_materials()

# Generate structured style card (used in every generation and revision call)
logger.info("Generating style card from writing samples...")
style_card = style_learning.generate_style_card(style_materials)

# Save style card for inspection/debugging
import json as _json
style_card_path = os.path.join(query_output_dir, "style_card.json")
with open(style_card_path, 'w', encoding='utf-8') as f:
    _json.dump(style_card, f, indent=2)
logger.info(f"Style card saved to {style_card_path}")

style_card_str = style_learning.format_style_card_for_prompt(style_card)
```

**Step 3: Replace article initialization (around line 456)**

Find:
```python
# Initialize article with title from query
article_file = article_writer.initialize_article(query, query_output_dir)
print(f"[ARTICLE WRITER] Created article file: {article_file}")

# Track the full article content for context
full_article_content = article_writer.read_current_article()
```

Replace with:
```python
# Read the finalized outline for conversation initialization
with open(outline_path, 'r', encoding='utf-8') as f:
    final_outline_content = f.read()

# Initialize stateful article conversation with style card + outline + research context
article_file = article_writer.start_article(
    title=query,
    query_output_dir=query_output_dir,
    style_card_str=style_card_str,
    outline=final_outline_content,
    research_summary=research_summary if 'research_summary' in dir() else ""
)
logger.info(f"Article conversation initialized: {article_file}")
```

Note: `research_summary` is the variable holding the summarization agent output. Check what variable name `main.py` uses for it and substitute accordingly.

**Step 4: Replace section generation (around lines 479–492)**

Find:
```python
# Generate and fact-check the section
section_content = article_writer.generate_and_check_section(
    section_info=section,
    research_data=section_sources,
    style_materials=style_materials,
    fact_checker=fact_checker,
    previous_content=full_article_content
)

# Append to article file
article_writer.append_section(section_content)

# Update full article content
full_article_content = article_writer.read_current_article()
```

Replace with:
```python
# Generate section using stateful conversation (style and prior sections always in context)
section_content = article_writer.write_section(
    section_info=section,
    relevant_sources=section_sources
)

# Fact-check the generated section
check_results = fact_checker.check_section(
    section_content=section_content,
    sources=section_sources
)
if not check_results.get('accurate', False):
    logger.info(f"Applying factual corrections to section: {section_title}")
    section_content = fact_checker.suggest_corrections(
        section_content=section_content,
        check_results=check_results
    )
    # Update the last accepted section with corrected content
    if article_writer.accepted_sections:
        article_writer.accepted_sections[-1]['content'] = section_content
        article_writer.accept_revision(section_title, section_content)
```

**Step 5: Replace the revision handling block (around lines 522–608)**

Find the entire `elif feedback['action'] == 'revise':` block (lines 522–607) and replace with:

```python
elif feedback['action'] == 'revise':
    section_with_content = section.copy()
    section_with_content['current_content'] = section_content

    revised_content = feedback_processor.process_revision_request(
        feedback=feedback,
        article_writer=article_writer,
        section_info=section_with_content,
        research_data=section_sources,
        style_materials=style_materials,
        fact_checker=fact_checker
    )

    # Accept revision — rewrites article file cleanly from accepted_sections list
    article_writer.accept_revision(section_title, revised_content)
    section_content = revised_content
    logger.info(f"Section '{section_title}' revised and updated.")
    feedback_processor.present_section(section_title, article_file)
```

**Step 6: Add logger import at top of main.py**

Find the imports section in `main.py` and add:
```python
from utils.logger import get_logger
logger = get_logger("main")
```

Replace `print(...)` calls throughout the article generation section with `logger.info(...)`.

**Step 7: Verify main.py imports cleanly**

Run: `python -c "import main" 2>&1 | head -30`
Expected: No import errors (the script may print startup messages but should not crash)

**Step 8: Commit**

```bash
git add main.py
git commit -m "feat: wire style card generation and stateful article conversation into main.py"
```

---

## Task 16: Remove openai dependency and run full test suite

**Files:**
- Modify: `requirements.txt`

**Step 1: Verify no openai imports remain**

Run: `grep -rn "from openai\|import openai\|OpenAI(" agents/ utils/ main.py config.py`
Expected: No output. If any appear, fix them before proceeding.

**Step 2: Remove openai from requirements.txt**

Find and remove the line `openai>=1.0.0` (or similar) from `requirements.txt`.

**Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

**Step 4: Smoke test — verify all imports work**

Run:
```bash
python -c "
from agents.coordinator import CoordinatorAgent
from agents.analysis import AnalysisAgent
from agents.style_learning import StyleLearningAgent
from agents.article_writer import ArticleWriterAgent
from agents.feedback_processor import FeedbackProcessor
from agents.outline_generator import OutlineGeneratorAgent
from utils.logger import get_logger
from utils.token_utils import truncate_to_token_limit
from utils.retry import retry_on_rate_limit
print('All imports OK')
"
```
Expected: `All imports OK`

**Step 5: Final commit**

```bash
git add requirements.txt
git commit -m "chore: remove openai dependency — all agents now use Claude"
```

---

## Summary

| # | Task | Key change |
|---|---|---|
| 1 | `utils/logger.py` | Centralized logging, replaces print() |
| 2 | `utils/token_utils.py` | tiktoken truncation, replaces char limits |
| 3 | `utils/retry.py` | Exponential backoff for Anthropic errors |
| 4 | `config.py` | `CLAUDE_FAST_MODEL` / `CLAUDE_QUALITY_MODEL` constants |
| 5 | `anthropic_client.py` | Add `generate_with_history()` |
| 6 | `claude_agent_base.py` | NEW — shared base for all Haiku agents |
| 7 | `coordinator.py` | OpenAI → Claude Haiku |
| 8 | `analysis.py` | OpenAI → Claude Haiku + token_utils |
| 9 | 4 agents batch | OpenAI → Claude Haiku |
| 10 | `youtube_search.py` | OpenAI → Claude Haiku |
| 11 | `outline_generator.py`, `outline_feedback.py` | Update to Claude Sonnet constants |
| 12 | `style_learning.py` | Add `generate_style_card()` + `format_style_card_for_prompt()` |
| 13 | `article_writer.py` | REWRITE — stateful multi-turn conversation |
| 14 | `feedback_processor.py` | REWRITE — remove regex, delegate to conversation |
| 15 | `main.py` | Wire style card + `start_article()` + `accept_revision()` |
| 16 | `requirements.txt` | Remove `openai` |
