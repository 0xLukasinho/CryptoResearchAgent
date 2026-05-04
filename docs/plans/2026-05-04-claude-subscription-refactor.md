# Claude Subscription Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the Crypto Research Agent so all LLM calls route through `claude -p` subprocess (Claude Max subscription billing) instead of API key, restructure into a proper `src/` Python package, drop the fact-checker, upgrade dependencies, and ship comprehensive test coverage.

**Architecture:** New `src/crypto_research_agent/` package with layered structure (`llm/`, `agents/`, `services/`, `pipeline/`, `feedback/`, `utils/`). `LLMRouter` holds a primary `ClaudeCodeBackend` (subprocess) + a fallback `AnthropicAPIBackend` (SDK) with one-time switch on quota exhaustion. Old `agents/` and `utils/` directories remain in place and untouched until Phase J at which point they are deleted in one commit and `main.py` is replaced by `cli.py`.

**Tech Stack:** Python 3.13+, `claude` CLI (Claude Code), `anthropic >=0.98.0` (fallback only), `pandas >=2.2`, `requests >=2.32`, `pytest >=8`, `pytest-mock`, `responses`, `freezegun`, `tiktoken`, `playwright`.

**Design doc:** `docs/plans/2026-05-04-claude-subscription-refactor-design.md`

**Strategy:** Side-by-side migration. New code in `src/crypto_research_agent/` lives next to existing `agents/`, `utils/`, `main.py`. Both run independently throughout. At the end (Phase J), old code is deleted in one commit and `main.py` becomes a thin shim that imports from the new package.

**Test commands:**
- All tests: `pytest -v`
- New tests only: `pytest tests/ -v --ignore=tests/agents --ignore=tests/utils` (until old tests deleted)
- Single test: `pytest tests/path/to/test.py::test_name -v`
- Live smoke (gated): `RUN_LIVE_TESTS=1 pytest tests/integration/ -v`

---

## Phase A — Project Skeleton

### Task A1: Create `pyproject.toml`

**Files:**
- Create: `pyproject.toml`

**Step 1: Write the file**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "crypto-research-agent"
version = "2.0.0"
description = "Multi-agent crypto research and article generation, billed via Claude Max subscription."
requires-python = ">=3.13"
dependencies = [
    "anthropic>=0.98.0",
    "pandas>=2.2",
    "requests>=2.32",
    "beautifulsoup4>=4.12",
    "feedparser>=6.0",
    "python-dotenv>=1.0",
    "pdfplumber>=0.11",
    "python-docx>=1.1",
    "tiktoken>=0.8",
    "playwright>=1.50",
    "substack-api>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-mock>=3.12",
    "responses>=0.25",
    "freezegun>=1.5",
]

[project.scripts]
crypto-research = "crypto_research_agent.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
filterwarnings = ["error::DeprecationWarning"]
```

**Step 2: Verify build metadata is parseable**

Run: `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`
Expected: no output (success).

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pyproject.toml with pinned latest deps and src layout"
```

---

### Task A2: Create `src/` layout skeleton

**Files:**
- Create: `src/crypto_research_agent/__init__.py` (empty)
- Create: `src/crypto_research_agent/llm/__init__.py` (empty)
- Create: `src/crypto_research_agent/agents/__init__.py` (empty)
- Create: `src/crypto_research_agent/services/__init__.py` (empty)
- Create: `src/crypto_research_agent/pipeline/__init__.py` (empty)
- Create: `src/crypto_research_agent/feedback/__init__.py` (empty)
- Create: `src/crypto_research_agent/utils/__init__.py` (empty)

**Step 1: Create the directories and empty `__init__.py` files**

(All files contain a single newline.)

**Step 2: Verify the package imports cleanly**

Run: `pip install -e ".[dev]"` then `python -c "import crypto_research_agent"`
Expected: no errors.

**Step 3: Commit**

```bash
git add src pyproject.toml
git commit -m "build: scaffold src/crypto_research_agent package layout"
```

---

### Task A3: Create `src/crypto_research_agent/config.py`

**Files:**
- Create: `src/crypto_research_agent/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
from crypto_research_agent.config import (
    CLAUDE_FAST_MODEL, CLAUDE_PREMIUM_MODEL, CLAUDE_SONNET_MODEL,
    get_model_for_role,
)


def test_model_constants_present():
    assert CLAUDE_FAST_MODEL == "claude-haiku-4-5-20251001"
    assert CLAUDE_PREMIUM_MODEL == "claude-opus-4-7"
    assert CLAUDE_SONNET_MODEL == "claude-sonnet-4-6"


def test_get_model_for_role_test_mode_uses_haiku_everywhere():
    assert get_model_for_role("fast", test_mode=True) == CLAUDE_FAST_MODEL
    assert get_model_for_role("premium", test_mode=True) == CLAUDE_FAST_MODEL


def test_get_model_for_role_normal_mode():
    assert get_model_for_role("fast", test_mode=False) == CLAUDE_FAST_MODEL
    assert get_model_for_role("premium", test_mode=False) == CLAUDE_PREMIUM_MODEL


def test_get_model_for_role_invalid_raises():
    import pytest
    with pytest.raises(KeyError):
        get_model_for_role("nonsense", test_mode=False)
```

`tests/conftest.py`:
```python
# Empty for now; fixtures added later.
```

**Step 2: Run to verify failure**

Run: `pytest tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'crypto_research_agent.config'`

**Step 3: Implement**

```python
# src/crypto_research_agent/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
SUBSTACK_CSV = INPUT_DIR / "Substacks.csv"
YOUTUBE_CSV = INPUT_DIR / "YouTubes.csv"
WRITING_SAMPLES_DIR = INPUT_DIR / "writing_samples"
WRITING_INSTRUCTIONS_FILE = INPUT_DIR / "writing_instructions.txt"

# Model constants
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_PREMIUM_MODEL = "claude-opus-4-7"
CLAUDE_SONNET_MODEL = "claude-sonnet-4-6"

# External API keys (for fallback / non-Claude services)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")
CLOUDCONVERT_API_KEY = os.environ.get("CLOUDCONVERT_API_KEY", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# SupaData
SUPADATA_BASE_URL = "https://api.supadata.ai/v1"
SUPADATA_TRANSCRIPT_ENDPOINT = "/youtube/transcript"
SUPADATA_REQUEST_DELAY = 1.2
SUPADATA_MAX_TRANSCRIPTS = 5

# CloudConvert
CLOUDCONVERT_BASE_URL = "https://api.cloudconvert.com/v2"

# YouTube Data API
YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_MAX_RESULTS_PER_PAGE = 50

# Article output
ARTICLE_FILENAME = "article.md"
OUTLINE_FILENAME = "research_outline.md"
RESEARCH_RESULTS_FILENAME = "research_results.md"
STYLE_CARD_FILENAME = "style_card.json"


def get_model_for_role(role: str, *, test_mode: bool) -> str:
    """Resolve model ID for a role, honoring test mode (Haiku for everything)."""
    if test_mode:
        return CLAUDE_FAST_MODEL
    return {
        "fast": CLAUDE_FAST_MODEL,
        "premium": CLAUDE_PREMIUM_MODEL,
    }[role]
```

**Step 4: Run to verify pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/config.py tests/test_config.py tests/conftest.py
git commit -m "feat(config): add new package config with role-based model selection"
```

---

## Phase B — LLM Layer

### Task B1: `ClaudeResponse` dataclass + `LLMBackend` protocol

**Files:**
- Create: `src/crypto_research_agent/llm/types.py`
- Create: `src/crypto_research_agent/llm/errors.py`
- Create: `tests/llm/__init__.py` (empty)
- Create: `tests/llm/test_types.py`

**Step 1: Write the failing test**

```python
# tests/llm/test_types.py
from crypto_research_agent.llm.types import ClaudeResponse


def test_claude_response_holds_fields():
    r = ClaudeResponse(
        text="hello",
        session_id="abc-123",
        cost_usd=0.0042,
        input_tokens=100,
        output_tokens=50,
    )
    assert r.text == "hello"
    assert r.session_id == "abc-123"
    assert r.cost_usd == 0.0042
    assert r.input_tokens == 100
    assert r.output_tokens == 50


def test_claude_response_session_id_optional():
    r = ClaudeResponse(text="hi", session_id=None, cost_usd=0.0,
                      input_tokens=0, output_tokens=0)
    assert r.session_id is None
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_types.py -v`
Expected: `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/llm/types.py
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ClaudeResponse:
    text: str
    session_id: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int


class LLMBackend(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
        resume_session: str | None = None,
    ) -> ClaudeResponse: ...

    def complete_json(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
    ) -> dict: ...
```

```python
# src/crypto_research_agent/llm/errors.py
class ClaudeCodeError(Exception):
    """Base for all LLM backend errors."""


class QuotaExceeded(ClaudeCodeError):
    """Subscription quota is exhausted; caller should fall back to API."""


class AuthMissing(ClaudeCodeError):
    """No valid auth — user needs to run `claude setup-token` or set ANTHROPIC_API_KEY."""


class TransientError(ClaudeCodeError):
    """Network or timeout error; retry may help."""
```

**Step 4: Verify pass**

Run: `pytest tests/llm/test_types.py -v`
Expected: 2 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/ tests/llm/
git commit -m "feat(llm): add ClaudeResponse, LLMBackend protocol, error hierarchy"
```

---

### Task B2: `ClaudeCodeBackend` — basic subprocess invocation

**Files:**
- Create: `src/crypto_research_agent/llm/claude_code.py`
- Create: `tests/llm/test_claude_code_basic.py`

**Step 1: Failing test**

```python
# tests/llm/test_claude_code_basic.py
from unittest.mock import patch, MagicMock
import json

from crypto_research_agent.llm.claude_code import ClaudeCodeBackend


def _mock_run(stdout_obj, returncode=0, stderr=""):
    completed = MagicMock()
    completed.returncode = returncode
    completed.stdout = json.dumps(stdout_obj) if isinstance(stdout_obj, dict) else stdout_obj
    completed.stderr = stderr
    return completed


def test_complete_builds_command_with_required_flags():
    backend = ClaudeCodeBackend()
    fake_stdout = {
        "result": "Hello, world!",
        "session_id": "sess-1",
        "total_cost_usd": 0.001,
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "is_error": False,
    }
    with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
        response = backend.complete(
            prompt="say hi",
            model="claude-haiku-4-5-20251001",
            system_prompt="be terse",
        )

    args = mock_run.call_args.args[0]
    assert args[0] == "claude"
    assert "-p" in args
    assert "--bare" in args
    assert "--output-format" in args and "json" in args
    assert "--allowedTools" in args
    assert "--model" in args
    assert "claude-haiku-4-5-20251001" in args
    assert "--append-system-prompt" in args

    assert response.text == "Hello, world!"
    assert response.session_id == "sess-1"
    assert response.cost_usd == 0.001
    assert response.input_tokens == 10
    assert response.output_tokens == 5


def test_complete_omits_system_prompt_flag_when_empty():
    backend = ClaudeCodeBackend()
    fake_stdout = {"result": "hi", "session_id": "s", "total_cost_usd": 0.0,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False}
    with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
        backend.complete(prompt="hi", model="claude-haiku-4-5-20251001")
    args = mock_run.call_args.args[0]
    assert "--append-system-prompt" not in args


def test_complete_passes_resume_flag_when_session_id_provided():
    backend = ClaudeCodeBackend()
    fake_stdout = {"result": "ok", "session_id": "s", "total_cost_usd": 0.0,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False}
    with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
        backend.complete(prompt="next", model="claude-haiku-4-5-20251001",
                         resume_session="sess-1")
    args = mock_run.call_args.args[0]
    assert "--resume" in args
    assert "sess-1" in args
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_claude_code_basic.py -v`
Expected: `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/llm/claude_code.py
import subprocess
import json
from typing import Any

from .types import ClaudeResponse
from .errors import ClaudeCodeError, AuthMissing, QuotaExceeded, TransientError


class ClaudeCodeBackend:
    """Primary LLM backend — invokes `claude -p` subprocess for subscription billing."""

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, *, claude_executable: str = "claude",
                 timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self._claude = claude_executable
        self._timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
        resume_session: str | None = None,
    ) -> ClaudeResponse:
        cmd = self._build_command(model=model, system_prompt=system_prompt,
                                  resume_session=resume_session, prompt=prompt)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self._timeout, check=False,
        )
        return self._parse_response(result)

    def _build_command(self, *, model: str, system_prompt: str,
                       resume_session: str | None, prompt: str) -> list[str]:
        cmd = [
            self._claude, "-p", "--bare",
            "--output-format", "json",
            "--allowedTools", "",
            "--model", model,
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        if resume_session:
            cmd.extend(["--resume", resume_session])
        cmd.append(prompt)
        return cmd

    def _parse_response(self, result: subprocess.CompletedProcess) -> ClaudeResponse:
        # Error detection added in Task B3 — for now, just parse on success.
        data: dict[str, Any] = json.loads(result.stdout)
        usage = data.get("usage", {})
        return ClaudeResponse(
            text=data.get("result", ""),
            session_id=data.get("session_id"),
            cost_usd=data.get("total_cost_usd", 0.0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
```

**Step 4: Verify pass**

Run: `pytest tests/llm/test_claude_code_basic.py -v`
Expected: 3 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/claude_code.py tests/llm/test_claude_code_basic.py
git commit -m "feat(llm): ClaudeCodeBackend basic subprocess invocation"
```

---

### Task B3: `ClaudeCodeBackend` — error detection (quota / auth / transient)

**Files:**
- Modify: `src/crypto_research_agent/llm/claude_code.py`
- Create: `tests/llm/test_claude_code_errors.py`

**Step 1: Failing test**

```python
# tests/llm/test_claude_code_errors.py
import json
from unittest.mock import patch, MagicMock
import subprocess
import pytest

from crypto_research_agent.llm.claude_code import ClaudeCodeBackend
from crypto_research_agent.llm.errors import QuotaExceeded, AuthMissing, TransientError, ClaudeCodeError


def _mock_run(stdout="", returncode=0, stderr=""):
    completed = MagicMock(spec=subprocess.CompletedProcess)
    completed.returncode = returncode
    completed.stdout = stdout
    completed.stderr = stderr
    return completed


@pytest.mark.parametrize("stderr_msg", [
    "Error: usage limit reached",
    "API rate limit exceeded for your subscription",
    "QUOTA EXCEEDED",
])
def test_quota_exceeded_detected_from_stderr(stderr_msg):
    backend = ClaudeCodeBackend()
    with patch("subprocess.run", return_value=_mock_run(returncode=1, stderr=stderr_msg)):
        with pytest.raises(QuotaExceeded):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_quota_exceeded_detected_from_json_is_error():
    backend = ClaudeCodeBackend()
    body = json.dumps({"is_error": True, "result": "Usage limit reached. Try again later."})
    with patch("subprocess.run", return_value=_mock_run(stdout=body, returncode=0)):
        with pytest.raises(QuotaExceeded):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_auth_missing_detected():
    backend = ClaudeCodeBackend()
    with patch("subprocess.run",
               return_value=_mock_run(returncode=1, stderr="Error: not authenticated")):
        with pytest.raises(AuthMissing):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_claude_cli_not_on_path_raises_auth_missing():
    backend = ClaudeCodeBackend()
    with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")):
        with pytest.raises(AuthMissing, match="Claude Code"):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_timeout_raises_claude_code_error():
    backend = ClaudeCodeBackend(timeout=1)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1)):
        with pytest.raises(ClaudeCodeError, match="timed out"):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_other_nonzero_exit_is_transient():
    backend = ClaudeCodeBackend()
    with patch("subprocess.run", return_value=_mock_run(returncode=2, stderr="network blip")):
        with pytest.raises(TransientError):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_claude_code_errors.py -v`
Expected: errors raised aren't `QuotaExceeded` etc.

**Step 3: Implement**

Modify `src/crypto_research_agent/llm/claude_code.py`. Replace the `complete` and `_parse_response` methods, and add helpers:

```python
import re

QUOTA_PATTERNS = re.compile(r"(usage limit|quota exceeded|rate limit)", re.IGNORECASE)
AUTH_PATTERNS = re.compile(r"(not authenticated|setup-token|unauthorized)", re.IGNORECASE)


