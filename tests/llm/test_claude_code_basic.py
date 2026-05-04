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
