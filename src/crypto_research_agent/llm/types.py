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
