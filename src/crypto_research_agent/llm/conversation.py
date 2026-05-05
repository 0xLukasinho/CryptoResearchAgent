from .types import LLMBackend


class Conversation:
    """Multi-turn wrapper around an LLMBackend (router or raw backend)."""

    def __init__(self, backend: LLMBackend, *, model: str, system_prompt: str):
        self._backend = backend
        self._model = model
        self._system_prompt = system_prompt
        self._session_id: str | None = None
        self._turn_count = 0

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def send(self, user_message: str) -> str:
        response = self._backend.complete(
            prompt=user_message,
            model=self._model,
            system_prompt=self._system_prompt if self._turn_count == 0 else "",
            resume_session=self._session_id,
        )
        self._session_id = response.session_id
        self._turn_count += 1
        return response.text
