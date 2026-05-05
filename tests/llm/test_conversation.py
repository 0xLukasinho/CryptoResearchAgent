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
