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
