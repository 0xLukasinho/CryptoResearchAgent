import subprocess
import json
from typing import Any

from .types import ClaudeResponse
from .errors import ClaudeCodeError, AuthMissing, QuotaExceeded, TransientError


class ClaudeCodeBackend:
    """Primary LLM backend — invokes `claude -p` subprocess for subscription billing."""

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, *, claude_executable: str = "claude",
                 timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self._claude = claude_executable
        self._timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
        resume_session: str | None = None,
    ) -> ClaudeResponse:
        cmd = self._build_command(model=model, system_prompt=system_prompt,
                                  resume_session=resume_session, prompt=prompt)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self._timeout, check=False,
        )
        return self._parse_response(result)

    def _build_command(self, *, model: str, system_prompt: str,
                       resume_session: str | None, prompt: str) -> list[str]:
        cmd = [
            self._claude, "-p", "--bare",
            "--output-format", "json",
            "--allowedTools", "",
            "--model", model,
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        if resume_session:
            cmd.extend(["--resume", resume_session])
        cmd.append(prompt)
        return cmd

    def _parse_response(self, result: subprocess.CompletedProcess) -> ClaudeResponse:
        # Error detection added in Task B3 — for now, just parse on success.
        data: dict[str, Any] = json.loads(result.stdout)
        usage = data.get("usage", {})
        return ClaudeResponse(
            text=data.get("result", ""),
            session_id=data.get("session_id"),
            cost_usd=data.get("total_cost_usd", 0.0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
