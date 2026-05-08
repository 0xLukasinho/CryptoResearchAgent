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
    # Path is resolved via shutil.which on Windows (.cmd shim) — accept any suffix
    assert "claude" in args[0].lower()
    assert "-p" in args
    assert "--output-format" in args and "json" in args
    assert "--tools" in args
    assert "--model" in args
    assert "claude-haiku-4-5-20251001" in args
    assert "--append-system-prompt-file" in args

    assert response.text == "Hello, world!"
    assert response.session_id == "sess-1"
    assert response.cost_usd == 0.001
    assert response.input_tokens == 10
    assert response.output_tokens == 5


def test_subprocess_env_strips_anthropic_api_key():
    """CRITICAL: claude -p prefers ANTHROPIC_API_KEY over OAuth when both are
    present. Without scrubbing, every call would bill the user's API credit
    instead of their Claude Max subscription. Verify the env passed to
    subprocess.run does NOT contain ANTHROPIC_API_KEY even when it's in
    the parent process env."""
    import os
    backend = ClaudeCodeBackend()
    fake_stdout = {"result": "ok", "session_id": "s", "total_cost_usd": 0.0,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False}
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-12345"}, clear=False):
        with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
            backend.complete(prompt="hi", model="claude-haiku-4-5-20251001")
        env_passed = mock_run.call_args.kwargs.get("env")
        assert env_passed is not None, (
            "subprocess.run was called without an explicit env argument — "
            "the parent ANTHROPIC_API_KEY would leak through and route via API"
        )
        assert "ANTHROPIC_API_KEY" not in env_passed, (
            "ANTHROPIC_API_KEY leaked into claude -p subprocess env — "
            "calls would bill against API credit instead of subscription"
        )
        # Other env vars should still be there (subprocess needs PATH etc.)
        assert "PATH" in env_passed or "Path" in env_passed


def test_complete_passes_prompt_via_stdin_not_argv():
    """Prompt is piped to claude via stdin, not appended as argv positional —
    avoids Windows argv length limits + cmd.exe newline breakage."""
    backend = ClaudeCodeBackend()
    fake_stdout = {"result": "ok", "session_id": "s", "total_cost_usd": 0.0,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False}
    with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
        backend.complete(prompt="LONG PROMPT TEXT", model="claude-haiku-4-5-20251001")
    args = mock_run.call_args.args[0]
    kwargs = mock_run.call_args.kwargs
    assert "LONG PROMPT TEXT" not in args
    assert kwargs.get("input") == "LONG PROMPT TEXT"


def test_complete_omits_system_prompt_flag_when_empty():
    backend = ClaudeCodeBackend()
    fake_stdout = {"result": "hi", "session_id": "s", "total_cost_usd": 0.0,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False}
    with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
        backend.complete(prompt="hi", model="claude-haiku-4-5-20251001")
    args = mock_run.call_args.args[0]
    assert "--append-system-prompt-file" not in args


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


def test_complete_omits_system_prompt_flag_when_resuming_session():
    """When --resume is passed, --append-system-prompt should NOT be added,
    because the system prompt is already baked into the resumed session."""
    backend = ClaudeCodeBackend()
    fake_stdout = {"result": "ok", "session_id": "s", "total_cost_usd": 0.0,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "is_error": False}
    with patch("subprocess.run", return_value=_mock_run(fake_stdout)) as mock_run:
        backend.complete(
            prompt="next",
            model="claude-haiku-4-5-20251001",
            system_prompt="be terse",
            resume_session="sess-1",
        )
    args = mock_run.call_args.args[0]
    assert "--append-system-prompt-file" not in args
    assert "--resume" in args and "sess-1" in args
