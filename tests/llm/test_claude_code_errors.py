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


def test_json_is_error_non_quota_raises_claude_code_error():
    backend = ClaudeCodeBackend()
    body = json.dumps({"is_error": True, "result": "Internal model failure"})
    with patch("subprocess.run", return_value=_mock_run(stdout=body, returncode=0)):
        with pytest.raises(ClaudeCodeError):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_json_is_error_auth_message_raises_auth_missing():
    backend = ClaudeCodeBackend()
    body = json.dumps({"is_error": True, "result": "Error: not authenticated"})
    with patch("subprocess.run", return_value=_mock_run(stdout=body, returncode=0)):
        with pytest.raises(AuthMissing):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_auth_missing_detected():
    backend = ClaudeCodeBackend()
    with patch("subprocess.run",
               return_value=_mock_run(returncode=1, stderr="Error: not authenticated")):
        with pytest.raises(AuthMissing):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_claude_cli_not_on_path_raises_auth_missing():
    """Real 'CLI not installed' case: shutil.which returns None upfront."""
    backend = ClaudeCodeBackend()
    with patch("crypto_research_agent.llm.claude_code.shutil.which",
               return_value=None):
        with pytest.raises(AuthMissing, match="Claude Code"):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_subprocess_filenotfound_after_resolution_is_transient():
    """If shutil.which resolved the path successfully but subprocess.run later
    raises FileNotFoundError, that's a transient Windows process-creation
    hiccup (antivirus, file lock, etc.) — not an install/auth issue. Must be
    retryable, not fatal."""
    backend = ClaudeCodeBackend(max_retries=0)  # don't actually retry/wait
    with patch("crypto_research_agent.llm.claude_code.shutil.which",
               return_value="C:/path/to/claude.cmd"):
        with patch("subprocess.run",
                   side_effect=FileNotFoundError("[WinError 2]")):
            with pytest.raises(TransientError, match="transient"):
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


def test_overload_529_classified_as_transient():
    """Anthropic 529 / overload errors must be retryable. Otherwise a
    single capacity hiccup kills the whole pipeline."""
    backend = ClaudeCodeBackend(max_retries=0)  # don't actually wait/retry
    body = json.dumps({
        "is_error": True,
        "result": "API Error: Repeated 529 Overloaded errors. The API is at capacity.",
    })
    with patch("subprocess.run", return_value=_mock_run(stdout=body, returncode=0)):
        with pytest.raises(TransientError, match="529|Overload|Transient"):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_503_temporarily_unavailable_classified_as_transient():
    backend = ClaudeCodeBackend(max_retries=0)
    body = json.dumps({"is_error": True, "result": "503 Service Temporarily Unavailable"})
    with patch("subprocess.run", return_value=_mock_run(stdout=body, returncode=0)):
        with pytest.raises(TransientError):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_no_fallback_model_flag_used():
    """--fallback-model must NOT be added: it routes via the Anthropic API
    (not the subscription), and surprises users without API credit with
    'Credit balance is too low'. Overload resilience comes from the retry
    loop instead, which stays on the subscription."""
    backend = ClaudeCodeBackend()
    ok = json.dumps({
        "result": "ok", "session_id": "s", "total_cost_usd": 0.0,
        "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False,
    })
    with patch("subprocess.run", return_value=_mock_run(stdout=ok)) as mock_run:
        backend.complete(prompt="x", model="claude-opus-4-7")
    args = mock_run.call_args.args[0]
    assert "--fallback-model" not in args


def test_credit_balance_classified_as_quota_exceeded():
    """When claude -p routes through the API (e.g. via --fallback-model in
    older builds, or when we accidentally trigger API), 'Credit balance is
    too low' must be QuotaExceeded so the LLMRouter can offer the
    Opus/Sonnet/Abort prompt instead of hard-crashing."""
    backend = ClaudeCodeBackend(max_retries=0)
    body = json.dumps({
        "is_error": True,
        "result": "Credit balance is too low",
    })
    with patch("subprocess.run", return_value=_mock_run(stdout=body, returncode=0)):
        with pytest.raises(QuotaExceeded, match="Credit balance|quota"):
            backend.complete(prompt="x", model="claude-haiku-4-5-20251001")


def test_haiku_model_no_fallback_flag():
    """Haiku also gets no --fallback-model (same reason as Opus — API routing)."""
    backend = ClaudeCodeBackend()
    ok = json.dumps({
        "result": "ok", "session_id": "s", "total_cost_usd": 0.0,
        "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False,
    })
    with patch("subprocess.run", return_value=_mock_run(stdout=ok)) as mock_run:
        backend.complete(prompt="x", model="claude-haiku-4-5-20251001")
    args = mock_run.call_args.args[0]
    assert "--fallback-model" not in args