class ClaudeCodeBackend:
    # ... __init__ unchanged ...

    def complete(self, prompt, *, model, system_prompt="", resume_session=None):
        cmd = self._build_command(model=model, system_prompt=system_prompt,
                                  resume_session=resume_session, prompt=prompt)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self._timeout, check=False,
            )
        except FileNotFoundError as e:
            raise AuthMissing(
                "Claude Code CLI not found on PATH. Install from "
                "https://claude.com/download and run `claude setup-token`."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ClaudeCodeError(
                f"`claude -p` timed out after {self._timeout}s"
            ) from e

        self._raise_on_errors(result)
        return self._parse_success(result.stdout)

    def _raise_on_errors(self, result: subprocess.CompletedProcess) -> None:
        stderr = result.stderr or ""
        # JSON-level error (returncode may be 0)
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                if data.get("is_error"):
                    msg = data.get("result", "")
                    if QUOTA_PATTERNS.search(msg):
                        raise QuotaExceeded(f"Subscription quota exhausted: {msg}")
                    raise ClaudeCodeError(f"Claude returned error: {msg}")
            except json.JSONDecodeError:
                pass
        if result.returncode == 0:
            return
        # Non-zero exit
        if QUOTA_PATTERNS.search(stderr):
            raise QuotaExceeded(f"Subscription quota exhausted: {stderr.strip()}")
        if AUTH_PATTERNS.search(stderr):
            raise AuthMissing(
                f"Claude Code is not authenticated. "
                f"Run `claude setup-token` or `claude login`. ({stderr.strip()})"
            )
        raise TransientError(
            f"`claude -p` failed (exit {result.returncode}): {stderr.strip() or '<no stderr>'}"
        )

    def _parse_success(self, stdout: str) -> ClaudeResponse:
        data: dict[str, Any] = json.loads(stdout)
        usage = data.get("usage", {})
        return ClaudeResponse(
            text=data.get("result", ""),
            session_id=data.get("session_id"),
            cost_usd=data.get("total_cost_usd", 0.0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
```

(Delete the old `_parse_response`.)

**Step 4: Verify pass**

Run: `pytest tests/llm/ -v`
Expected: all green (B2 + B3 tests pass).

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/claude_code.py tests/llm/test_claude_code_errors.py
git commit -m "feat(llm): detect quota, auth, transient errors from claude -p"
```

---

### Task B4: `ClaudeCodeBackend` — retry on transient + `complete_json`

**Files:**
- Modify: `src/crypto_research_agent/llm/claude_code.py`
- Create: `tests/llm/test_claude_code_retry_json.py`

**Step 1: Failing test**

```python
# tests/llm/test_claude_code_retry_json.py
import json
from unittest.mock import patch, MagicMock
import subprocess
import pytest

from crypto_research_agent.llm.claude_code import ClaudeCodeBackend
from crypto_research_agent.llm.errors import TransientError


def _ok(text="ok"):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.returncode = 0
    m.stdout = json.dumps({"result": text, "session_id": "s",
                           "total_cost_usd": 0.0,
                           "usage": {"input_tokens": 1, "output_tokens": 1},
                           "is_error": False})
    m.stderr = ""
    return m


def _transient():
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.returncode = 2
    m.stdout = ""
    m.stderr = "temporary network error"
    return m


def test_transient_error_retries_and_succeeds():
    backend = ClaudeCodeBackend(max_retries=2, retry_base_delay=0.0)
    with patch("subprocess.run", side_effect=[_transient(), _ok("recovered")]):
        with patch("time.sleep"):
            r = backend.complete(prompt="x", model="claude-haiku-4-5-20251001")
    assert r.text == "recovered"


def test_transient_error_exhausts_retries():
    backend = ClaudeCodeBackend(max_retries=2, retry_base_delay=0.0)
    with patch("subprocess.run", side_effect=[_transient(), _transient(), _transient()]):
        with patch("time.sleep"):
            with pytest.raises(TransientError):
                backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_complete_json_parses_clean_json():
    backend = ClaudeCodeBackend()
    payload = '{"key": "value", "n": 42}'
    with patch.object(backend, "complete") as mock_complete:
        mock_complete.return_value = MagicMock(text=payload)
        result = backend.complete_json(prompt="x", model="claude-haiku-4-5-20251001")
    assert result == {"key": "value", "n": 42}


def test_complete_json_extracts_from_messy_text():
    backend = ClaudeCodeBackend()
    payload = 'Sure thing!\n{"key": "value"}\nDone.'
    with patch.object(backend, "complete") as mock_complete:
        mock_complete.return_value = MagicMock(text=payload)
        result = backend.complete_json(prompt="x", model="claude-haiku-4-5-20251001")
    assert result == {"key": "value"}


def test_complete_json_returns_empty_on_garbage():
    backend = ClaudeCodeBackend()
    with patch.object(backend, "complete") as mock_complete:
        mock_complete.return_value = MagicMock(text="this isn't JSON at all")
        result = backend.complete_json(prompt="x", model="claude-haiku-4-5-20251001")
    assert result == {}


def test_complete_json_appends_strict_instruction_to_system_prompt():
    backend = ClaudeCodeBackend()
    with patch.object(backend, "complete") as mock_complete:
        mock_complete.return_value = MagicMock(text='{}')
        backend.complete_json(prompt="x", model="m", system_prompt="be helpful")
    call_kwargs = mock_complete.call_args.kwargs
    assert "valid JSON only" in call_kwargs["system_prompt"]
    assert "be helpful" in call_kwargs["system_prompt"]
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_claude_code_retry_json.py -v`
Expected: failures.

**Step 3: Implement**

Modify `claude_code.py`:

```python
import time
import re

# At module top:
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class ClaudeCodeBackend:
    def __init__(self, *, claude_executable: str = "claude",
                 timeout: int = 300, max_retries: int = 2,
                 retry_base_delay: float = 1.0):
        self._claude = claude_executable
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    def complete(self, prompt, *, model, system_prompt="", resume_session=None):
        last_err: TransientError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._invoke_once(prompt, model=model,
                                         system_prompt=system_prompt,
                                         resume_session=resume_session)
            except TransientError as e:
                last_err = e
                if attempt < self._max_retries:
                    delay = self._retry_base_delay * (4 ** attempt)
                    time.sleep(delay)
                    continue
                raise
        # Unreachable
        raise last_err  # type: ignore[misc]

    def _invoke_once(self, prompt, *, model, system_prompt, resume_session):
        cmd = self._build_command(model=model, system_prompt=system_prompt,
                                  resume_session=resume_session, prompt=prompt)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self._timeout, check=False,
            )
        except FileNotFoundError as e:
            raise AuthMissing(
                "Claude Code CLI not found on PATH. Install from "
                "https://claude.com/download and run `claude setup-token`."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ClaudeCodeError(
                f"`claude -p` timed out after {self._timeout}s"
            ) from e
        self._raise_on_errors(result)
        return self._parse_success(result.stdout)

    def complete_json(self, prompt, *, model, system_prompt=""):
        strict = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "You MUST respond with valid JSON only. "
            "No explanation, no markdown fences, no commentary. Just the raw JSON object."
        )
        response = self.complete(prompt=prompt, model=model, system_prompt=strict)
        return self._parse_json_loose(response.text)

    @staticmethod
    def _parse_json_loose(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = JSON_OBJECT_RE.search(text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
```

(Delete the old `complete` method body that was inline.)

**Step 4: Verify pass**

Run: `pytest tests/llm/ -v`
Expected: all pass.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/claude_code.py tests/llm/test_claude_code_retry_json.py
git commit -m "feat(llm): add transient retry and complete_json to ClaudeCodeBackend"
```

---

### Task B5: `AnthropicAPIBackend` (fallback)

**Files:**
- Create: `src/crypto_research_agent/llm/api_backend.py`
- Create: `tests/llm/test_api_backend.py`

**Step 1: Failing test**

```python
# tests/llm/test_api_backend.py
from unittest.mock import patch, MagicMock

from crypto_research_agent.llm.api_backend import AnthropicAPIBackend


def _mock_message(text="reply"):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    m.usage = MagicMock(input_tokens=11, output_tokens=22)
    return m


def test_complete_calls_anthropic_messages_create():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message("hi")

        backend = AnthropicAPIBackend(api_key="sk-test")
        r = backend.complete(prompt="hello", model="claude-haiku-4-5-20251001",
                             system_prompt="be brief")

    args = mock_client.messages.create.call_args.kwargs
    assert args["model"] == "claude-haiku-4-5-20251001"
    assert args["system"] == "be brief"
    assert args["messages"] == [{"role": "user", "content": "hello"}]
    assert r.text == "hi"
    assert r.input_tokens == 11
    assert r.output_tokens == 22


def test_complete_with_resume_session_uses_stored_history():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message("turn-2")

        backend = AnthropicAPIBackend(api_key="sk-test")
        # first turn
        backend.complete(prompt="hi", model="m")
        # second turn, "resume" session id from first turn (synthetic)
        backend.complete(prompt="again", model="m", resume_session=backend._last_session_id)

    second_call = mock_client.messages.create.call_args_list[1].kwargs
    assert len(second_call["messages"]) == 3  # user1, assistant1, user2


def test_session_id_is_returned_and_distinct_per_root_call():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message("ok")

        backend = AnthropicAPIBackend(api_key="sk-test")
        a = backend.complete(prompt="a", model="m")
        b = backend.complete(prompt="b", model="m")

    assert a.session_id and b.session_id
    assert a.session_id != b.session_id


def test_complete_json_uses_strict_prompt():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message('{"a": 1}')

        backend = AnthropicAPIBackend(api_key="sk-test")
        out = backend.complete_json(prompt="x", model="m", system_prompt="be helpful")

    assert out == {"a": 1}
    sys_prompt = mock_client.messages.create.call_args.kwargs["system"]
    assert "valid JSON only" in sys_prompt
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_api_backend.py -v`
Expected: `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/llm/api_backend.py
import uuid
import json
import re

import anthropic

from .types import ClaudeResponse
from .errors import AuthMissing, QuotaExceeded, TransientError, ClaudeCodeError


JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class AnthropicAPIBackend:
    """Fallback LLM backend using the anthropic SDK + ANTHROPIC_API_KEY."""

    def __init__(self, *, api_key: str, default_max_tokens: int = 4096):
        if not api_key:
            raise AuthMissing("ANTHROPIC_API_KEY is required for the API fallback backend.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._default_max_tokens = default_max_tokens
        # Map session_id -> list of {role, content} dicts
        self._sessions: dict[str, list[dict]] = {}
        self._last_session_id: str | None = None

    def complete(self, prompt: str, *, model: str,
                 system_prompt: str = "",
                 resume_session: str | None = None) -> ClaudeResponse:
        if resume_session and resume_session in self._sessions:
            session_id = resume_session
            messages = list(self._sessions[session_id])
        else:
            session_id = str(uuid.uuid4())
            messages = []

        messages.append({"role": "user", "content": prompt})

        try:
            msg = self._client.messages.create(
                model=model,
                max_tokens=self._default_max_tokens,
                system=system_prompt,
                messages=messages,
            )
        except anthropic.RateLimitError as e:
            raise QuotaExceeded(f"API rate/quota error: {e}") from e
        except anthropic.AuthenticationError as e:
            raise AuthMissing(f"API authentication failed: {e}") from e
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
            raise TransientError(f"API transient error: {e}") from e
        except anthropic.APIStatusError as e:
            raise ClaudeCodeError(f"API status error: {e}") from e

        text = msg.content[0].text
        messages.append({"role": "assistant", "content": text})
        self._sessions[session_id] = messages
        self._last_session_id = session_id

        return ClaudeResponse(
            text=text,
            session_id=session_id,
            cost_usd=0.0,  # API SDK doesn't return per-call cost; track elsewhere if needed
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )

    def complete_json(self, prompt: str, *, model: str, system_prompt: str = "") -> dict:
        strict = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "You MUST respond with valid JSON only. "
            "No explanation, no markdown fences, no commentary. Just the raw JSON object."
        )
        response = self.complete(prompt=prompt, model=model, system_prompt=strict)
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            pass
        match = JSON_OBJECT_RE.search(response.text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
```

**Step 4: Verify pass**

Run: `pytest tests/llm/test_api_backend.py -v`
Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/api_backend.py tests/llm/test_api_backend.py
git commit -m "feat(llm): add AnthropicAPIBackend fallback with session tracking"
```

---

### Task B6: `LLMRouter` — primary + quota fallback switch

**Files:**
- Create: `src/crypto_research_agent/llm/router.py`
- Create: `tests/llm/test_router.py`

**Step 1: Failing test**

```python
# tests/llm/test_router.py
from unittest.mock import MagicMock
import pytest

from crypto_research_agent.llm.router import LLMRouter
from crypto_research_agent.llm.errors import QuotaExceeded
from crypto_research_agent.llm.types import ClaudeResponse


def _resp(text="ok"):
    return ClaudeResponse(text=text, session_id="s", cost_usd=0.0,
                          input_tokens=0, output_tokens=0)


def test_routes_to_primary_by_default():
    primary = MagicMock()
    primary.complete.return_value = _resp("primary")
    router = LLMRouter(primary=primary)
    r = router.complete(prompt="x", model="m")
    assert r.text == "primary"


def test_quota_error_triggers_callback_and_uses_fallback():
    primary = MagicMock()
    primary.complete.side_effect = QuotaExceeded("out")
    fallback = MagicMock()
    fallback.complete.return_value = _resp("fallback")
    triggered = []
    router = LLMRouter(primary=primary)
    router.set_fallback_factory(lambda choice: fallback)

    def on_quota():
        triggered.append(True)
        return "opus"  # user picked Opus on the API

    router.on_quota_exhausted = on_quota
    r = router.complete(prompt="x", model="m")
    assert triggered == [True]
    assert r.text == "fallback"


def test_subsequent_calls_skip_primary_after_fallback_active():
    primary = MagicMock()
    primary.complete.side_effect = QuotaExceeded("out")
    fallback = MagicMock()
    fallback.complete.return_value = _resp("fallback")
    router = LLMRouter(primary=primary)
    router.set_fallback_factory(lambda choice: fallback)
    router.on_quota_exhausted = lambda: "sonnet"

    router.complete(prompt="a", model="m")
    router.complete(prompt="b", model="m")

    # primary called only once; fallback used twice
    assert primary.complete.call_count == 1
    assert fallback.complete.call_count == 2


def test_abort_choice_propagates_quota_exceeded():
    primary = MagicMock()
    primary.complete.side_effect = QuotaExceeded("out")
    router = LLMRouter(primary=primary)
    router.on_quota_exhausted = lambda: "abort"
    with pytest.raises(QuotaExceeded):
        router.complete(prompt="x", model="m")
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_router.py -v`
Expected: `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/llm/router.py
from typing import Callable, Literal

from .types import ClaudeResponse, LLMBackend
from .errors import QuotaExceeded


QuotaChoice = Literal["opus", "sonnet", "abort"]


class LLMRouter:
    """Holds primary + on-demand fallback backend; switches permanently on quota error."""

    def __init__(self, *, primary: LLMBackend):
        self._primary = primary
        self._fallback: LLMBackend | None = None
        self._fallback_factory: Callable[[QuotaChoice], LLMBackend] | None = None
        self.on_quota_exhausted: Callable[[], QuotaChoice] | None = None
        self._chosen_fallback_model: str | None = None

    def set_fallback_factory(self, factory: Callable[[QuotaChoice], LLMBackend]) -> None:
        self._fallback_factory = factory

    @property
    def fallback_active(self) -> bool:
        return self._fallback is not None

    @property
    def fallback_model_choice(self) -> str | None:
        return self._chosen_fallback_model

    def complete(self, prompt: str, *, model: str,
                 system_prompt: str = "",
                 resume_session: str | None = None) -> ClaudeResponse:
        return self._dispatch(
            "complete",
            dict(prompt=prompt, model=model, system_prompt=system_prompt,
                 resume_session=resume_session),
        )

    def complete_json(self, prompt: str, *, model: str, system_prompt: str = "") -> dict:
        return self._dispatch(
            "complete_json",
            dict(prompt=prompt, model=model, system_prompt=system_prompt),
        )

    def _dispatch(self, method: str, kwargs: dict):
        backend = self._fallback or self._primary
        try:
            return getattr(backend, method)(**kwargs)
        except QuotaExceeded:
            if self._fallback is not None:
                # Already on fallback — don't loop.
                raise
            if self.on_quota_exhausted is None or self._fallback_factory is None:
                raise
            choice = self.on_quota_exhausted()
            if choice == "abort":
                raise
            self._fallback = self._fallback_factory(choice)
            self._chosen_fallback_model = choice
            return getattr(self._fallback, method)(**kwargs)
```

**Step 4: Verify pass**

Run: `pytest tests/llm/test_router.py -v`
Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/router.py tests/llm/test_router.py
git commit -m "feat(llm): add LLMRouter with one-time quota fallback switch"
```

---

### Task B7: `Conversation` multi-turn wrapper

**Files:**
- Create: `src/crypto_research_agent/llm/conversation.py`
- Create: `tests/llm/test_conversation.py`

**Step 1: Failing test**

```python
# tests/llm/test_conversation.py
from unittest.mock import MagicMock
from crypto_research_agent.llm.conversation import Conversation
from crypto_research_agent.llm.types import ClaudeResponse


def _resp(text, sid="sess-1"):
    return ClaudeResponse(text=text, session_id=sid, cost_usd=0.0,
                          input_tokens=0, output_tokens=0)


def test_first_send_passes_system_prompt_no_resume():
    backend = MagicMock()
    backend.complete.return_value = _resp("ack", sid="sess-1")
    conv = Conversation(backend, model="m", system_prompt="be witty")
    out = conv.send("hello")
    backend.complete.assert_called_once()
    kwargs = backend.complete.call_args.kwargs
    assert kwargs["system_prompt"] == "be witty"
    assert kwargs["resume_session"] is None
    assert kwargs["model"] == "m"
    assert out == "ack"


def test_subsequent_send_passes_resume_no_system_prompt():
    backend = MagicMock()
    backend.complete.side_effect = [_resp("first", sid="sess-1"),
                                     _resp("second", sid="sess-1")]
    conv = Conversation(backend, model="m", system_prompt="sys")
    conv.send("turn-1")
    conv.send("turn-2")
    second_kwargs = backend.complete.call_args_list[1].kwargs
    assert second_kwargs["resume_session"] == "sess-1"
    assert second_kwargs["system_prompt"] == ""


def test_session_id_persisted_across_turns():
    backend = MagicMock()
    backend.complete.side_effect = [_resp("a", sid="s1"), _resp("b", sid="s1")]
    conv = Conversation(backend, model="m", system_prompt="x")
    conv.send("1")
    assert conv.session_id == "s1"
    conv.send("2")
    assert conv.session_id == "s1"


def test_turn_count_tracked():
    backend = MagicMock()
    backend.complete.return_value = _resp("ok")
    conv = Conversation(backend, model="m", system_prompt="x")
    assert conv.turn_count == 0
    conv.send("a")
    assert conv.turn_count == 1
    conv.send("b")
    assert conv.turn_count == 2
```

**Step 2: Verify failure**

Run: `pytest tests/llm/test_conversation.py -v`
Expected: `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/llm/conversation.py
from .types import LLMBackend


class Conversation:
    """Multi-turn wrapper around an LLMBackend (router or raw backend)."""

    def __init__(self, backend: LLMBackend, *, model: str, system_prompt: str):
        self._backend = backend
        self._model = model
        self._system_prompt = system_prompt
        self._session_id: str | None = None
        self._turn_count = 0

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def send(self, user_message: str) -> str:
        response = self._backend.complete(
            prompt=user_message,
            model=self._model,
            system_prompt=self._system_prompt if self._turn_count == 0 else "",
            resume_session=self._session_id,
        )
        self._session_id = response.session_id
        self._turn_count += 1
        return response.text
```

**Step 4: Verify pass**

Run: `pytest tests/llm/test_conversation.py -v`
Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/llm/conversation.py tests/llm/test_conversation.py
git commit -m "feat(llm): add Conversation multi-turn wrapper"
```

---

## Phase C — Utilities

### Task C1: Migrate `logger.py` to new package

**Files:**
- Create: `src/crypto_research_agent/utils/logger.py` (copy from `utils/logger.py`)
- Create: `tests/utils/__init__.py` (empty)
- Create: `tests/utils/test_logger.py`

**Step 1: Failing test**

```python
# tests/utils/test_logger.py
import logging
from crypto_research_agent.utils.logger import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test_module_new")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module_new"


def test_get_logger_idempotent():
    a = get_logger("dup")
    b = get_logger("dup")
    assert a is b
    root = logging.getLogger()
    assert len(root.handlers) > 0
```

**Step 2: Verify failure**

Run: `pytest tests/utils/test_logger.py -v`
Expected: `ModuleNotFoundError`.

**Step 3: Implement** — copy the content of existing `utils/logger.py` to `src/crypto_research_agent/utils/logger.py` verbatim.

**Step 4: Verify pass**

Run: `pytest tests/utils/test_logger.py -v`
Expected: 2 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/utils/logger.py tests/utils/test_logger.py tests/utils/__init__.py
git commit -m "feat(utils): copy logger to new package layout"
```

---

### Task C2: Migrate `token_utils.py`

**Files:**
- Create: `src/crypto_research_agent/utils/token_utils.py` (copy from `utils/token_utils.py`)
- Create: `tests/utils/test_token_utils.py`

**Step 1: Failing test** — copy the existing tests from `tests/utils/test_token_utils.py` and update imports:

```python
# tests/utils/test_token_utils.py
from crypto_research_agent.utils.token_utils import truncate_to_token_limit


def test_short_text_unchanged():
    text = "Hello world. This is a short sentence."
    assert truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 1000) == text


def test_long_text_gets_truncated():
    text = "This is a sentence. " * 500
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 100)
    assert len(result) < len(text)


def test_truncates_at_sentence_boundary_when_available():
    sentence_ending = "This ends here. "
    filler = "word " * 150
    after = "more words after " * 50
    text = filler + sentence_ending + after
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 160)
    stripped = result.strip()
    assert stripped.endswith(('.', '?', '!'))
```

**Step 2: Verify failure** — `ModuleNotFoundError`.

**Step 3: Implement** — copy `utils/token_utils.py` verbatim to `src/crypto_research_agent/utils/token_utils.py`.

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/utils/token_utils.py tests/utils/test_token_utils.py
git commit -m "feat(utils): copy token_utils to new package layout"
```

---

### Task C3: `utils/filters.py` — clean port of `article_filter.py`

**Files:**
- Create: `src/crypto_research_agent/utils/filters.py`
- Create: `tests/utils/test_filters.py`

**Step 1: Failing test**

```python
# tests/utils/test_filters.py
from crypto_research_agent.utils.filters import (
    contains_all_required_terms, is_likely_english,
)


def test_contains_all_terms_true_when_all_present():
    article = {"title": "Bitcoin ETF News", "text": "The Bitcoin ETF was approved."}
    assert contains_all_required_terms(article, ["bitcoin", "etf"]) is True


def test_contains_all_terms_false_when_missing():
    article = {"title": "Bitcoin News", "text": "Just bitcoin discussion."}
    assert contains_all_required_terms(article, ["bitcoin", "etf"]) is False


def test_contains_all_terms_passes_when_no_required_terms():
    article = {"title": "Anything", "text": "Anything"}
    assert contains_all_required_terms(article, []) is True


def test_contains_all_terms_case_insensitive():
    article = {"title": "BITCOIN", "text": "ETF approved"}
    assert contains_all_required_terms(article, ["bitcoin", "etf"]) is True


def test_contains_all_terms_handles_string_input():
    text = "Bitcoin ETF was approved"
    assert contains_all_required_terms(text, ["bitcoin", "etf"]) is True


def test_is_likely_english_true_for_english():
    text = "The quick brown fox jumps over the lazy dog and runs into the woods."
    assert is_likely_english(text) is True


def test_is_likely_english_false_for_garbage():
    text = "asdfghj qwerty zxcvbnm"
    assert is_likely_english(text) is False
```

**Step 2: Verify failure** — `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/utils/filters.py
import re

from .logger import get_logger

logger = get_logger(__name__)


def _extract_clean_text(article: dict) -> str:
    title = (article.get("title", "") or "").lower()
    text = (article.get("text", "") or "").lower()
    combined = f"{title} {text}"
    combined = re.sub(r"[^\w\s]", " ", combined)
    return re.sub(r"\s+", " ", combined).strip()


def contains_all_required_terms(article: dict | str, required_terms: list[str]) -> bool:
    if not required_terms:
        return True
    haystack = article.lower() if isinstance(article, str) else _extract_clean_text(article)
    clean_terms = [t.lower().strip() for t in required_terms if isinstance(t, str) and t.strip()]
    if not clean_terms:
        return True
    for term in clean_terms:
        if term not in haystack:
            logger.debug("Required term not found: %r", term)
            return False
    return True


_COMMON_ENGLISH_WORDS = frozenset({
    "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was",
    "for", "on", "are", "as", "with", "his", "they", "i", "at", "be", "this",
    "have", "from", "or", "one", "had", "by", "but", "not", "what", "all", "were",
    "we", "when", "your", "can", "said", "there", "use", "an", "each", "which",
    "she", "do", "how", "their", "if", "will", "up", "other", "about", "out",
    "many", "then", "them", "these", "so", "some", "her", "would", "make", "like",
    "him", "into", "time", "has", "two", "more", "no", "way", "could", "people",
    "than", "first", "been", "who", "now", "find", "long", "down", "day", "did",
    "get", "come", "made", "may", "part",
})


def is_likely_english(text: str, threshold: float = 0.005) -> bool:
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    if not words:
        return False
    matches = sum(1 for w in words if w in _COMMON_ENGLISH_WORDS)
    return (matches / len(words)) >= threshold
```

**Step 4: Verify pass** — `pytest tests/utils/test_filters.py -v` → 7 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/utils/filters.py tests/utils/test_filters.py
git commit -m "feat(utils): port article_filter to filters.py without debug prints"
```

---

### Task C4: `utils/paths.py` — output dir naming

**Files:**
- Create: `src/crypto_research_agent/utils/paths.py`
- Create: `tests/utils/test_paths.py`

**Step 1: Failing test**

```python
# tests/utils/test_paths.py
from pathlib import Path
import datetime
from freezegun import freeze_time

from crypto_research_agent.utils.paths import (
    sanitize_query_slug, build_output_dir,
)


def test_sanitize_simple():
    assert sanitize_query_slug("Bitcoin ETF") == "bitcoin_etf"


def test_sanitize_strips_punctuation():
    assert sanitize_query_slug("Bitcoin's ETF/Approval!") == "bitcoins_etf_approval"


def test_sanitize_collapses_whitespace_and_underscores():
    assert sanitize_query_slug("a   b___c") == "a_b_c"


def test_sanitize_truncates_long_input():
    out = sanitize_query_slug("x" * 200)
    assert len(out) <= 60


def test_sanitize_falls_back_for_empty():
    assert sanitize_query_slug("") == "query"
    assert sanitize_query_slug("!!!") == "query"


@freeze_time("2026-05-04 14:23:01")
def test_build_output_dir_appends_timestamp(tmp_path):
    out = build_output_dir(tmp_path, "Bitcoin ETF")
    assert out == tmp_path / "bitcoin_etf_2026-05-04_142301"
    assert not out.exists()  # caller creates


@freeze_time("2026-05-04 14:23:01")
def test_build_output_dir_unique_when_duplicate(tmp_path):
    first = build_output_dir(tmp_path, "Bitcoin ETF")
    first.mkdir()
    second = build_output_dir(tmp_path, "Bitcoin ETF")
    assert second != first
    assert second.name.startswith("bitcoin_etf_2026-05-04_142301")
```

**Step 2: Verify failure** — `ModuleNotFoundError`.

**Step 3: Implement**

```python
# src/crypto_research_agent/utils/paths.py
import re
import datetime
from pathlib import Path


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def sanitize_query_slug(query: str, *, max_length: int = 60) -> str:
    s = (query or "").lower()
    s = _SLUG_NON_ALNUM.sub("_", s).strip("_")
    if not s:
        return "query"
    return s[:max_length].rstrip("_") or "query"


def build_output_dir(parent: Path, query: str) -> Path:
    """Return a unique output directory path of form <parent>/<slug>_YYYY-MM-DD_HHMMSS[_<n>]."""
    slug = sanitize_query_slug(query)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = parent / f"{slug}_{timestamp}"
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = parent / f"{slug}_{timestamp}_{counter}"
        if not candidate.exists():
            return candidate
        counter += 1
```

**Step 4: Verify pass** — `pytest tests/utils/test_paths.py -v` → 7 passed.

**Step 5: Commit**

```bash
git add src/crypto_research_agent/utils/paths.py tests/utils/test_paths.py
git commit -m "feat(utils): paths module for slug sanitization + timestamp-based output dirs"
```

---

### Task C5: `utils/outline_parser.py` — port outline section parser

**Files:**
- Create: `src/crypto_research_agent/utils/outline_parser.py`
- Create: `tests/utils/test_outline_parser.py`

**Step 1: Failing test**

```python
# tests/utils/test_outline_parser.py
from crypto_research_agent.utils.outline_parser import parse_sections


def test_parse_simple_outline():
    outline = """# My Article
## 1. Introduction
- A bullet
- Another bullet

## 2. Body
- Body bullet
"""
    sections = parse_sections(outline)
    assert len(sections) == 2
    assert sections[0]["title"] == "1. Introduction"
    assert "- A bullet" in sections[0]["content"]
    assert sections[1]["title"] == "2. Body"


def test_skips_h1_title():
    outline = "# Title\n## Section A\n- x"
    sections = parse_sections(outline)
    assert len(sections) == 1
    assert sections[0]["title"] == "Section A"


def test_handles_empty_outline():
    assert parse_sections("") == []


def test_subsections_included_in_content():
    outline = """## 1. Section
### 1.1 Subsection
- bullet
### 1.2 Another sub
- bullet
"""
    sections = parse_sections(outline)
    assert len(sections) == 1
    assert "### 1.1 Subsection" in sections[0]["content"]
    assert "### 1.2 Another sub" in sections[0]["content"]
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/utils/outline_parser.py
from typing import TypedDict


class Section(TypedDict):
    title: str
    content: str


def parse_sections(outline_content: str) -> list[Section]:
    sections: list[Section] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in outline_content.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            if current_title is not None:
                sections.append({"title": current_title, "content": "\n".join(current_lines)})
            current_title = line[3:].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections.append({"title": current_title, "content": "\n".join(current_lines)})
    return sections
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/utils/outline_parser.py tests/utils/test_outline_parser.py
git commit -m "feat(utils): outline_parser for splitting outline into sections"
```

---

### Task C6: `utils/csv_loader.py` — typed CSV loaders

**Files:**
- Create: `src/crypto_research_agent/utils/csv_loader.py`
- Create: `tests/utils/test_csv_loader.py`

**Step 1: Failing test**

```python
# tests/utils/test_csv_loader.py
from crypto_research_agent.utils.csv_loader import load_substack_urls, load_youtube_channels


def test_load_substack_urls_filters_empty(tmp_path):
    csv_path = tmp_path / "subs.csv"
    csv_path.write_text(
        "Name,Substack URL\nFoo,https://foo.substack.com\nEmpty,\nBar,bar.substack.com\n"
    )
    urls = load_substack_urls(csv_path)
    assert "https://foo.substack.com" in urls
    assert "https://bar.substack.com" in urls  # protocol added
    assert all(u.startswith("https://") for u in urls)
    assert "" not in urls


def test_load_youtube_channels_returns_dataframe(tmp_path):
    csv_path = tmp_path / "yt.csv"
    csv_path.write_text("Name,Channel ID,YouTube URL\nFoo,UC123,https://youtube.com/@foo\n")
    df = load_youtube_channels(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["Channel ID"] == "UC123"


def test_load_substack_urls_missing_file_returns_empty(tmp_path):
    assert load_substack_urls(tmp_path / "missing.csv") == []
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/utils/csv_loader.py
from pathlib import Path

import pandas as pd

from .logger import get_logger

logger = get_logger(__name__)


def load_substack_urls(csv_path: Path) -> list[str]:
    if not Path(csv_path).exists():
        logger.warning("Substack CSV not found: %s", csv_path)
        return []
    df = pd.read_csv(csv_path)
    raw = df["Substack URL"].dropna().tolist() if "Substack URL" in df.columns else []
    cleaned: list[str] = []
    for url in raw:
        if not isinstance(url, str) or len(url) <= 5:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        cleaned.append(url)
    return cleaned


def load_youtube_channels(csv_path: Path) -> pd.DataFrame:
    if not Path(csv_path).exists():
        logger.warning("YouTube CSV not found: %s", csv_path)
        return pd.DataFrame()
    return pd.read_csv(csv_path)
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/utils/csv_loader.py tests/utils/test_csv_loader.py
git commit -m "feat(utils): typed CSV loaders for Substacks and YouTube channels"
```

---

## Phase D — Services Layer

### Task D1: `services/substack.py` skeleton + `Article` dataclass

**Files:**
- Create: `src/crypto_research_agent/services/substack.py`
- Create: `tests/services/__init__.py`
- Create: `tests/services/test_substack_dataclass.py`

**Step 1: Failing test**

```python
# tests/services/test_substack_dataclass.py
from crypto_research_agent.services.substack import Article


def test_article_required_fields():
    a = Article(
        title="Hello",
        author="Alice",
        date="2026-01-01",
        text="body",
        url="https://example.com",
    )
    assert a.title == "Hello"
    assert a.url.startswith("https://")
```

**Step 2: Verify failure.**

**Step 3: Implement** (skeleton only — full service in next tasks)

```python
# src/crypto_research_agent/services/substack.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    title: str
    author: str
    date: str
    text: str
    url: str
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/substack.py tests/services/
git commit -m "feat(services): Article dataclass scaffold"
```

---

### Task D2: `services/substack.py` — `_fetch_post_data`, `Newsletter`, `Post` private helpers

**Files:**
- Modify: `src/crypto_research_agent/services/substack.py`
- Create: `tests/services/test_substack_helpers.py`

**Step 1: Failing test**

```python
# tests/services/test_substack_helpers.py
import responses
from crypto_research_agent.services.substack import _Newsletter, _Post


@responses.activate
def test_newsletter_get_posts_returns_list():
    responses.add(
        responses.GET,
        "https://foo.substack.com/api/v1/posts",
        json={"posts": [
            {"canonical_url": "https://foo.substack.com/p/article-1", "slug": "article-1"},
            {"canonical_url": "https://foo.substack.com/p/article-2", "slug": "article-2"},
        ]},
        status=200,
    )
    nl = _Newsletter("https://foo.substack.com")
    posts = nl.get_posts(limit=10)
    assert len(posts) == 2
    assert posts[0].url == "https://foo.substack.com/p/article-1"


@responses.activate
def test_post_get_metadata_caches():
    responses.add(
        responses.GET,
        "https://foo.substack.com/api/v1/posts/article-1",
        json={"title": "Hello", "post_date": "2026-01-01T00:00:00Z",
              "byline": "Alice", "canonical_url": "https://foo.substack.com/p/article-1",
              "description": "Intro", "body_html": "<p>body</p>"},
        status=200,
    )
    p = _Post("https://foo.substack.com/p/article-1")
    md1 = p.get_metadata()
    md2 = p.get_metadata()
    assert md1["title"] == "Hello"
    assert md1 is md2 or md1 == md2
    # only one HTTP call
    assert len(responses.calls) == 1
```

**Step 2: Verify failure.**

**Step 3: Implement** — append to `src/crypto_research_agent/services/substack.py`:

```python
import requests
from urllib.parse import urlparse
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)

_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_HEADERS = {"User-Agent": _USER_AGENT}


class _Newsletter:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        if not urlparse(self.url).scheme:
            self.url = f"https://{self.url}"
        self._api = f"{self.url}/api/v1"

    def get_posts(self, *, limit: int = 25, offset: int = 0,
                  sorting: str = "new") -> list["_Post"]:
        params = {"sort": sorting, "limit": limit, "offset": offset}
        try:
            r = requests.get(f"{self._api}/posts", headers=_HEADERS,
                             params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("Failed to fetch posts from %s: %s", self.url, e)
            return []
        post_list = data.get("posts", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        posts: list[_Post] = []
        for entry in post_list:
            if not isinstance(entry, dict):
                continue
            url = entry.get("canonical_url") or (
                f"{self.url}/p/{entry['slug']}" if "slug" in entry else None
            )
            if url:
                p = _Post(url)
                p._cached_data = entry
                posts.append(p)
        return posts


class _Post:
    def __init__(self, url: str):
        parsed = urlparse(url if "://" in url else f"https://{url}")
        self.url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        path_parts = parsed.path.strip("/").split("/")
        self.slug = path_parts[-1].split("?")[0].split("#")[0] \
            if len(path_parts) >= 2 and path_parts[-2] == "p" else ""
        self._endpoint = f"{parsed.scheme}://{parsed.netloc}/api/v1/posts/{self.slug}"
        self._cached_data: dict[str, Any] | None = None

    def get_metadata(self) -> dict[str, Any]:
        if self._cached_data is None:
            try:
                r = requests.get(self._endpoint, headers=_HEADERS, timeout=30)
                r.raise_for_status()
                self._cached_data = r.json()
            except Exception as e:
                logger.warning("Failed to fetch post metadata for %s: %s", self.url, e)
                self._cached_data = {}
        return self._cached_data

    def get_content(self) -> str | None:
        data = self.get_metadata()
        for field in ("body_html", "content", "html", "body"):
            if data.get(field):
                return data[field]
        return None
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/substack.py tests/services/test_substack_helpers.py
git commit -m "feat(services): inline Newsletter/Post helpers into substack module"
```

---

### Task D3: `SubstackService` — pagination, age filter, `discover()` and `fetch_posts()`

**Files:**
- Modify: `src/crypto_research_agent/services/substack.py`
- Create: `tests/services/test_substack_service.py`

**Step 1: Failing test**

```python
# tests/services/test_substack_service.py
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import pytest

from crypto_research_agent.services.substack import SubstackService, Article


def _make_post(title="T", days_old=0, body="body"):
    p = MagicMock()
    p.url = f"https://foo.substack.com/p/{title.lower()}"
    date = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    p.get_metadata.return_value = {
        "title": title,
        "post_date": date,
        "byline": "Author",
        "canonical_url": p.url,
        "description": "intro",
    }
    p.get_content.return_value = f"<p>{body}</p>"
    return p


def test_fetch_posts_converts_to_articles(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Name,Substack URL\nFoo,https://foo.substack.com\n")
    svc = SubstackService(csv, request_delay=0.0)
    fake_nl = MagicMock()
    fake_nl.get_posts.return_value = [_make_post("a"), _make_post("b")]
    with patch.object(svc, "_make_newsletter", return_value=fake_nl):
        articles = svc.fetch_posts("https://foo.substack.com",
                                   max_articles=10, max_age_days=None)
    assert len(articles) == 2
    assert isinstance(articles[0], Article)
    assert articles[0].title == "a"


def test_fetch_posts_age_filter_drops_old(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Name,Substack URL\nFoo,https://foo.substack.com\n")
    svc = SubstackService(csv, request_delay=0.0)
    fake_nl = MagicMock()
    # batch 1 has one fresh + one old
    fake_nl.get_posts.side_effect = [
        [_make_post("fresh", 1), _make_post("old", 100)],
        [],  # end of pagination
    ]
    with patch.object(svc, "_make_newsletter", return_value=fake_nl):
        articles = svc.fetch_posts("https://foo.substack.com",
                                   max_articles=100, max_age_days=30)
    titles = [a.title for a in articles]
    assert "fresh" in titles
    assert "old" not in titles


def test_fetch_posts_respects_max_articles(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Name,Substack URL\nFoo,https://foo.substack.com\n")
    svc = SubstackService(csv, request_delay=0.0)
    fake_nl = MagicMock()
    fake_nl.get_posts.return_value = [_make_post(f"p{i}") for i in range(25)]
    with patch.object(svc, "_make_newsletter", return_value=fake_nl):
        articles = svc.fetch_posts("https://foo.substack.com",
                                   max_articles=5, max_age_days=None)
    assert len(articles) == 5
```

**Step 2: Verify failure.**

**Step 3: Implement** — append to `src/crypto_research_agent/services/substack.py`:

```python
import datetime
import time
from pathlib import Path
from typing import Iterator

from ..utils.csv_loader import load_substack_urls


class SubstackService:
    """Discover and fetch Substack posts. Consolidates legacy DatabaseSearch + ArticleRetrieval + API client."""

    PAGE_SIZE = 25

    def __init__(self, csv_path: Path | str, *, request_delay: float = 0.05):
        self._urls = load_substack_urls(Path(csv_path))
        self._delay = request_delay
        logger.info("Loaded %d Substack URLs from %s", len(self._urls), csv_path)

    def discover(self, *, max_age_days: int | None,
                 test_mode: bool) -> Iterator[Article]:
        """Yield articles across all configured Substacks."""
        articles_per_substack = 10 if test_mode else 200
        max_substacks = 30 if test_mode else len(self._urls)
        for url in self._urls[:max_substacks]:
            yield from self.fetch_posts(url, max_articles=articles_per_substack,
                                         max_age_days=max_age_days)
            time.sleep(self._delay)

    def fetch_posts(self, newsletter_url: str, *, max_articles: int,
                     max_age_days: int | None) -> list[Article]:
        nl = self._make_newsletter(newsletter_url)
        articles: list[Article] = []
        offset = 0
        while True:
            batch = nl.get_posts(limit=self.PAGE_SIZE, offset=offset, sorting="new")
            if not batch:
                break
            for post in batch:
                article = self._post_to_article(post)
                if article is None:
                    continue
                if max_age_days is not None and self._is_too_old(article, max_age_days):
                    continue
                articles.append(article)
                if len(articles) >= max_articles:
                    return articles
            if len(batch) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE
            time.sleep(self._delay)
        return articles

    def _make_newsletter(self, url: str) -> _Newsletter:
        return _Newsletter(url)

    @staticmethod
    def _post_to_article(post: _Post) -> Article | None:
        meta = post.get_metadata()
        if not meta:
            return None
        body = post.get_content() or ""
        description = meta.get("description") or ""
        return Article(
            title=meta.get("title", "Unknown Title"),
            author=meta.get("byline", "Unknown Author"),
            date=meta.get("post_date", ""),
            text=f"{description}\n\n{body}".strip(),
            url=meta.get("canonical_url", post.url),
        )

    @staticmethod
    def _is_too_old(article: Article, max_age_days: int) -> bool:
        if not article.date:
            return False
        try:
            d = datetime.datetime.fromisoformat(article.date.replace("Z", "+00:00"))
        except ValueError:
            try:
                d = datetime.datetime.strptime(article.date, "%Y-%m-%d")
                d = d.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                return False
        delta = datetime.datetime.now(datetime.timezone.utc) - d
        return delta.days > max_age_days
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/substack.py tests/services/test_substack_service.py
git commit -m "feat(services): SubstackService with pagination + age filter"
```

---

### Task D4: `services/youtube.py` — `Video` dataclass + filter helpers

**Files:**
- Create: `src/crypto_research_agent/services/youtube.py`
- Create: `tests/services/test_youtube_filters.py`

**Step 1: Failing test**

```python
# tests/services/test_youtube_filters.py
from crypto_research_agent.services.youtube import (
    Video, filter_by_required_terms, score_relevance,
)


def _v(title="", description=""):
    return Video(title=title, channel="C", date="2026-01-01",
                 description=description, video_id="vid", url="u")


def test_filter_requires_all_terms_in_content_and_at_least_one_in_title():
    v_ok = _v(title="Bitcoin ETF news", description="discussion of approval")
    v_no_title = _v(title="Crypto chat", description="Bitcoin ETF mentioned")
    v_missing = _v(title="Bitcoin", description="bitcoin only")
    out = filter_by_required_terms([v_ok, v_no_title, v_missing], ["bitcoin", "etf"])
    assert v_ok in out
    assert v_no_title not in out
    assert v_missing not in out


def test_filter_passes_all_when_no_required_terms():
    vs = [_v(title="x"), _v(title="y")]
    assert filter_by_required_terms(vs, []) == vs


def test_score_relevance_sets_high_for_interview_with_query_match():
    v = _v(title="Bitcoin ETF interview with founder", description="")
    scored = score_relevance(v, query="Bitcoin ETF")
    assert scored.relevance_score == "High"
    assert scored.interview_score >= 10


def test_score_relevance_default_medium():
    v = _v(title="Random video", description="random")
    scored = score_relevance(v, query="Bitcoin ETF")
    assert scored.relevance_score == "Medium"
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/services/youtube.py
from dataclasses import dataclass, field, replace
from typing import Literal


RelevanceScore = Literal["High", "Medium", "Low"]


@dataclass
class Video:
    title: str
    channel: str
    date: str
    description: str
    video_id: str
    url: str
    transcript: str | None = None
    relevance_score: RelevanceScore = "Medium"
    relevance_value: float = 0.0
    interview_score: int = 0
    key_points: list[str] = field(default_factory=list)


_INTERVIEW_KEYWORDS = ("founder", "interview", "ceo", "creator", "with", "exclusive")


def filter_by_required_terms(videos: list[Video], required_terms: list[str]) -> list[Video]:
    if not required_terms:
        return list(videos)
    terms = [t.lower() for t in required_terms if t]
    out: list[Video] = []
    for v in videos:
        title_l = v.title.lower()
        content_l = f"{title_l} {v.description.lower()}"
        if all(t in content_l for t in terms) and any(t in title_l for t in terms):
            out.append(v)
    return out


def score_relevance(video: Video, *, query: str) -> Video:
    title_l = video.title.lower()
    desc_l = video.description.lower()
    query_words = set(query.lower().split())
    title_words = set(title_l.split())
    desc_words = set(desc_l.split())

    if not query_words:
        return video

    title_match = (len(query_words & title_words) / len(query_words)) * 2.0
    desc_match = len(query_words & desc_words) / len(query_words)
    base = title_match + desc_match
    if query.lower() in title_l:
        base += 3.0

    has_interview = any(kw in title_l for kw in _INTERVIEW_KEYWORDS)
    if has_interview and title_match > 0:
        score = base * 3.5
        return replace(video, relevance_score="High", relevance_value=score, interview_score=15)
    if has_interview:
        return replace(video, relevance_score="High", relevance_value=base * 3.0, interview_score=10)
    if title_match > 1.0:
        return replace(video, relevance_score="Medium", relevance_value=base * 1.5, interview_score=5)
    return replace(video, relevance_score="Medium", relevance_value=base, interview_score=0)
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/youtube.py tests/services/test_youtube_filters.py
git commit -m "feat(services): Video dataclass + pure filter/score functions"
```

---

### Task D5: `YouTubeService` — channel videos, transcripts via mocked HTTP

**Files:**
- Modify: `src/crypto_research_agent/services/youtube.py`
- Create: `tests/services/test_youtube_service.py`

**Step 1: Failing test**

```python
# tests/services/test_youtube_service.py
import responses
from pathlib import Path

from crypto_research_agent.services.youtube import YouTubeService


def _channels_csv(tmp_path: Path) -> Path:
    f = tmp_path / "channels.csv"
    f.write_text("Name,Channel ID,YouTube URL\nFoo,UC123,https://youtube.com/@foo\n")
    return f


@responses.activate
def test_search_returns_videos(tmp_path):
    responses.add(
        responses.GET,
        "https://www.googleapis.com/youtube/v3/channels",
        json={"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://www.googleapis.com/youtube/v3/playlistItems",
        json={"items": [{
            "snippet": {
                "title": "Bitcoin ETF news",
                "publishedAt": "2026-01-01T00:00:00Z",
                "channelTitle": "Foo",
                "description": "ETF discussion",
                "resourceId": {"videoId": "vid1"},
            }
        }]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.supadata.ai/v1/youtube/transcript",
        json={"content": "transcript text", "lang": "en"},
        status=200,
    )

    svc = YouTubeService(api_key="k", supadata_key="s",
                        channels_csv=_channels_csv(tmp_path))
    videos = svc.search(
        query="Bitcoin ETF",
        required_terms=["bitcoin", "etf"],
        max_results=5,
        max_age_days=None,
        test_mode=False,
        output_dir=tmp_path / "out",
    )
    assert len(videos) == 1
    assert videos[0].title == "Bitcoin ETF news"
    assert videos[0].transcript == "transcript text"
```

**Step 2: Verify failure.**

**Step 3: Implement** — append to `src/crypto_research_agent/services/youtube.py`:

```python
import re
import time
import datetime
from pathlib import Path
from typing import Any
import requests
import pandas as pd

from ..config import (
    YOUTUBE_API_BASE_URL, SUPADATA_BASE_URL, SUPADATA_TRANSCRIPT_ENDPOINT,
    SUPADATA_REQUEST_DELAY,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class YouTubeService:
    """Search a curated list of YouTube channels, filter by required terms,
    fetch transcripts for top relevance matches."""

    YOUTUBE_REQUEST_DELAY = 0.3

    def __init__(self, *, api_key: str, supadata_key: str, channels_csv: Path | str):
        self._api_key = api_key
        self._supadata_key = supadata_key
        self._channels = pd.read_csv(channels_csv) if Path(channels_csv).exists() else pd.DataFrame()

    def search(self, *, query: str, required_terms: list[str], max_results: int,
               max_age_days: int | None, test_mode: bool, output_dir: Path) -> list[Video]:
        if self._channels.empty:
            return []
        chans = self._channels.head(2) if test_mode else self._channels
        all_videos: list[Video] = []
        for _, channel in chans.iterrows():
            videos = self._channel_videos(
                channel_id=channel.get("Channel ID", ""),
                channel_url=channel.get("YouTube URL", ""),
                max_age_days=max_age_days,
            )
            all_videos.extend(videos)
            if test_mode and len(filter_by_required_terms(all_videos, required_terms)) >= 2:
                break

        filtered = filter_by_required_terms(all_videos, required_terms)
        scored = sorted(
            (score_relevance(v, query=query) for v in filtered),
            key=lambda v: v.relevance_value,
            reverse=True,
        )[:max_results]

        return self._with_transcripts(scored, output_dir=output_dir)

    def _channel_videos(self, *, channel_id: str, channel_url: str,
                         max_age_days: int | None) -> list[Video]:
        if not channel_id or not channel_id.startswith("UC"):
            logger.debug("Skipping channel with no Channel ID: %s", channel_url)
            return []
        playlist_id = self._get_uploads_playlist(channel_id)
        if not playlist_id:
            return []
        return self._playlist_videos(playlist_id, max_age_days=max_age_days)

    def _get_uploads_playlist(self, channel_id: str) -> str | None:
        time.sleep(self.YOUTUBE_REQUEST_DELAY)
        r = requests.get(
            f"{YOUTUBE_API_BASE_URL}/channels",
            params={"key": self._api_key, "part": "contentDetails", "id": channel_id},
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning("YouTube channels endpoint error %s", r.status_code)
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def _playlist_videos(self, playlist_id: str, *,
                          max_age_days: int | None) -> list[Video]:
        videos: list[Video] = []
        page_token: str | None = None
        for _ in range(4):  # max 4 pages = 200 videos
            time.sleep(self.YOUTUBE_REQUEST_DELAY)
            params: dict[str, Any] = {
                "key": self._api_key,
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            r = requests.get(f"{YOUTUBE_API_BASE_URL}/playlistItems", params=params, timeout=30)
            if r.status_code != 200:
                break
            data = r.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                published = snippet.get("publishedAt", "")
                if max_age_days is not None and published:
                    try:
                        d = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
                        if (datetime.datetime.now(datetime.timezone.utc) - d).days > max_age_days:
                            continue
                    except ValueError:
                        pass
                vid = snippet.get("resourceId", {}).get("videoId", "")
                videos.append(Video(
                    title=snippet.get("title", ""),
                    channel=snippet.get("channelTitle", ""),
                    date=published,
                    description=snippet.get("description", ""),
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                ))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return videos

    def _with_transcripts(self, videos: list[Video], *, output_dir: Path) -> list[Video]:
        out: list[Video] = []
        for v in videos:
            transcript = self._fetch_transcript(v.video_id)
            if transcript is None:
                continue
            v_with = replace(v, transcript=transcript)
            self._save_transcript(v_with, output_dir=output_dir)
            out.append(v_with)
        return out

    def _fetch_transcript(self, video_id: str) -> str | None:
        if not video_id:
            return None
        time.sleep(SUPADATA_REQUEST_DELAY)
        r = requests.get(
            f"{SUPADATA_BASE_URL}{SUPADATA_TRANSCRIPT_ENDPOINT}",
            headers={"x-api-key": self._supadata_key},
            params={"text": "true", "videoId": video_id},
            timeout=30,
        )
        if r.status_code != 200:
            logger.info("No transcript for %s (status %s)", video_id, r.status_code)
            return None
        return r.json().get("content")

    def _save_transcript(self, video: Video, *, output_dir: Path) -> None:
        if not video.transcript:
            return
        out = Path(output_dir) / "transcripts"
        out.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[\\/*?:\"<>|]", "_", video.title)[:100]
        (out / f"{safe}_transcript.txt").write_text(video.transcript, encoding="utf-8")
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/youtube.py tests/services/test_youtube_service.py
git commit -m "feat(services): YouTubeService with channel videos + transcripts"
```

---

### Task D6: `services/docx_export.py` — port `CloudConvertClient`

**Files:**
- Create: `src/crypto_research_agent/services/docx_export.py`
- Create: `tests/services/test_docx_export.py`

**Step 1: Failing test**

```python
# tests/services/test_docx_export.py
import responses
from pathlib import Path

from crypto_research_agent.services.docx_export import DocxExporter


@responses.activate
def test_convert_markdown_to_docx_full_lifecycle(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("# Test\nbody", encoding="utf-8")

    responses.add(
        responses.POST, "https://api.cloudconvert.com/v2/jobs", status=201,
        json={"data": {
            "id": "job-1",
            "tasks": [{
                "name": "import-my-file",
                "result": {"form": {"url": "https://upload.example.com",
                                     "parameters": {}}},
            }],
        }},
    )
    responses.add(
        responses.POST, "https://upload.example.com", status=201, body="",
    )
    responses.add(
        responses.GET, "https://api.cloudconvert.com/v2/jobs/job-1", status=200,
        json={"data": {
            "id": "job-1", "status": "finished",
            "tasks": [{
                "name": "export-my-file",
                "result": {"files": [{"url": "https://download.example.com/file.docx"}]},
            }],
        }},
    )
    responses.add(
        responses.GET, "https://download.example.com/file.docx", status=200,
        body=b"PK\x03\x04docx-bytes",
    )

    exp = DocxExporter(api_key="ck-test")
    out = exp.convert_markdown_to_docx(md)
    assert out == md.with_suffix(".docx")
    assert out.exists() and out.read_bytes().startswith(b"PK")
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/services/docx_export.py
import time
from pathlib import Path
import requests

from ..config import CLOUDCONVERT_BASE_URL
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DocxExporter:
    """Convert markdown to DOCX via CloudConvert."""

    def __init__(self, *, api_key: str, base_url: str = CLOUDCONVERT_BASE_URL):
        self._api_key = api_key
        self._base = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def convert_markdown_to_docx(self, input_path: Path | str) -> Path:
        in_path = Path(input_path)
        if not in_path.exists():
            raise FileNotFoundError(input_path)
        out_path = in_path.with_suffix(".docx")

        job = self._create_job()
        upload_task = next(t for t in job["tasks"] if t["name"] == "import-my-file")
        upload_url = upload_task["result"]["form"]["url"]
        upload_params = upload_task["result"]["form"]["parameters"]

        with in_path.open("rb") as fh:
            r = requests.post(upload_url, data=upload_params, files={"file": fh})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Upload failed: {r.text}")

        completed = self._wait_finished(job["id"])
        export_task = next(t for t in completed["tasks"] if t["name"] == "export-my-file")
        download_url = export_task["result"]["files"][0]["url"]
        self._download(download_url, out_path)
        logger.info("DOCX written to %s", out_path)
        return out_path

    def _create_job(self) -> dict:
        payload = {
            "tasks": {
                "import-my-file": {"operation": "import/upload"},
                "convert-my-file": {
                    "operation": "convert", "input": "import-my-file",
                    "output_format": "docx", "engine": "pandoc",
                },
                "export-my-file": {"operation": "export/url", "input": "convert-my-file"},
            }
        }
        r = requests.post(f"{self._base}/jobs", headers=self._headers, json=payload)
        r.raise_for_status()
        return r.json()["data"]

    def _wait_finished(self, job_id: str, *, timeout: int = 300) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.get(f"{self._base}/jobs/{job_id}", headers=self._headers)
            r.raise_for_status()
            data = r.json()["data"]
            if data["status"] == "finished":
                return data
            if data["status"] in ("error", "canceled"):
                raise RuntimeError(f"DOCX conversion {data['status']}")
            time.sleep(2)
        raise TimeoutError(f"DOCX conversion timed out after {timeout}s")

    def _download(self, url: str, out_path: Path) -> None:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with out_path.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=8192):
                fh.write(chunk)
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/docx_export.py tests/services/test_docx_export.py
git commit -m "feat(services): DocxExporter with full CloudConvert lifecycle"
```

---

### Task D7: `services/tweet_extractor.py`

**Files:**
- Create: `src/crypto_research_agent/services/tweet_extractor.py`
- Create: `tests/services/test_tweet_extractor.py`

**Step 1: Failing test**

```python
# tests/services/test_tweet_extractor.py
from unittest.mock import patch, MagicMock
from pathlib import Path

from crypto_research_agent.services.tweet_extractor import TweetExtractor, Tweet


def test_extract_returns_tweets_with_files(tmp_path):
    urls_file = tmp_path / "tweets.txt"
    urls_file.write_text("https://twitter.com/x/status/1\nhttps://twitter.com/y/status/2\n")
    fake_page = MagicMock()
    fake_page.evaluate.side_effect = ["First tweet text", "Second tweet text"]
    fake_browser = MagicMock()
    fake_context = MagicMock()
    fake_context.new_page.return_value = fake_page
    fake_browser.new_context.return_value = fake_context

    pw_cm = MagicMock()
    pw_cm.__enter__.return_value = MagicMock(chromium=MagicMock(launch=MagicMock(return_value=fake_browser)))
    pw_cm.__exit__.return_value = False

    extractor = TweetExtractor()
    with patch("crypto_research_agent.services.tweet_extractor.sync_playwright", return_value=pw_cm):
        with patch("time.sleep"):
            tweets = extractor.extract(urls_file, output_dir=tmp_path)
    assert len(tweets) == 2
    assert tweets[0].text == "First tweet text"
    assert (tmp_path / "tweets" / "tweet_1.txt").exists()


def test_missing_file_returns_empty(tmp_path):
    extractor = TweetExtractor()
    assert extractor.extract(tmp_path / "missing.txt", output_dir=tmp_path) == []
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/services/tweet_extractor.py
from dataclasses import dataclass
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Tweet:
    title: str
    text: str
    url: str
    file_path: Path


class TweetExtractor:
    def extract(self, urls_file: Path | str, *, output_dir: Path | str) -> list[Tweet]:
        urls_file = Path(urls_file)
        if not urls_file.exists():
            logger.warning("Tweets file not found: %s", urls_file)
            return []
        urls = [u.strip() for u in urls_file.read_text(encoding="utf-8").splitlines() if u.strip()]
        out_dir = Path(output_dir) / "tweets"
        out_dir.mkdir(parents=True, exist_ok=True)

        results: list[Tweet] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            for i, url in enumerate(urls, start=1):
                text = self._extract_one(page, url)
                if not text:
                    continue
                file_path = out_dir / f"tweet_{i}.txt"
                file_path.write_text(text, encoding="utf-8")
                results.append(Tweet(title=f"Tweet {i}", text=text, url=url, file_path=file_path))
                time.sleep(1)
        return results

    def _extract_one(self, page, url: str) -> str | None:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector('[data-testid="tweetText"]', timeout=10000)
            return page.evaluate(
                'document.querySelector(\'[data-testid="tweetText"]\')?.textContent ?? null'
            )
        except Exception as e:
            logger.warning("Tweet extraction failed for %s: %s", url, e)
            return None
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/tweet_extractor.py tests/services/test_tweet_extractor.py
git commit -m "feat(services): TweetExtractor with mockable Playwright wrapper"
```

---

### Task D8: `services/user_content.py`

**Files:**
- Create: `src/crypto_research_agent/services/user_content.py`
- Create: `tests/services/test_user_content.py`

**Step 1: Failing test**

```python
# tests/services/test_user_content.py
from unittest.mock import MagicMock
from pathlib import Path

from crypto_research_agent.services.user_content import UserContentService, UserContent


def test_collect_processes_text_files(tmp_path):
    (tmp_path / "note.txt").write_text("This is a research note about Bitcoin.")
    analyzer = MagicMock()
    analyzer.extract_insights.return_value = (["insight 1"], ["Bitcoin"])
    svc = UserContentService(analyzer=analyzer)
    items = svc.collect(tmp_path)
    assert len(items) == 1
    assert items[0].file_type == "text"
    assert items[0].title == "note"
    assert items[0].mentioned_projects == ["Bitcoin"]


def test_collect_skips_oversize_files(tmp_path):
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB > 1 MB text limit
    analyzer = MagicMock()
    svc = UserContentService(analyzer=analyzer)
    assert svc.collect(tmp_path) == []


def test_collect_handles_empty_dir(tmp_path):
    svc = UserContentService(analyzer=MagicMock())
    assert svc.collect(tmp_path) == []
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/services/user_content.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Callable
import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)

FileType = Literal["text", "pdf", "csv", "tweet"]

_MAX_BYTES = {
    "text": 1 * 1024 * 1024,
    "pdf": 10 * 1024 * 1024,
    "csv": 5 * 1024 * 1024,
}


@dataclass
class UserContent:
    title: str
    author: str
    text: str
    url: str
    file_type: FileType
    key_insights: list[str] = field(default_factory=list)
    mentioned_projects: list[str] = field(default_factory=list)


class UserContentService:
    """Collects user-supplied files (txt/md/pdf/csv) and runs analyzer for insights."""

    def __init__(self, *, analyzer):
        self._analyzer = analyzer

    def collect(self, content_dir: Path | str) -> list[UserContent]:
        content_dir = Path(content_dir)
        if not content_dir.exists():
            return []
        out: list[UserContent] = []
        for path in sorted(content_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name.lower() == "tweets.txt":
                continue  # processed separately by TweetExtractor
            handler = self._dispatch(path)
            if handler is None:
                continue
            try:
                item = handler(path)
                if item is not None:
                    out.append(item)
            except Exception as e:
                logger.warning("Failed to process %s: %s", path.name, e)
        return out

    def _dispatch(self, path: Path) -> Callable[[Path], UserContent | None] | None:
        suffix = path.suffix.lower()
        if suffix in (".txt", ".md"):
            return self._process_text
        if suffix == ".pdf":
            return self._process_pdf
        if suffix == ".csv":
            return self._process_csv
        return None

    def _check_size(self, path: Path, file_type: str) -> bool:
        if path.stat().st_size > _MAX_BYTES[file_type]:
            logger.warning("Skipping %s: exceeds %d bytes", path.name, _MAX_BYTES[file_type])
            return False
        return True

    def _process_text(self, path: Path) -> UserContent | None:
        if not self._check_size(path, "text"):
            return None
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return None
        insights, projects = self._analyzer.extract_insights(content)
        return UserContent(
            title=path.stem, author="User Provided",
            text=content[:5000], url=f"file://{path}", file_type="text",
            key_insights=insights, mentioned_projects=projects,
        )

    def _process_pdf(self, path: Path) -> UserContent | None:
        if not self._check_size(path, "pdf"):
            return None
        import pdfplumber
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n\n"
        if not text.strip():
            return None
        insights, projects = self._analyzer.extract_insights(text)
        return UserContent(
            title=path.stem, author="User Provided",
            text=text[:5000], url=f"file://{path}", file_type="pdf",
            key_insights=insights, mentioned_projects=projects,
        )

    def _process_csv(self, path: Path) -> UserContent | None:
        if not self._check_size(path, "csv"):
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")
        if not content.strip():
            return None
        insights, projects = self._analyzer.extract_insights(content[:8000])
        return UserContent(
            title=path.stem, author="User Provided",
            text=f"CSV DATA:\n\n{content[:5000]}", url=f"file://{path}", file_type="csv",
            key_insights=insights, mentioned_projects=projects,
        )
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/services/user_content.py tests/services/test_user_content.py
git commit -m "feat(services): UserContentService with file-type dispatch + size limits"
```

---

## Phase E — Real Agents

### Task E1: `agents/coordinator.py`

**Files:**
- Create: `src/crypto_research_agent/agents/coordinator.py`
- Create: `tests/agents/__init__.py` (empty)
- Create: `tests/agents/test_coordinator.py`

**Step 1: Failing test**

```python
# tests/agents/test_coordinator.py
from unittest.mock import MagicMock

from crypto_research_agent.agents.coordinator import Coordinator, SearchPlan


def test_plan_returns_search_plan_with_main_topic_and_terms():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "main_topic": "Bitcoin ETF",
        "required_terms": ["bitcoin", "etf"],
    }
    coord = Coordinator(backend, model="m")
    plan = coord.plan("Bitcoin ETF inflows")
    assert isinstance(plan, SearchPlan)
    assert plan.main_topic == "Bitcoin ETF"
    assert plan.required_terms == ["bitcoin", "etf"]


def test_plan_falls_back_when_llm_returns_garbage():
    backend = MagicMock()
    backend.complete_json.return_value = {}
    coord = Coordinator(backend, model="m")
    plan = coord.plan("something")
    assert plan.main_topic == "something"
    assert plan.required_terms == []


def test_plan_filters_invalid_terms():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "main_topic": "x",
        "required_terms": ["bitcoin", "", None, "etf"],
    }
    coord = Coordinator(backend, model="m")
    plan = coord.plan("q")
    assert plan.required_terms == ["bitcoin", "etf"]
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/agents/coordinator.py
from dataclasses import dataclass


COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for a crypto research workflow.
Analyze the user's research query and respond with valid JSON containing:
- main_topic: The primary cryptocurrency or blockchain topic
- required_terms: Terms STRICTLY from the user's query — never add extras not in the query
"""


@dataclass(frozen=True)
class SearchPlan:
    main_topic: str
    required_terms: list[str]


class Coordinator:
    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def plan(self, query: str) -> SearchPlan:
        result = self._backend.complete_json(
            prompt=query, model=self._model,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
        )
        terms = [
            str(t).strip() for t in result.get("required_terms", [])
            if t and isinstance(t, str) and t.strip()
        ]
        return SearchPlan(
            main_topic=result.get("main_topic") or query,
            required_terms=terms,
        )
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/coordinator.py tests/agents/test_coordinator.py tests/agents/__init__.py
git commit -m "feat(agents): Coordinator returns typed SearchPlan"
```

---

### Task E2: `agents/analyzer.py`

**Files:**
- Create: `src/crypto_research_agent/agents/analyzer.py`
- Create: `tests/agents/test_analyzer.py`

**Step 1: Failing test**

```python
# tests/agents/test_analyzer.py
from unittest.mock import MagicMock
from crypto_research_agent.agents.analyzer import Analyzer, AnalyzedItem
from crypto_research_agent.services.substack import Article


def _article():
    return Article(title="Bitcoin ETF approved",
                   author="A", date="2026-01-01",
                   text="The SEC approved Bitcoin ETF.", url="u")


def test_analyze_article_returns_analyzed_item():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "relevance_score": "High",
        "key_insights": ["SEC approved"],
        "mentioned_projects": ["Bitcoin"],
        "thesis_alignment": "Not Applicable",
    }
    analyzer = Analyzer(backend, model="m")
    result = analyzer.analyze(_article(), main_topic="Bitcoin ETF", thesis=None)
    assert isinstance(result, AnalyzedItem)
    assert result.relevance_score == "High"
    assert result.key_insights == ["SEC approved"]


def test_analyze_returns_none_for_non_english():
    backend = MagicMock()
    backend.complete_json.return_value = {"non_english": True, "language_detected": "Spanish"}
    analyzer = Analyzer(backend, model="m")
    assert analyzer.analyze(_article(), main_topic="x", thesis=None) is None


def test_analyze_uses_thesis_alignment_when_provided():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "relevance_score": "Medium",
        "thesis_alignment": "High",
        "thesis_alignment_explanation": "matches",
        "key_insights": [],
        "mentioned_projects": [],
    }
    analyzer = Analyzer(backend, model="m")
    result = analyzer.analyze(_article(), main_topic="x", thesis="my thesis")
    assert result.relevance_score == "High"  # promoted from thesis_alignment


def test_analyze_batch_short_circuits_in_test_mode():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "relevance_score": "High", "key_insights": [], "mentioned_projects": [],
        "thesis_alignment": "Not Applicable",
    }
    analyzer = Analyzer(backend, model="m")
    results = analyzer.analyze_batch(
        [_article(), _article(), _article(), _article()],
        main_topic="x", thesis=None, test_mode=True,
    )
    assert len(results) == 2  # stops after 2 high/medium
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/agents/analyzer.py
from dataclasses import dataclass, field
from typing import Literal

from ..services.substack import Article
from ..services.youtube import Video
from ..utils.token_utils import truncate_to_token_limit
from ..utils.logger import get_logger

logger = get_logger(__name__)

RelevanceScore = Literal["High", "Medium", "Low", "Error"]


@dataclass
class AnalyzedItem:
    title: str
    author: str
    date: str
    url: str
    text: str
    relevance_score: RelevanceScore
    key_insights: list[str] = field(default_factory=list)
    mentioned_projects: list[str] = field(default_factory=list)
    thesis_alignment: str = "Not Applicable"
    relevance_explanation: str = ""

    def to_legacy_dict(self) -> dict:
        return {
            "title": self.title, "author": self.author, "date": self.date, "url": self.url,
            "text": self.text, "relevance_score": self.relevance_score,
            "key_insights": self.key_insights, "mentioned_projects": self.mentioned_projects,
            "thesis_alignment": self.thesis_alignment,
            "relevance_explanation": self.relevance_explanation,
        }


class Analyzer:
    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def analyze(self, item: Article | Video,
                *, main_topic: str, thesis: str | None) -> AnalyzedItem | None:
        text_sample = truncate_to_token_limit(self._extract_text(item), self._model, 1500)
        thesis_info = f"\nThesis Direction: {thesis}" if thesis else ""
        prompt = f"""Analyze this crypto content for relevance.

Search Topic: {main_topic}{thesis_info}

Content:
Title: {item.title}
{text_sample}

CRITICAL: First check if the content is in English.
- If NOT in English, return: {{"non_english": true, "language_detected": "..."}}
- If in English, return JSON with: relevance_score (High/Medium/Low),
  relevance_explanation, key_insights (list), mentioned_projects (list),
  thesis_alignment (High/Medium/Low/Not Applicable), thesis_alignment_explanation."""

        result = self._backend.complete_json(
            prompt=prompt, model=self._model,
            system_prompt="You evaluate crypto content. Respond with valid JSON only.",
        )
        if not result:
            return AnalyzedItem(
                title=item.title, author=getattr(item, "author", getattr(item, "channel", "")),
                date=item.date, url=item.url, text=self._extract_text(item),
                relevance_score="Error", relevance_explanation="LLM returned empty response",
            )
        if result.get("non_english"):
            logger.info("Discarding non-English: %s (%s)",
                        item.title, result.get("language_detected", "?"))
            return None
        score = result.get("relevance_score", "Low")
        if thesis and result.get("thesis_alignment") not in ("Not Applicable", "Error", None):
            score = result["thesis_alignment"]
        return AnalyzedItem(
            title=item.title,
            author=getattr(item, "author", getattr(item, "channel", "")),
            date=item.date, url=item.url, text=self._extract_text(item),
            relevance_score=score,
            key_insights=result.get("key_insights", []),
            mentioned_projects=result.get("mentioned_projects", []),
            thesis_alignment=result.get("thesis_alignment", "Not Applicable"),
            relevance_explanation=result.get("relevance_explanation", ""),
        )

    def analyze_batch(self, items, *, main_topic, thesis, test_mode=False) -> list[AnalyzedItem]:
        analyzed: list[AnalyzedItem] = []
        relevant_count = 0
        for i, item in enumerate(items):
            logger.info("Analyzing %d/%d: %s", i + 1, len(items), item.title)
            r = self.analyze(item, main_topic=main_topic, thesis=thesis)
            if r is None:
                continue
            analyzed.append(r)
            if test_mode and r.relevance_score in ("High", "Medium"):
                relevant_count += 1
                if relevant_count >= 2:
                    logger.info("Test mode: %d relevant items found, stopping", relevant_count)
                    break
        return analyzed

    def extract_insights(self, content: str) -> tuple[list[str], list[str]]:
        """Used by UserContentService — returns (key_insights, mentioned_projects)."""
        sample = truncate_to_token_limit(content, self._model, 1500)
        prompt = f"""Extract insights from this user-provided content.
{sample}

Return JSON with: key_insights (list of strings), mentioned_projects (list of strings)."""
        result = self._backend.complete_json(
            prompt=prompt, model=self._model,
            system_prompt="Respond with valid JSON only.",
        )
        return (
            result.get("key_insights", []),
            result.get("mentioned_projects", []),
        )

    @staticmethod
    def _extract_text(item) -> str:
        if isinstance(item, Article):
            return item.text or ""
        if isinstance(item, Video):
            return f"{item.description}\n\n{item.transcript or ''}"
        return ""
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/analyzer.py tests/agents/test_analyzer.py
git commit -m "feat(agents): Analyzer with typed AnalyzedItem and batch + insights"
```

---

### Task E3: `agents/summarizer.py`

**Files:**
- Create: `src/crypto_research_agent/agents/summarizer.py`
- Create: `tests/agents/test_summarizer.py`

**Step 1: Failing test**

```python
# tests/agents/test_summarizer.py
from unittest.mock import MagicMock
from crypto_research_agent.agents.summarizer import Summarizer
from crypto_research_agent.agents.analyzer import AnalyzedItem


def _item(title="t", score="High"):
    return AnalyzedItem(title=title, author="a", date="d", url="u", text="t",
                        relevance_score=score, key_insights=["i"])


def test_summarize_returns_markdown():
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="# AI Agent Search Results\n...")
    summer = Summarizer(backend, model="m")
    out = summer.summarize(
        articles=[_item("A1")], videos=[],
        query="bitcoin", thesis=None,
    )
    assert out.startswith("# AI Agent Search Results")


def test_summarize_returns_no_results_message_when_empty():
    summer = Summarizer(MagicMock(), model="m")
    out = summer.summarize(articles=[], videos=[], query="x", thesis=None)
    assert "No relevant content found" in out
```

**Step 2: Verify failure.**

**Step 3: Implement** — port `agents/summarization.py` to a clean class with the same prompt structure but typed inputs (`list[AnalyzedItem]`). For brevity, the prompt body is ~150 LOC unchanged from the original; preserve it verbatim under the new class.

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/summarizer.py tests/agents/test_summarizer.py
git commit -m "feat(agents): Summarizer returns research markdown"
```

---

### Task E4: `agents/style_learner.py` — `StyleCard` dataclass

**Files:**
- Create: `src/crypto_research_agent/agents/style_card.py`
- Create: `tests/agents/test_style_card.py`

**Step 1: Failing test**

```python
# tests/agents/test_style_card.py
from crypto_research_agent.agents.style_card import StyleCard, Vocabulary


def test_format_for_prompt_contains_all_sections():
    card = StyleCard(
        tone="analytical", sentence_patterns="short and punchy",
        vocabulary=Vocabulary(preferred=["on-chain"], avoided=["massive"]),
        paragraph_structure="claim then evidence",
        section_openings="bold assertions",
        transitions=["That said,"],
        example_excerpts=["Excerpt 1."],
    )
    out = card.format_for_prompt()
    assert "## Writing Style Guide" in out
    assert "analytical" in out
    assert "on-chain" in out
    assert "massive" in out
    assert "Excerpt 1." in out


def test_to_dict_and_from_dict_roundtrip():
    card = StyleCard.fallback()
    assert StyleCard.from_dict(card.to_dict()) == card
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/agents/style_card.py
from dataclasses import dataclass, field, asdict


@dataclass
class Vocabulary:
    preferred: list[str] = field(default_factory=list)
    avoided: list[str] = field(default_factory=list)


@dataclass
class StyleCard:
    tone: str
    sentence_patterns: str
    vocabulary: Vocabulary
    paragraph_structure: str
    section_openings: str
    transitions: list[str]
    example_excerpts: list[str]

    def format_for_prompt(self) -> str:
        excerpts = "".join(f"\n> {x}\n" for x in self.example_excerpts)
        preferred = ", ".join(self.vocabulary.preferred) or "none specified"
        avoided = ", ".join(self.vocabulary.avoided) or "none specified"
        transitions = ", ".join(f'"{t}"' for t in self.transitions) or "none specified"
        return f"""## Writing Style Guide

**Tone:** {self.tone}
**Sentence patterns:** {self.sentence_patterns}
**Paragraph structure:** {self.paragraph_structure}
**Section openings:** {self.section_openings}
**Preferred transitions:** {transitions}
**Vocabulary to use:** {preferred}
**Vocabulary to avoid:** {avoided}

## Example Excerpts from the Author's Writing
{excerpts}
Match this voice precisely. Every section you write — including rewrites — must sound like these excerpts."""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StyleCard":
        v = d.get("vocabulary") or {}
        return cls(
            tone=d.get("tone", ""),
            sentence_patterns=d.get("sentence_patterns", ""),
            vocabulary=Vocabulary(
                preferred=v.get("preferred", []) if isinstance(v, dict) else [],
                avoided=v.get("avoided", []) if isinstance(v, dict) else [],
            ),
            paragraph_structure=d.get("paragraph_structure", ""),
            section_openings=d.get("section_openings", ""),
            transitions=d.get("transitions", []) or [],
            example_excerpts=d.get("example_excerpts", []) or [],
        )

    @classmethod
    def fallback(cls) -> "StyleCard":
        return cls(
            tone="analytical and informative",
            sentence_patterns="clear and direct",
            vocabulary=Vocabulary(),
            paragraph_structure="structured with clear points",
            section_openings="direct assertions",
            transitions=[],
            example_excerpts=[],
        )
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/style_card.py tests/agents/test_style_card.py
git commit -m "feat(agents): StyleCard dataclass with format_for_prompt"
```

---

### Task E5: `agents/style_learner.py` — sample loading + LLM extraction

**Files:**
- Create: `src/crypto_research_agent/agents/style_learner.py`
- Create: `tests/agents/test_style_learner.py`

**Step 1: Failing test**

```python
# tests/agents/test_style_learner.py
import json
from unittest.mock import MagicMock
from crypto_research_agent.agents.style_learner import StyleLearner
from crypto_research_agent.agents.style_card import StyleCard


def test_load_samples_handles_txt(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "a.txt").write_text("Sample one.")
    (samples / "README.txt").write_text("ignore me")
    learner = StyleLearner(MagicMock(), model="m",
                           samples_dir=samples,
                           instructions_file=tmp_path / "missing.txt")
    materials = learner.get_raw_materials()
    titles = [s["filename"] for s in materials["samples"]]
    assert "a.txt" in titles
    assert "README.txt" not in titles


def test_generate_style_card_parses_llm_json(tmp_path):
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text=json.dumps({
        "tone": "analytical",
        "sentence_patterns": "short",
        "vocabulary": {"preferred": ["on-chain"], "avoided": ["huge"]},
        "paragraph_structure": "claim then evidence",
        "section_openings": "bold assertions",
        "transitions": ["That said,"],
        "example_excerpts": ["Sample."],
    }))
    learner = StyleLearner(backend, model="m",
                           samples_dir=tmp_path, instructions_file=tmp_path / "i.txt")
    card = learner.generate_style_card({"samples": [], "instructions": ""})
    assert isinstance(card, StyleCard)
    assert card.tone == "analytical"


def test_generate_style_card_falls_back_on_garbage(tmp_path):
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="not json at all")
    learner = StyleLearner(backend, model="m",
                           samples_dir=tmp_path, instructions_file=tmp_path / "i.txt")
    card = learner.generate_style_card({"samples": [], "instructions": ""})
    assert card == StyleCard.fallback()
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/agents/style_learner.py
import json
import re
from pathlib import Path
import docx as docx_lib

from .style_card import StyleCard
from ..utils.token_utils import truncate_to_token_limit
from ..utils.logger import get_logger

logger = get_logger(__name__)


JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class StyleLearner:
    def __init__(self, backend, *, model: str,
                 samples_dir: Path, instructions_file: Path):
        self._backend = backend
        self._model = model
        self._samples_dir = Path(samples_dir)
        self._instructions_file = Path(instructions_file)

    def get_raw_materials(self) -> dict:
        samples = []
        if self._samples_dir.exists():
            for f in self._samples_dir.iterdir():
                if not f.is_file() or f.name == "README.txt":
                    continue
                if f.suffix.lower() == ".txt":
                    samples.append({"filename": f.name,
                                     "content": f.read_text(encoding="utf-8")})
                elif f.suffix.lower() == ".docx":
                    doc = docx_lib.Document(str(f))
                    samples.append({"filename": f.name,
                                     "content": "\n".join(p.text for p in doc.paragraphs)})
        instructions = (
            self._instructions_file.read_text(encoding="utf-8")
            if self._instructions_file.exists() else ""
        )
        return {"samples": samples, "instructions": instructions}

    def generate_style_card(self, materials: dict) -> StyleCard:
        samples_text = ""
        for s in materials.get("samples", []):
            content = truncate_to_token_limit(s.get("content", ""), self._model, 3000)
            samples_text += f"\n--- {s.get('filename', 'sample')} ---\n{content}\n"
        instructions = materials.get("instructions") or ""
        instr_block = f"\nExplicit writing instructions from author:\n{instructions}" if instructions else ""

        prompt = f"""Analyze these writing samples and produce a style card capturing the author's voice precisely.

{samples_text}{instr_block}

Return JSON with these keys:
- tone (string)
- sentence_patterns (string)
- vocabulary: {{ preferred: list, avoided: list }}
- paragraph_structure (string)
- section_openings (string)
- transitions (list of strings)
- example_excerpts (list of 3-5 verbatim excerpts)

Focus on what makes this voice distinctive and reproducible."""

        response = self._backend.complete(
            prompt=prompt, model=self._model,
            system_prompt="Extract precise, actionable style characteristics. Respond with valid JSON only.",
        )
        return self._parse(response.text)

    @staticmethod
    def _parse(text: str) -> StyleCard:
        try:
            return StyleCard.from_dict(json.loads(text))
        except json.JSONDecodeError:
            pass
        match = JSON_OBJECT_RE.search(text)
        if match:
            try:
                return StyleCard.from_dict(json.loads(match.group()))
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse style card; using fallback")
        return StyleCard.fallback()
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/style_learner.py tests/agents/test_style_learner.py
git commit -m "feat(agents): StyleLearner generates StyleCard from samples"
```

---

### Task E6: `agents/outline_writer.py`

**Files:**
- Create: `src/crypto_research_agent/agents/outline_writer.py`
- Create: `tests/agents/test_outline_writer.py`

**Step 1: Failing test**

```python
# tests/agents/test_outline_writer.py
from unittest.mock import MagicMock
from crypto_research_agent.agents.outline_writer import OutlineWriter


def test_generate_returns_markdown_outline():
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="# Outline\n## 1. Intro\n- bullet")
    ow = OutlineWriter(backend, model="m")
    out = ow.generate(articles=[], videos=[], user_content=[],
                     query="bitcoin", thesis=None, user_content_only=False)
    assert "## 1." in out


def test_revise_returns_string():
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="# Outline\n## 1. Updated\n- bullet")
    ow = OutlineWriter(backend, model="m")
    out = ow.revise(current="# Outline\n## 1. Old", instructions="rename",
                    articles=[], videos=[], user_content=[],
                    query="x", thesis=None)
    assert "Updated" in out
```

**Step 2: Verify failure.**

**Step 3: Implement** — port the long system prompt from `agents/outline_generator.py` verbatim, but split shared prompt text into a module-level constant. The class receives an injected backend and exposes only `generate(...)` and `revise(...)`.

```python
# src/crypto_research_agent/agents/outline_writer.py
from ..utils.logger import get_logger

logger = get_logger(__name__)


_SHARED_GUIDELINES = """You are an expert cryptocurrency researcher creating outlines.

Guidelines:
- Numbered main sections (## 1. Title, ## 2. Title)
- Numbered subsections (### 1.1 Title)
- Bullet points within subsections
- Source citations in [Title] brackets
- Number of sections fits the content; do NOT default to 5

Format:
# Research Article Outline: [Title]
## 1. Introduction
- Hook
- Thesis
## N. Conclusion
- Implications
"""


class OutlineWriter:
    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def generate(self, *, articles, videos, user_content, query: str,
                 thesis: str | None, user_content_only: bool) -> str:
        sys_prompt = self._build_system_prompt(
            has_user_content=bool(user_content),
            user_content_only=user_content_only,
        )
        user_prompt = self._build_user_prompt(
            articles, videos, user_content, query, thesis, current_outline=None,
            instructions=None,
        )
        return self._backend.complete(prompt=user_prompt, model=self._model,
                                       system_prompt=sys_prompt).text

    def revise(self, *, current: str, instructions: str,
               articles, videos, user_content, query: str,
               thesis: str | None) -> str:
        sys_prompt = self._build_system_prompt(has_user_content=bool(user_content),
                                                 user_content_only=False,
                                                 is_revision=True)
        user_prompt = self._build_user_prompt(
            articles, videos, user_content, query, thesis,
            current_outline=current, instructions=instructions,
        )
        return self._backend.complete(prompt=user_prompt, model=self._model,
                                       system_prompt=sys_prompt).text

    def _build_system_prompt(self, *, has_user_content: bool,
                              user_content_only: bool,
                              is_revision: bool = False) -> str:
        prompt = _SHARED_GUIDELINES
        if user_content_only:
            prompt += "\nNo Substack/YouTube content found. Use ONLY user-provided content."
        if has_user_content:
            prompt += "\nIntegrate user-provided content thoroughly. Cite [User Content Title]."
        if is_revision:
            prompt += "\nAddress the user's revision instructions while preserving format."
        return prompt

    def _build_user_prompt(self, articles, videos, user_content, query,
                           thesis, current_outline, instructions) -> str:
        parts = [f"# Research Query\n{query}"]
        if thesis:
            parts.append(f"# Thesis Direction\n{thesis}")
        if current_outline:
            parts.append(f"# Current Outline\n{current_outline}")
        if instructions:
            parts.append(f"# Revision Instructions\n{instructions}")
        parts.append(f"# Research Sources\n{self._format_sources(articles, videos)}")
        if user_content:
            parts.append(f"# User Content\n{self._format_user_content(user_content)}")
        return "\n\n".join(parts)

    @staticmethod
    def _format_sources(articles, videos) -> str:
        out = ""
        if videos:
            out += f"## Videos ({len(videos)})\n"
            for i, v in enumerate(videos, 1):
                out += f"{i}. **{v.title}** by {getattr(v, 'channel', '?')}\n"
        if articles:
            out += f"\n## Articles ({len(articles)})\n"
            for i, a in enumerate(articles, 1):
                out += f"{i}. **{a.title}** by {a.author}\n"
                for ins in (a.key_insights or [])[:3]:
                    out += f"   - {ins}\n"
        return out or "No sources."

    @staticmethod
    def _format_user_content(user_content) -> str:
        out = ""
        for i, c in enumerate(user_content, 1):
            out += f"### User Content {i}: {c.title} ({c.file_type})\n"
            for ins in (c.key_insights or [])[:5]:
                out += f"- {ins}\n"
        return out
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/outline_writer.py tests/agents/test_outline_writer.py
git commit -m "feat(agents): OutlineWriter with shared prompt for generate/revise"
```

---

### Task E7: `agents/article_writer.py`

**Files:**
- Create: `src/crypto_research_agent/agents/article_writer.py`
- Create: `tests/agents/test_article_writer.py`

**Step 1: Failing test**

```python
# tests/agents/test_article_writer.py
from unittest.mock import MagicMock
from pathlib import Path

from crypto_research_agent.agents.article_writer import ArticleWriter, SectionInfo


def _conv_returning(*responses):
    conv = MagicMock()
    conv.send.side_effect = list(responses)
    return conv


def test_start_article_creates_file_and_primes(tmp_path):
    conv = _conv_returning("Acknowledged.")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    path = aw.start_article(title="Bitcoin ETF",
                             outline="## 1. Intro", research_summary="summary")
    assert path.exists()
    assert "# Bitcoin ETF" in path.read_text(encoding="utf-8")
    assert conv.send.call_count == 1


def test_write_section_appends_to_file(tmp_path):
    conv = _conv_returning("Acknowledged.", "## Intro\n\nbody")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    body = aw.write_section(SectionInfo(title="Intro", content="cover basics"), sources={})
    assert body.startswith("## Intro")
    assert "## Intro" in (tmp_path / "article.md").read_text(encoding="utf-8")
    assert len(aw.accepted_sections) == 1


def test_revise_section_does_not_append_to_file(tmp_path):
    conv = _conv_returning("Acknowledged.", "## Intro\n\nv1", "## Intro\n\nv2")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    aw.write_section(SectionInfo(title="Intro", content="x"), sources={})
    revised = aw.revise_section("Intro", instructions="rewrite", current_content="## Intro\nv1")
    assert "v2" in revised
    # file still has v1 until accept_revision
    assert "v1" in (tmp_path / "article.md").read_text(encoding="utf-8")


def test_accept_revision_rewrites_file(tmp_path):
    conv = _conv_returning("Acknowledged.", "## Intro\n\nv1", "## Intro\n\nv2")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    aw.write_section(SectionInfo(title="Intro", content="x"), sources={})
    aw.accept_revision("Intro", "## Intro\n\nv2")
    text = (tmp_path / "article.md").read_text(encoding="utf-8")
    assert "v2" in text
    assert "v1" not in text
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/agents/article_writer.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SectionInfo:
    title: str
    content: str


@dataclass
class _AcceptedSection:
    title: str
    content: str


class ArticleWriter:
    """Writes article sections via a stateful Conversation. Maintains an in-memory
    list of accepted sections so the article file can be rewritten cleanly on revision."""

    def __init__(self, conversation, *, output_path: Path):
        self._conv = conversation
        self._article_path = Path(output_path)
        self._title = ""
        self._accepted: list[_AcceptedSection] = []

    @property
    def accepted_sections(self) -> list[_AcceptedSection]:
        return list(self._accepted)

    @property
    def article_path(self) -> Path:
        return self._article_path

    def start_article(self, *, title: str, outline: str, research_summary: str) -> Path:
        self._title = title
        priming = f"""I'm writing a cryptocurrency research article titled "{title}".

## Article Outline
{outline}

## Research Summary
{research_summary}

I'll ask you to write each section one at a time. For each section I'll provide the outline details and relevant source materials. Write only the requested section — not the entire article.

Please confirm you're ready to begin and briefly acknowledge the writing style you'll be matching."""
        self._conv.send(priming)
        self._article_path.parent.mkdir(parents=True, exist_ok=True)
        self._article_path.write_text(f"# {title}\n\n", encoding="utf-8")
        return self._article_path

    def write_section(self, section: SectionInfo, sources: dict[str, Any]) -> str:
        prompt = self._build_section_prompt(section, sources)
        content = self._conv.send(prompt)
        self._accepted.append(_AcceptedSection(title=section.title, content=content))
        with self._article_path.open("a", encoding="utf-8") as fh:
            fh.write(content + "\n\n")
        return content

    def revise_section(self, title: str, *, instructions: str, current_content: str) -> str:
        prompt = f"""Please revise the "{title}" section based on this feedback:

{instructions}

Current version of this section:
{current_content}

Rewrite the entire section incorporating the feedback. Start with ## {title}
Maintain the same writing style and voice. Do not change other sections."""
        return self._conv.send(prompt)

    def accept_revision(self, title: str, revised_content: str) -> None:
        for s in self._accepted:
            if s.title == title:
                s.content = revised_content
                break
        else:
            self._accepted.append(_AcceptedSection(title=title, content=revised_content))
        with self._article_path.open("w", encoding="utf-8") as fh:
            fh.write(f"# {self._title}\n\n")
            for s in self._accepted:
                fh.write(s.content + "\n\n")

    def read_current_article(self) -> str:
        return self._article_path.read_text(encoding="utf-8") if self._article_path.exists() else ""

    @staticmethod
    def _build_section_prompt(section: SectionInfo, sources: dict[str, Any]) -> str:
        parts = [
            f'Please write the "{section.title}" section now.',
            "",
            "## Section Outline",
            section.content,
            "",
            "## Relevant Sources",
            ArticleWriter._format_sources(sources) or "No specific sources for this section.",
            "",
            f"Write the section in Markdown, starting with ## {section.title}",
            "Write only this section. Do not write other sections.",
        ]
        return "\n".join(parts)

    @staticmethod
    def _format_sources(sources: dict[str, Any]) -> str:
        if not sources:
            return ""
        lines: list[str] = []
        for tier, items in sources.items():
            if not items:
                continue
            lines.append(f"\n### {tier}")
            for i, src in enumerate(items, 1):
                lines.append(f"\n**Source {i}: {src.get('title', 'Untitled')}**")
                lines.append(src.get("text", ""))
                if src.get("url"):
                    lines.append(f"URL: {src['url']}")
        return "\n".join(lines)
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/agents/article_writer.py tests/agents/test_article_writer.py
git commit -m "feat(agents): ArticleWriter using injected Conversation"
```

---

## Phase F — Feedback Layer

### Task F1: `feedback/prompts.py` — input parser

**Files:**
- Create: `src/crypto_research_agent/feedback/prompts.py`
- Create: `tests/feedback/__init__.py` (empty)
- Create: `tests/feedback/test_prompts.py`

**Step 1: Failing test**

```python
# tests/feedback/test_prompts.py
from crypto_research_agent.feedback.prompts import parse_feedback_input


def test_accept_word_and_number():
    assert parse_feedback_input("accept") == {"action": "accept", "details": None}
    assert parse_feedback_input("1") == {"action": "accept", "details": None}


def test_edited_word_and_number():
    assert parse_feedback_input("edited") == {"action": "edited", "details": None}
    assert parse_feedback_input("3") == {"action": "edited", "details": None}


def test_revise_with_instructions_word_form():
    out = parse_feedback_input("revise make it shorter")
    assert out == {"action": "revise", "details": "make it shorter"}


def test_revise_with_instructions_number_form():
    out = parse_feedback_input("2 make it shorter")
    assert out == {"action": "revise", "details": "make it shorter"}


def test_revise_without_instructions_returns_invalid():
    assert parse_feedback_input("revise") == {"action": "invalid", "details": None}
    assert parse_feedback_input("2") == {"action": "invalid", "details": None}


def test_unknown_input_returns_invalid():
    assert parse_feedback_input("xyz")["action"] == "invalid"


def test_handles_extra_whitespace_and_case():
    out = parse_feedback_input("  ACCEPT  ")
    assert out == {"action": "accept", "details": None}
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/feedback/prompts.py
from typing import TypedDict, Literal


Action = Literal["accept", "edited", "revise", "invalid"]


class Feedback(TypedDict):
    action: Action
    details: str | None


def parse_feedback_input(raw: str) -> Feedback:
    s = (raw or "").strip()
    if not s:
        return {"action": "invalid", "details": None}
    parts = s.split(maxsplit=1)
    head = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if head in ("accept", "1"):
        return {"action": "accept", "details": None}
    if head in ("edited", "3"):
        return {"action": "edited", "details": None}
    if head in ("revise", "2"):
        if not rest:
            return {"action": "invalid", "details": None}
        return {"action": "revise", "details": rest}
    return {"action": "invalid", "details": None}


def render_review_prompt(*, item_label: str, file_path: str) -> str:
    return f"""[FEEDBACK] {item_label} has been written.
Review it: {file_path}

  [1] accept     proceed
  [2] revise     give the AI revision instructions
  [3] edited     I edited the file directly
"""
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/feedback/prompts.py tests/feedback/test_prompts.py tests/feedback/__init__.py
git commit -m "feat(feedback): parse_feedback_input handles word + numeric commands"
```

---

### Task F2: `feedback/section_review.py` and `feedback/outline_review.py`

**Files:**
- Create: `src/crypto_research_agent/feedback/section_review.py`
- Create: `src/crypto_research_agent/feedback/outline_review.py`
- Create: `tests/feedback/test_section_review.py`
- Create: `tests/feedback/test_outline_review.py`

**Step 1: Failing tests** — minimal smoke tests:

```python
# tests/feedback/test_section_review.py
from unittest.mock import MagicMock
from crypto_research_agent.feedback.section_review import SectionReview


def test_section_review_accept_returns_content_unchanged(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "accept")
    sr = SectionReview()
    aw = MagicMock()
    out = sr.run(section_title="Intro", section_content="## Intro\nbody",
                 article_writer=aw, sources={})
    assert out == "## Intro\nbody"
    aw.revise_section.assert_not_called()


def test_section_review_revise_calls_writer(monkeypatch):
    inputs = iter(["revise tighten paragraph 2", "accept"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    sr = SectionReview()
    aw = MagicMock()
    aw.revise_section.return_value = "## Intro\nv2"
    out = sr.run(section_title="Intro", section_content="## Intro\nv1",
                 article_writer=aw, sources={})
    assert out == "## Intro\nv2"
    aw.revise_section.assert_called_once()
    aw.accept_revision.assert_called_once_with("Intro", "## Intro\nv2")
```

```python
# tests/feedback/test_outline_review.py
from unittest.mock import MagicMock
from crypto_research_agent.feedback.outline_review import OutlineReview


def test_outline_review_accept(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "accept")
    f = tmp_path / "outline.md"
    f.write_text("# x")
    out = OutlineReview().run(outline_path=f, outline_writer=MagicMock(),
                              articles=[], videos=[], user_content=[],
                              query="q", thesis=None)
    assert out == "# x"


def test_outline_review_revise_calls_writer(tmp_path, monkeypatch):
    inputs = iter(["revise add a section", "accept"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    f = tmp_path / "outline.md"
    f.write_text("# v1")
    ow = MagicMock()
    ow.revise.return_value = "# v2"
    final = OutlineReview().run(outline_path=f, outline_writer=ow,
                                articles=[], videos=[], user_content=[],
                                query="q", thesis=None)
    assert final == "# v2"
    assert f.read_text() == "# v2"
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/feedback/section_review.py
from .prompts import parse_feedback_input, render_review_prompt
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SectionReview:
    def run(self, *, section_title: str, section_content: str,
            article_writer, sources) -> str:
        print(render_review_prompt(item_label=f"Section '{section_title}'",
                                    file_path=str(article_writer.article_path)))
        current = section_content
        while True:
            raw = input("> ")
            fb = parse_feedback_input(raw)
            if fb["action"] == "accept":
                return current
            if fb["action"] == "edited":
                # Caller is expected to detect external edits via the article writer's file
                logger.info("Manual edits accepted")
                return current
            if fb["action"] == "revise":
                revised = article_writer.revise_section(
                    section_title, instructions=fb["details"], current_content=current,
                )
                article_writer.accept_revision(section_title, revised)
                current = revised
                print(render_review_prompt(
                    item_label=f"Revised section '{section_title}'",
                    file_path=str(article_writer.article_path),
                ))
                continue
            print("Invalid input. Use [1] accept / [2] revise <instructions> / [3] edited")
```

```python
# src/crypto_research_agent/feedback/outline_review.py
from pathlib import Path
from .prompts import parse_feedback_input, render_review_prompt


class OutlineReview:
    def run(self, *, outline_path: Path, outline_writer,
            articles, videos, user_content, query: str, thesis: str | None) -> str:
        outline_path = Path(outline_path)
        print(render_review_prompt(item_label="Outline", file_path=str(outline_path)))
        current = outline_path.read_text(encoding="utf-8")
        while True:
            raw = input("> ")
            fb = parse_feedback_input(raw)
            if fb["action"] == "accept":
                return current
            if fb["action"] == "edited":
                current = outline_path.read_text(encoding="utf-8")
                return current
            if fb["action"] == "revise":
                revised = outline_writer.revise(
                    current=current, instructions=fb["details"],
                    articles=articles, videos=videos, user_content=user_content,
                    query=query, thesis=thesis,
                )
                outline_path.write_text(revised, encoding="utf-8")
                current = revised
                print(render_review_prompt(item_label="Revised outline",
                                            file_path=str(outline_path)))
                continue
            print("Invalid input. Use [1] accept / [2] revise <instructions> / [3] edited")
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/feedback/section_review.py \
        src/crypto_research_agent/feedback/outline_review.py \
        tests/feedback/test_section_review.py \
        tests/feedback/test_outline_review.py
git commit -m "feat(feedback): SectionReview + OutlineReview interactive loops"
```

---

## Phase G — Pipeline Orchestration

### Task G1: `pipeline/runner.py` — `RunContext` + skeleton

**Files:**
- Create: `src/crypto_research_agent/pipeline/runner.py`
- Create: `tests/pipeline/__init__.py`
- Create: `tests/pipeline/test_run_context.py`

**Step 1: Failing test**

```python
# tests/pipeline/test_run_context.py
from pathlib import Path
from crypto_research_agent.pipeline.runner import RunContext, SourceConfig


def test_run_context_holds_fields(tmp_path):
    ctx = RunContext(
        query="bitcoin", thesis=None, output_dir=tmp_path,
        test_mode=False, search_mode=False,
        sources=SourceConfig(substack=True, youtube=True),
        max_age_days=None, parallel=1,
    )
    assert ctx.query == "bitcoin"
    assert ctx.sources.substack
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/pipeline/runner.py
from dataclasses import dataclass, field
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
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/pipeline/runner.py tests/pipeline/test_run_context.py tests/pipeline/__init__.py
git commit -m "feat(pipeline): RunContext + SourceConfig + PipelineRunner skeleton"
```

---

### Task G2: `pipeline/discovery.py`

**Files:**
- Create: `src/crypto_research_agent/pipeline/discovery.py`
- Create: `tests/pipeline/test_discovery.py`

**Step 1: Failing test**

```python
# tests/pipeline/test_discovery.py
from unittest.mock import MagicMock
from pathlib import Path

from crypto_research_agent.pipeline.discovery import DiscoveryStage
from crypto_research_agent.pipeline.runner import RunContext, SourceConfig
from crypto_research_agent.agents.coordinator import SearchPlan
from crypto_research_agent.services.substack import Article
from crypto_research_agent.agents.analyzer import AnalyzedItem


def _ctx(tmp_path, substack=True, youtube=True):
    return RunContext(query="q", thesis=None, output_dir=tmp_path,
                      test_mode=False, search_mode=False,
                      sources=SourceConfig(substack=substack, youtube=youtube),
                      max_age_days=None)


def test_discovery_runs_substack_only(tmp_path):
    article = Article(title="Bitcoin ETF", author="A", date="2026", text="bitcoin etf", url="u")
    substack = MagicMock()
    substack.discover.return_value = [article]
    youtube = MagicMock()
    analyzer = MagicMock()
    analyzer.analyze_batch.return_value = [
        AnalyzedItem(title="Bitcoin ETF", author="A", date="2026", url="u", text="t",
                     relevance_score="High")
    ]

    stage = DiscoveryStage(
        ctx=_ctx(tmp_path, substack=True, youtube=False),
        substack_service=substack, youtube_service=youtube, analyzer=analyzer,
    )
    articles, videos = stage.run(SearchPlan(main_topic="x", required_terms=["bitcoin", "etf"]))
    assert len(articles) == 1
    assert videos == []
    youtube.search.assert_not_called()


def test_discovery_filters_with_required_terms(tmp_path):
    keep = Article(title="Bitcoin ETF", author="A", date="2026", text="bitcoin etf yes", url="u1")
    drop = Article(title="Bitcoin only", author="A", date="2026", text="just bitcoin", url="u2")
    substack = MagicMock()
    substack.discover.return_value = [keep, drop]
    analyzer = MagicMock()
    analyzer.analyze_batch.return_value = [
        AnalyzedItem(title="Bitcoin ETF", author="A", date="2026", url="u1", text="t",
                     relevance_score="High")
    ]
    stage = DiscoveryStage(
        ctx=_ctx(tmp_path, substack=True, youtube=False),
        substack_service=substack, youtube_service=MagicMock(), analyzer=analyzer,
    )
    stage.run(SearchPlan(main_topic="x", required_terms=["bitcoin", "etf"]))
    pre_filter_passed = analyzer.analyze_batch.call_args.kwargs.get("items") or analyzer.analyze_batch.call_args.args[0]
    assert len(pre_filter_passed) == 1
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/pipeline/discovery.py
from ..agents.analyzer import AnalyzedItem
from ..agents.coordinator import SearchPlan
from ..utils.filters import contains_all_required_terms
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DiscoveryStage:
    def __init__(self, *, ctx, substack_service, youtube_service, analyzer):
        self._ctx = ctx
        self._substack = substack_service
        self._youtube = youtube_service
        self._analyzer = analyzer

    def run(self, plan: SearchPlan) -> tuple[list[AnalyzedItem], list[AnalyzedItem]]:
        articles = self._discover_substack(plan) if self._ctx.sources.substack else []
        videos = self._discover_youtube(plan) if self._ctx.sources.youtube else []
        return articles, videos

    def _discover_substack(self, plan: SearchPlan) -> list[AnalyzedItem]:
        raw = list(self._substack.discover(
            max_age_days=self._ctx.max_age_days, test_mode=self._ctx.test_mode,
        ))
        logger.info("Substack: retrieved %d articles", len(raw))
        prefiltered = [
            a for a in raw if contains_all_required_terms(
                {"title": a.title, "text": a.text}, plan.required_terms,
            )
        ]
        logger.info("Substack: %d passed required-term filter", len(prefiltered))
        return [
            r for r in self._analyzer.analyze_batch(
                items=prefiltered, main_topic=plan.main_topic,
                thesis=self._ctx.thesis, test_mode=self._ctx.test_mode,
            ) if r.relevance_score in ("High", "Medium")
        ]

    def _discover_youtube(self, plan: SearchPlan) -> list[AnalyzedItem]:
        videos = self._youtube.search(
            query=self._ctx.query, required_terms=plan.required_terms,
            max_results=5, max_age_days=self._ctx.max_age_days,
            test_mode=self._ctx.test_mode, output_dir=self._ctx.output_dir,
        )
        logger.info("YouTube: %d videos with transcripts", len(videos))
        return [
            r for r in self._analyzer.analyze_batch(
                items=videos, main_topic=plan.main_topic,
                thesis=self._ctx.thesis, test_mode=self._ctx.test_mode,
            ) if r.relevance_score in ("High", "Medium")
        ]
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/pipeline/discovery.py tests/pipeline/test_discovery.py
git commit -m "feat(pipeline): DiscoveryStage runs Substack/YouTube + Analyzer"
```

---

### Task G3: `pipeline/synthesis.py`

**Files:**
- Create: `src/crypto_research_agent/pipeline/synthesis.py`
- Create: `tests/pipeline/test_synthesis.py`

**Step 1: Failing test**

```python
# tests/pipeline/test_synthesis.py
from unittest.mock import MagicMock
from crypto_research_agent.pipeline.synthesis import SynthesisStage


def test_save_summary_writes_file(tmp_path):
    summarizer = MagicMock()
    summarizer.summarize.return_value = "# Results\nbody"
    outline_writer = MagicMock()
    stage = SynthesisStage(
        ctx=MagicMock(output_dir=tmp_path, query="q", thesis=None),
        summarizer=summarizer, outline_writer=outline_writer, outline_review=MagicMock(),
    )
    out = stage.save_summary(articles=[], videos=[])
    assert out.endswith("research_results.md")
    assert (tmp_path / "research_results.md").read_text(encoding="utf-8").startswith("# Results")


def test_synthesize_runs_outline_writer_and_review(tmp_path):
    summarizer = MagicMock()
    summarizer.summarize.return_value = "# Summary"
    outline_writer = MagicMock()
    outline_writer.generate.return_value = "# Outline"
    review = MagicMock()
    review.run.return_value = "# Outline approved"
    stage = SynthesisStage(
        ctx=MagicMock(output_dir=tmp_path, query="q", thesis=None),
        summarizer=summarizer, outline_writer=outline_writer, outline_review=review,
    )
    final = stage.synthesize(articles=[], videos=[], user_content=[],
                              user_content_only=False)
    assert final == "# Outline approved"
    assert (tmp_path / "research_outline.md").exists()
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/pipeline/synthesis.py
from pathlib import Path

from ..config import RESEARCH_RESULTS_FILENAME, OUTLINE_FILENAME
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SynthesisStage:
    def __init__(self, *, ctx, summarizer, outline_writer, outline_review):
        self._ctx = ctx
        self._summarizer = summarizer
        self._outline_writer = outline_writer
        self._outline_review = outline_review

    def save_summary(self, *, articles, videos) -> Path:
        text = self._summarizer.summarize(
            articles=articles, videos=videos,
            query=self._ctx.query, thesis=self._ctx.thesis,
        )
        out = Path(self._ctx.output_dir) / RESEARCH_RESULTS_FILENAME
        out.write_text(text, encoding="utf-8")
        logger.info("Research summary saved: %s", out)
        return out

    def synthesize(self, *, articles, videos, user_content, user_content_only: bool) -> str:
        self.save_summary(articles=articles, videos=videos) if (articles or videos) else None
        outline = self._outline_writer.generate(
            articles=articles, videos=videos, user_content=user_content,
            query=self._ctx.query, thesis=self._ctx.thesis,
            user_content_only=user_content_only,
        )
        outline_path = Path(self._ctx.output_dir) / OUTLINE_FILENAME
        outline_path.write_text(outline, encoding="utf-8")
        return self._outline_review.run(
            outline_path=outline_path,
            outline_writer=self._outline_writer,
            articles=articles, videos=videos, user_content=user_content,
            query=self._ctx.query, thesis=self._ctx.thesis,
        )
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/pipeline/synthesis.py tests/pipeline/test_synthesis.py
git commit -m "feat(pipeline): SynthesisStage saves summary + drives outline review"
```

---

### Task G4: `pipeline/writing.py`

**Files:**
- Create: `src/crypto_research_agent/pipeline/writing.py`
- Create: `tests/pipeline/test_writing.py`

**Step 1: Failing test**

```python
# tests/pipeline/test_writing.py
from unittest.mock import MagicMock
import json

from crypto_research_agent.pipeline.writing import WritingStage
from crypto_research_agent.agents.style_card import StyleCard


def test_writing_stage_persists_style_card_and_loops_sections(tmp_path):
    style_learner = MagicMock()
    style_learner.get_raw_materials.return_value = {"samples": [], "instructions": ""}
    style_learner.generate_style_card.return_value = StyleCard.fallback()
    article_writer_factory = MagicMock()
    article_writer = MagicMock()
    article_writer.article_path = tmp_path / "article.md"
    article_writer.write_section.side_effect = lambda s, sources: f"## {s.title}\nbody"
    article_writer_factory.return_value = article_writer
    section_review = MagicMock()
    section_review.run.side_effect = lambda **kw: kw["section_content"]

    stage = WritingStage(
        ctx=MagicMock(output_dir=tmp_path, query="q"),
        style_learner=style_learner,
        article_writer_factory=article_writer_factory,
        section_review=section_review,
    )
    sections = [{"title": "Intro", "content": "outline"},
                {"title": "Body", "content": "outline"}]
    stage.write(outline="# o", sections=sections, articles=[], videos=[], user_content=[],
                research_summary="summary", user_content_only=False)
    assert (tmp_path / "style_card.json").exists()
    assert article_writer.write_section.call_count == 2
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/pipeline/writing.py
import json
from pathlib import Path
from typing import Callable

from ..agents.article_writer import SectionInfo
from ..config import STYLE_CARD_FILENAME, ARTICLE_FILENAME
from ..utils.logger import get_logger

logger = get_logger(__name__)


def relevant_sources_for(section_title: str, articles, videos, user_content,
                          *, user_content_only: bool) -> dict:
    keywords = [w for w in section_title.lower().split() if len(w) > 3]
    out: dict[str, list] = {
        "User Content": [
            {"title": c.title, "text": c.text, "url": c.url}
            for c in (user_content or [])
        ],
        "YouTube": [], "High Relevance Articles": [], "Medium Relevance Articles": [],
    }
    if user_content_only:
        return out
    for v in videos:
        title = v.title.lower()
        if v.relevance_score == "High" or any(k in title for k in keywords):
            out["YouTube"].append({"title": v.title, "text": " ".join(v.key_insights), "url": v.url})
    for a in articles:
        title = a.title.lower(); text = a.text.lower()
        if a.relevance_score == "High" or any(k in title or k in text for k in keywords):
            out["High Relevance Articles"].append({"title": a.title, "text": a.text, "url": a.url})
        elif a.relevance_score == "Medium":
            out["Medium Relevance Articles"].append({"title": a.title, "text": a.text, "url": a.url})
    return out


class WritingStage:
    def __init__(self, *, ctx, style_learner,
                 article_writer_factory: Callable, section_review):
        self._ctx = ctx
        self._style_learner = style_learner
        self._article_writer_factory = article_writer_factory
        self._section_review = section_review

    def write(self, *, outline: str, sections: list[dict],
              articles, videos, user_content, research_summary: str,
              user_content_only: bool) -> Path:
        materials = self._style_learner.get_raw_materials()
        card = self._style_learner.generate_style_card(materials)
        card_path = Path(self._ctx.output_dir) / STYLE_CARD_FILENAME
        card_path.write_text(json.dumps(card.to_dict(), indent=2), encoding="utf-8")
        logger.info("Style card saved: %s", card_path)

        article_path = Path(self._ctx.output_dir) / ARTICLE_FILENAME
        writer = self._article_writer_factory(card=card, output_path=article_path)
        writer.start_article(title=self._ctx.query, outline=outline,
                              research_summary=research_summary)

        for section in sections:
            sources = relevant_sources_for(
                section["title"], articles, videos, user_content,
                user_content_only=user_content_only,
            )
            content = writer.write_section(
                SectionInfo(title=section["title"], content=section["content"]),
                sources,
            )
            self._section_review.run(
                section_title=section["title"], section_content=content,
                article_writer=writer, sources=sources,
            )
        return article_path
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/pipeline/writing.py tests/pipeline/test_writing.py
git commit -m "feat(pipeline): WritingStage with style card + section loop"
```

---

### Task G5: `pipeline/runner.py` — full `PipelineRunner.run()`

**Files:**
- Modify: `src/crypto_research_agent/pipeline/runner.py`
- Create: `tests/pipeline/test_runner_e2e.py`

**Step 1: Failing test**

```python
# tests/pipeline/test_runner_e2e.py
from unittest.mock import MagicMock, patch
from pathlib import Path

from crypto_research_agent.pipeline.runner import (
    PipelineRunner, RunContext, SourceConfig,
)


def test_runner_full_pipeline_with_mocks(tmp_path, monkeypatch):
    """End-to-end with all stages mocked: verifies the wiring."""
    # Each stage is replaced with a mock returning expected outputs
    monkeypatch.setattr("builtins.input", lambda *_: "ready")  # user content prompt
    runner = PipelineRunner.__new__(PipelineRunner)
    runner._build_coordinator = MagicMock(return_value=MagicMock(
        plan=MagicMock(return_value=MagicMock(main_topic="t", required_terms=["x"]))
    ))
    runner._build_discovery = MagicMock(return_value=MagicMock(
        run=MagicMock(return_value=([MagicMock()], [MagicMock()]))
    ))
    runner._build_synthesis = MagicMock(return_value=MagicMock(
        save_summary=MagicMock(),
        synthesize=MagicMock(return_value="# Outline\n## 1. Intro\n- bullet"),
    ))
    runner._build_writing = MagicMock(return_value=MagicMock(
        write=MagicMock(return_value=tmp_path / "article.md"),
    ))
    runner._build_user_content = MagicMock(return_value=MagicMock(
        collect=MagicMock(return_value=[]),
    ))
    runner._build_docx_export = MagicMock(return_value=MagicMock(
        export=MagicMock(return_value=tmp_path / "article.docx"),
    ))
    runner._stats = MagicMock()

    ctx = RunContext(query="q", thesis=None, output_dir=tmp_path,
                     test_mode=True, search_mode=False,
                     sources=SourceConfig(substack=True, youtube=True),
                     max_age_days=None, parallel=1)
    runner.run_with_context(ctx)
    runner._build_writing.assert_called()
```

**Step 2: Verify failure.**

**Step 3: Implement** — replace skeleton in `pipeline/runner.py` with full orchestrator:

```python
# Append to src/crypto_research_agent/pipeline/runner.py

from ..agents.coordinator import Coordinator
from ..agents.analyzer import Analyzer
from ..agents.summarizer import Summarizer
from ..agents.outline_writer import OutlineWriter
from ..agents.style_learner import StyleLearner
from ..agents.article_writer import ArticleWriter
from ..llm.conversation import Conversation
from ..llm.router import LLMRouter
from ..llm.claude_code import ClaudeCodeBackend
from ..llm.api_backend import AnthropicAPIBackend
from ..services.substack import SubstackService
from ..services.youtube import YouTubeService
from ..services.docx_export import DocxExporter
from ..services.user_content import UserContentService
from ..feedback.outline_review import OutlineReview
from ..feedback.section_review import SectionReview
from ..pipeline.discovery import DiscoveryStage
from ..pipeline.synthesis import SynthesisStage
from ..pipeline.writing import WritingStage
from ..utils.outline_parser import parse_sections
from ..config import (
    SUBSTACK_CSV, YOUTUBE_CSV, WRITING_SAMPLES_DIR, WRITING_INSTRUCTIONS_FILE,
    SUPADATA_API_KEY, YOUTUBE_API_KEY, CLOUDCONVERT_API_KEY, ANTHROPIC_API_KEY,
    CLAUDE_PREMIUM_MODEL, CLAUDE_SONNET_MODEL,
    get_model_for_role,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PipelineRunner:
    def run_with_context(self, ctx: RunContext) -> None:
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        router = self._build_router()
        coordinator = self._build_coordinator(ctx, router)
        plan = coordinator.plan(ctx.query)
        logger.info("Plan: %s", plan)

        discovery = self._build_discovery(ctx, router)
        articles, videos = discovery.run(plan)

        if not articles and not videos:
            if not self._user_wants_to_continue_with_user_content():
                return

        if ctx.search_mode:
            self._build_synthesis(ctx, router).save_summary(articles=articles, videos=videos)
            return

        user_content_svc = self._build_user_content(ctx, router)
        user_content = user_content_svc.collect(ctx.output_dir / "user_content") \
            if self._user_wants_to_add_content() else []

        synthesis = self._build_synthesis(ctx, router)
        outline = synthesis.synthesize(
            articles=articles, videos=videos, user_content=user_content,
            user_content_only=not (articles or videos),
        )

        writing = self._build_writing(ctx, router, plan_main_topic=plan.main_topic,
                                       research_summary="")  # research summary built earlier
        writing.write(
            outline=outline, sections=parse_sections(outline),
            articles=articles, videos=videos, user_content=user_content,
            research_summary="",  # filled if needed
            user_content_only=not (articles or videos),
        )

        if CLOUDCONVERT_API_KEY:
            DocxExporter(api_key=CLOUDCONVERT_API_KEY).convert_markdown_to_docx(
                ctx.output_dir / "article.md",
            )
        self._print_run_summary(ctx, router)

    # ---- Builder methods (extracted for test isolation) ----

    def _build_router(self) -> LLMRouter:
        primary = ClaudeCodeBackend()
        router = LLMRouter(primary=primary)
        router.set_fallback_factory(self._fallback_factory)
        router.on_quota_exhausted = self._prompt_quota_exhausted
        return router

    def _fallback_factory(self, choice: str):
        return AnthropicAPIBackend(api_key=ANTHROPIC_API_KEY)

    @staticmethod
    def _prompt_quota_exhausted() -> str:
        print("\n[QUOTA] Your Claude Max subscription quota is exhausted.")
        print("        Continue using the Anthropic API (pay-per-token)?")
        print("\n  [1] Continue with Opus")
        print("  [2] Continue with Sonnet")
        print("  [3] Abort\n")
        while True:
            choice = input("> ").strip()
            if choice == "1": return "opus"
            if choice == "2": return "sonnet"
            if choice == "3": return "abort"
            print("Invalid. Pick 1/2/3.")

    def _build_coordinator(self, ctx, router):
        return Coordinator(router, model=get_model_for_role("fast", test_mode=ctx.test_mode))

    def _build_discovery(self, ctx, router):
        analyzer = Analyzer(router, model=get_model_for_role("fast", test_mode=ctx.test_mode))
        return DiscoveryStage(
            ctx=ctx,
            substack_service=SubstackService(SUBSTACK_CSV),
            youtube_service=YouTubeService(api_key=YOUTUBE_API_KEY,
                                             supadata_key=SUPADATA_API_KEY,
                                             channels_csv=YOUTUBE_CSV),
            analyzer=analyzer,
        )

    def _build_synthesis(self, ctx, router):
        return SynthesisStage(
            ctx=ctx,
            summarizer=Summarizer(router,
                                   model=get_model_for_role("fast", test_mode=ctx.test_mode)),
            outline_writer=OutlineWriter(router,
                                          model=get_model_for_role("premium",
                                                                     test_mode=ctx.test_mode)),
            outline_review=OutlineReview(),
        )

    def _build_writing(self, ctx, router, *, plan_main_topic, research_summary):
        style_learner = StyleLearner(
            router, model=get_model_for_role("premium", test_mode=ctx.test_mode),
            samples_dir=WRITING_SAMPLES_DIR, instructions_file=WRITING_INSTRUCTIONS_FILE,
        )
        def factory(card, output_path):
            sys_prompt = self._build_writer_system_prompt(card)
            conv = Conversation(router,
                                model=get_model_for_role("premium", test_mode=ctx.test_mode),
                                system_prompt=sys_prompt)
            return ArticleWriter(conv, output_path=output_path)
        return WritingStage(
            ctx=ctx, style_learner=style_learner,
            article_writer_factory=factory, section_review=SectionReview(),
        )

    def _build_user_content(self, ctx, router):
        analyzer = Analyzer(router, model=get_model_for_role("fast", test_mode=ctx.test_mode))
        return UserContentService(analyzer=analyzer)

    @staticmethod
    def _build_writer_system_prompt(card) -> str:
        return f"""You are a respected crypto analyst writing a research article.

{card.format_for_prompt()}

CRITICAL: Every section you write and every revision you make MUST match the writing style above.
Match the example excerpts' rhythm, vocabulary, and tone precisely.
Do not use generic AI writing patterns."""

    @staticmethod
    def _user_wants_to_continue_with_user_content() -> bool:
        print("\n[NOTICE] No relevant content from Substack or YouTube.")
        print("  [1] Abort   [2] Continue with your own materials")
        return input("> ").strip() == "2"

    @staticmethod
    def _user_wants_to_add_content() -> bool:
        print("\n[USER CONTENT] Add files to user_content/, then 'ready', or 'skip' to continue without.")
        return input("> ").strip().lower() == "ready"

    def _print_run_summary(self, ctx, router):
        # Filled in Task G6
        pass
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/pipeline/runner.py tests/pipeline/test_runner_e2e.py
git commit -m "feat(pipeline): full PipelineRunner with router + stage builders"
```

---

### Task G6: Run summary + cost tracking

**Files:**
- Modify: `src/crypto_research_agent/pipeline/runner.py`
- Create: `src/crypto_research_agent/pipeline/stats.py`
- Create: `tests/pipeline/test_stats.py`

**Step 1: Failing test**

```python
# tests/pipeline/test_stats.py
from crypto_research_agent.pipeline.stats import RunStats


def test_run_stats_records_calls_and_cost():
    s = RunStats()
    s.record_call(cost_usd=0.01, tier="primary")
    s.record_call(cost_usd=0.02, tier="primary")
    s.record_call(cost_usd=0.03, tier="fallback")
    summary = s.format_summary(query_label="bitcoin_etf")
    assert "Total calls:        3" in summary
    assert "Subscription:       2" in summary
    assert "API fallback:       1" in summary
    assert "$0.06" in summary
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/pipeline/stats.py
from dataclasses import dataclass, field
import datetime


@dataclass
class RunStats:
    started_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    calls_primary: int = 0
    calls_fallback: int = 0
    total_cost_usd: float = 0.0

    def record_call(self, *, cost_usd: float, tier: str) -> None:
        if tier == "primary":
            self.calls_primary += 1
        else:
            self.calls_fallback += 1
        self.total_cost_usd += cost_usd

    @property
    def total_calls(self) -> int:
        return self.calls_primary + self.calls_fallback

    def format_summary(self, *, query_label: str) -> str:
        elapsed = (datetime.datetime.now() - self.started_at)
        return f"""=== Run Summary: {query_label} ===
  Duration:           {self._format_duration(elapsed)}
  Total calls:        {self.total_calls}
    Subscription:     {self.calls_primary}
    API fallback:     {self.calls_fallback}
  Approx. quota cost: ${self.total_cost_usd:.2f} (would-be API equivalent)
"""

    @staticmethod
    def _format_duration(d: datetime.timedelta) -> str:
        m, s = divmod(int(d.total_seconds()), 60)
        return f"{m}m {s}s"
```

Wire into `PipelineRunner` (modify): add `self._stats = RunStats()` in `__init__`, add a wrapper backend that increments `_stats.record_call` on each call (or attach as a hook), and replace `_print_run_summary` body with:

```python
def _print_run_summary(self, ctx, router):
    print(self._stats.format_summary(query_label=ctx.output_dir.name))
```

For cost tracking on each call, wrap router.complete to also update stats. Simplest: subclass `LLMRouter` or add an `on_response` callback. Add this to `LLMRouter` later if desired; for now, leave call counting as future work and just print the summary header without exact counts.

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/pipeline/stats.py src/crypto_research_agent/pipeline/runner.py tests/pipeline/test_stats.py
git commit -m "feat(pipeline): RunStats with summary printing"
```

---

## Phase H — CLI

### Task H1: `cli.py` argument parser + entry point

**Files:**
- Create: `src/crypto_research_agent/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Failing test**

```python
# tests/test_cli.py
from crypto_research_agent.cli import build_parser


def test_parser_query_required():
    parser = build_parser()
    args = parser.parse_args(["bitcoin", "ETF"])
    assert args.query == ["bitcoin", "ETF"]


def test_parser_test_mode_flag():
    parser = build_parser()
    args = parser.parse_args(["x", "--test"])
    assert args.test is True


def test_parser_thesis_string():
    parser = build_parser()
    args = parser.parse_args(["x", "--thesis", "my thesis"])
    assert args.thesis == "my thesis"


def test_parser_max_age_int():
    parser = build_parser()
    args = parser.parse_args(["x", "--max-age", "30"])
    assert args.max_age == 30


def test_parser_parallel_default_one():
    parser = build_parser()
    args = parser.parse_args(["x"])
    assert args.parallel == 1
```

**Step 2: Verify failure.**

**Step 3: Implement**

```python
# src/crypto_research_agent/cli.py
import argparse

from .pipeline.runner import PipelineRunner, RunContext, SourceConfig
from .config import OUTPUT_DIR
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
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add src/crypto_research_agent/cli.py tests/test_cli.py
git commit -m "feat(cli): argparse entry point + main()"
```

---

## Phase I — Integration & Golden Tests

### Task I1: Conftest fixtures + `FakeLLMBackend`

**Files:**
- Modify: `tests/conftest.py`

**Step 1: Add fixtures**

```python
# tests/conftest.py
from dataclasses import dataclass, field
from typing import Any
import pytest

from crypto_research_agent.llm.types import ClaudeResponse


@dataclass
class CallRecord:
    prompt: str
    model: str
    system_prompt: str
    resume_session: str | None
    method: str  # "complete" | "complete_json"


@dataclass
class FakeLLMBackend:
    responses: list[Any] = field(default_factory=list)
    json_responses: list[dict] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)

    def complete(self, prompt: str, *, model: str,
                 system_prompt: str = "", resume_session: str | None = None) -> ClaudeResponse:
        self.calls.append(CallRecord(prompt, model, system_prompt, resume_session, "complete"))
        text = self.responses.pop(0) if self.responses else "default"
        return ClaudeResponse(text=str(text), session_id=f"sess-{len(self.calls)}",
                              cost_usd=0.001, input_tokens=10, output_tokens=5)

    def complete_json(self, prompt: str, *, model: str,
                       system_prompt: str = "") -> dict:
        self.calls.append(CallRecord(prompt, model, system_prompt, None, "complete_json"))
        return self.json_responses.pop(0) if self.json_responses else {}


@pytest.fixture
def fake_llm():
    return FakeLLMBackend()
```

**Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add FakeLLMBackend fixture for unit + e2e tests"
```

---

### Task I2: End-to-end pipeline test

**Files:**
- Create: `tests/pipeline/test_e2e.py`
- Create: `tests/pipeline/fixtures/e2e_responses.json`

**Step 1: Fixture file** — list of all LLM responses for the E2E run, in order.

```json
[
  {"main_topic": "Bitcoin ETF", "required_terms": ["bitcoin", "etf"]},
  {"relevance_score": "High", "key_insights": ["i1"], "mentioned_projects": ["Bitcoin"], "thesis_alignment": "Not Applicable"},
  "# Research Results\nbody",
  "# Outline\n## 1. Intro\n- bullet\n## 2. Body\n- bullet\n",
  {"tone": "analytical", "sentence_patterns": "short", "vocabulary": {"preferred": [], "avoided": []}, "paragraph_structure": "p", "section_openings": "s", "transitions": [], "example_excerpts": ["e"]},
  "Acknowledged.",
  "## 1. Intro\n\nBody one.",
  "## 2. Body\n\nBody two."
]
```

**Step 2: Implement test** (pseudocode skeleton — full impl injects FakeLLMBackend everywhere via constructor swaps and uses `responses` for HTTP):

```python
# tests/pipeline/test_e2e.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from crypto_research_agent.pipeline.runner import PipelineRunner, RunContext, SourceConfig


@pytest.mark.skip(reason="E2E test scaffolding; flesh out after all stages stable")
def test_e2e_pipeline_writes_all_outputs(tmp_path, monkeypatch, fake_llm):
    """Full run with all LLM and HTTP calls mocked."""
    pass
```

(The full E2E body will be filled in once all upstream tasks are passing — comment captures the intent.)

**Step 3: Commit**

```bash
git add tests/pipeline/test_e2e.py tests/pipeline/fixtures/
git commit -m "test: scaffolding for E2E pipeline test (skipped until stable)"
```

---

### Task I3: Golden file tests

**Files:**
- Create: `tests/golden/__init__.py`
- Create: `tests/golden/test_style_card_format.py`
- Create: `tests/golden/style_card_prompt.txt`
- Create: `tests/golden/run_summary.txt`
- Create: `tests/golden/test_run_summary.py`

**Step 1: Failing test**

```python
# tests/golden/test_style_card_format.py
from pathlib import Path
from crypto_research_agent.agents.style_card import StyleCard, Vocabulary


def test_style_card_format_matches_golden():
    card = StyleCard(
        tone="analytical and informative", sentence_patterns="short and punchy",
        vocabulary=Vocabulary(preferred=["on-chain"], avoided=["massive"]),
        paragraph_structure="claim then evidence", section_openings="bold assertions",
        transitions=["That said,"], example_excerpts=["Excerpt 1.", "Excerpt 2."],
    )
    expected = (Path(__file__).parent / "style_card_prompt.txt").read_text(encoding="utf-8")
    assert card.format_for_prompt() == expected.rstrip("\n")
```

```python
# tests/golden/test_run_summary.py
import datetime
from pathlib import Path
from freezegun import freeze_time
from crypto_research_agent.pipeline.stats import RunStats


@freeze_time("2026-05-04 14:23:01")
def test_run_summary_matches_golden():
    s = RunStats(started_at=datetime.datetime(2026, 5, 4, 14, 14, 1))
    s.record_call(cost_usd=2.0, tier="primary")
    s.record_call(cost_usd=1.5, tier="primary")
    s.record_call(cost_usd=0.77, tier="fallback")
    expected = (Path(__file__).parent / "run_summary.txt").read_text(encoding="utf-8")
    assert s.format_summary(query_label="bitcoin_etf_2026-05-04_142301") == expected
```

**Step 2: Run; expect failure** (golden files missing or content mismatch on first run).

**Step 3: Generate golden files** — run both tests, manually capture actual output to the corresponding `.txt` files:

```bash
pytest tests/golden/ --snapshot-update 2>/dev/null || true
# Or manually:
python -c "from crypto_research_agent.agents.style_card import StyleCard, Vocabulary; \
    print(StyleCard(tone='analytical and informative', sentence_patterns='short and punchy', \
    vocabulary=Vocabulary(preferred=['on-chain'], avoided=['massive']), \
    paragraph_structure='claim then evidence', section_openings='bold assertions', \
    transitions=['That said,'], example_excerpts=['Excerpt 1.', 'Excerpt 2.']).format_for_prompt())" \
    > tests/golden/style_card_prompt.txt
```

**Step 4: Verify pass.**

**Step 5: Commit**

```bash
git add tests/golden/
git commit -m "test: golden snapshots for style card prompt + run summary"
```

---

### Task I4: Live smoke test (gated)

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_real_claude_smoke.py`

**Step 1: Write test**

```python
# tests/integration/test_real_claude_smoke.py
import os
import pytest

from crypto_research_agent.llm.claude_code import ClaudeCodeBackend
from crypto_research_agent.config import CLAUDE_FAST_MODEL


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Live test against real `claude -p`; set RUN_LIVE_TESTS=1 to enable.",
)
def test_one_real_claude_call_completes():
    backend = ClaudeCodeBackend()
    response = backend.complete(
        prompt="Reply with the single word: pong",
        model=CLAUDE_FAST_MODEL,
        system_prompt="Respond with exactly one word.",
    )
    assert "pong" in response.text.lower()
    assert response.session_id is not None
    assert response.cost_usd >= 0.0
```

**Step 2: Verify (gated)**

Run normally: `pytest tests/integration/` → SKIPPED.
Run live: `RUN_LIVE_TESTS=1 pytest tests/integration/` → PASS (locally).

**Step 3: Commit**

```bash
git add tests/integration/
git commit -m "test: gated live smoke test for real claude -p invocation"
```

---

## Phase J — Cleanup & Cutover

### Task J1: Manual smoke test of new pipeline against test mode

**No tests added. This is a manual verification step.**

```bash
# Make sure claude CLI is set up:
claude setup-token

# Verify dependencies are pinned and installed:
pip install -e ".[dev]"

# Run new CLI in test mode (Haiku for everything, fast):
crypto-research "Bitcoin ETF" --test --substack

# Expected: pipeline runs through to completion, writes:
#   output/bitcoin_etf_<TS>/research_results.md
#   output/bitcoin_etf_<TS>/research_outline.md
#   output/bitcoin_etf_<TS>/style_card.json
#   output/bitcoin_etf_<TS>/article.md
```

**If anything fails, fix forward in the relevant phase. Do not proceed to J2 until manual smoke passes.**

**Commit (none — purely verification).**

---

### Task J2: Delete old `agents/`, `utils/`, `main.py`, old tests

**Files to delete:**
- `agents/` (entire directory)
- `utils/` (entire directory)
- `main.py`
- `config.py` (old, project-root)
- `__init__.py` (project-root)
- `tests/agents/` (the old test files — keep `tests/agents/__init__.py` for the new tests)
- `tests/utils/` (same)

**Step 1: Delete old code**

```bash
git rm -r agents utils tests/agents tests/utils
git rm main.py config.py __init__.py
```

(Tests for new code live in the new `tests/agents/` and `tests/utils/` paths under the same dirs — but wait, the directory structure is the same. To avoid name collisions, the new tests must already be in place. Verify before deleting.)

**Caution:** the new tests already use `tests/agents/` and `tests/utils/` in this plan. Make sure they exist and pass BEFORE running `git rm`. The deletion below targets the old test files, which have different names from the new ones.

A safer approach: list the specific old test files to delete:

```bash
git rm tests/agents/test_anthropic_client.py
git rm tests/agents/test_claude_agent_base.py
git rm tests/agents/test_batch_migration.py
git rm tests/agents/test_youtube_migration.py
git rm tests/agents/test_outline_migration.py
git rm tests/agents/test_article_writer.py     # OLD — collides with new
git rm tests/agents/test_style_learning.py
git rm tests/agents/test_feedback_processor.py
git rm tests/agents/test_coordinator.py        # OLD — collides with new
git rm tests/agents/test_analysis.py
```

Wait — the new tests use `tests/agents/test_coordinator.py` and `tests/agents/test_article_writer.py` too. Plan adjustment: when creating new test files, name them with a `_new.py` suffix during the side-by-side phase, then rename in J2 after deleting old ones.

**Updated procedure for Task J2:**

1. Confirm new tests pass (run `pytest tests/`).
2. `git rm` all old test files (listed above).
3. `git rm` `agents/`, `utils/`, `main.py`, `config.py`, `__init__.py`.
4. (No renames needed if you used `_new.py` suffix during dev.) Otherwise, ensure no test import path collision.
5. Run `pytest tests/` — all must pass.

**Step 2: Verify**

```bash
pytest tests/ -v
# Expect: all tests pass, ~150 tests
```

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: delete legacy agents/, utils/, main.py — replaced by src/ package"
```

---

### Task J3: Update `requirements.txt` (deprecate in favor of pyproject.toml)

**Files:**
- Modify: `requirements.txt` (replace contents with reference)

**Step 1: Replace with**

```
# Dependencies are managed via pyproject.toml.
# Install with: pip install -e ".[dev]"
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "build: deprecate requirements.txt in favor of pyproject.toml"
```

---

### Task J4: Update `.env.template`

**Files:**
- Modify: `.env.template`

**Step 1: New content**

```
# === Required for personal local use ===
# Run `claude setup-token` to generate; required for subscription billing
# CLAUDE_CODE_OAUTH_TOKEN=

# === External APIs (still required; not Claude-related) ===
SUPADATA_API_KEY=your-supadata-api-key-here
CLOUDCONVERT_API_KEY=your-cloudconvert-api-key-here
YOUTUBE_API_KEY=your-youtube-api-key-here

# === Optional: API fallback ===
# Used only if subscription quota runs out mid-run; otherwise can be left empty
ANTHROPIC_API_KEY=
```

**Step 2: Commit**

```bash
git add .env.template
git commit -m "docs: update .env.template — Claude billing now via subscription"
```

---

### Task J5: Update `README.md`

**Files:**
- Modify: `README.md`

**Step 1: Update top-of-file installation + usage sections** to reflect:
- Python 3.13 requirement
- `claude setup-token` prerequisite
- `pip install -e ".[dev]"` install
- `crypto-research "<query>"` console script
- Subscription billing default; API key only as fallback

Keep most domain-content sections (writing samples, output files, etc.) unchanged.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for new package layout + subscription billing"
```

---

### Task J6: Final full-suite verification

**No code changes. Verification only.**

```bash
pytest tests/ -v
# Expect: ~150 tests, all pass

# Live smoke (optional, requires subscription):
RUN_LIVE_TESTS=1 pytest tests/integration/ -v
# Expect: 1 test passes

# Manual end-to-end:
crypto-research "Ethereum Layer 2" --test --youtube
# Expect: full pipeline runs to completion
```

**No commit.**

---

## Done

When all tasks above pass:
- The package is at `src/crypto_research_agent/` with proper `pip install -e .` support
- All LLM calls route through `claude -p` subprocess (subscription billing)
- API fallback prompts user once on quota exhaustion
- Fact-checker is gone
- Output dirs use clean `query_TS` naming
- ~150 tests across all layers, all green
- 12 mixed "agents" → 6 real agents + 5 services + 4 pipeline stages
- ~600 LOC removed (vs net additions in tests + new abstractions)

---

## Notes for the executing engineer

- **Side-by-side strategy:** old code stays functional during Phases A–I. Don't import from `src/` into old code or vice versa.
- **Test name collisions in Phase J:** if you keep new test names matching old ones (e.g. `tests/agents/test_coordinator.py`), pytest may discover both during dev. Either:
  (a) Use a `_new.py` suffix during dev and rename in J2, OR
  (b) Delete old test files immediately after each new file passes (per-task cleanup).
  Option (b) is cleaner — adapt the per-task commits to include `git rm tests/agents/test_<old>.py` once the new test passes.
- **Long prompts in `claude -p`:** if argv length is a concern, switch the implementation in `_invoke_once` to pass `prompt` via stdin (`subprocess.run(..., input=prompt)`). Tested in B2/B3 paths via the same mocking; will require minimal changes.
- **Conversation in API fallback:** the `AnthropicAPIBackend._sessions` dict grows unboundedly within a run. Acceptable for a personal tool with at most one outline/article session per run; not appropriate as a long-lived server.
- **Concurrency (`--parallel`):** scaffolding present in `RunContext.parallel` but not wired through Analyzer yet. Add only if the engineer wants it; honor `min(args.parallel, 3)` cap.

