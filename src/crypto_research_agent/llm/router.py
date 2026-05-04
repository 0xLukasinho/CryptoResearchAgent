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
