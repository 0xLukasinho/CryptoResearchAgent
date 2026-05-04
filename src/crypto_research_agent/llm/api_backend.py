import uuid

import anthropic

from .types import ClaudeResponse
from .errors import AuthMissing, QuotaExceeded, TransientError, ClaudeCodeError
from ._json import parse_json_loose


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
                messages=list(messages),
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
        return parse_json_loose(response.text)
