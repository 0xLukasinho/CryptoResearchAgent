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
