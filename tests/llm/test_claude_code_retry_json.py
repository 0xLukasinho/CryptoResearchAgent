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
