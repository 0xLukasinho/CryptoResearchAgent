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
