import subprocess
import json
import re
from typing import Any

from .types import ClaudeResponse
from .errors import ClaudeCodeError, AuthMissing, QuotaExceeded, TransientError


QUOTA_PATTERNS = re.compile(r"(usage limit|quota exceeded|rate limit)", re.IGNORECASE)
AUTH_PATTERNS = re.compile(r"(not authenticated|setup-token|unauthorized)", re.IGNORECASE)


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
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                timeout=self._timeout, check=False,
            )
        except FileNotFoundError as e:
            raise AuthMissing(
                "Claude Code CLI not found on PATH. Install from "
                "https://claude.com/download and run `claude setup-token`."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ClaudeCodeError(
                f"`claude -p` timed out after {self._timeout}s"
            ) from e

        self._raise_on_errors(result)
        return self._parse_success(result.stdout)

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

    def _raise_on_errors(self, result: subprocess.CompletedProcess) -> None:
        stderr = result.stderr or ""
        # JSON-level error (returncode may be 0)
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                if data.get("is_error"):
                    msg = data.get("result", "")
                    if QUOTA_PATTERNS.search(msg):
                        raise QuotaExceeded(f"Subscription quota exhausted: {msg}")
                    raise ClaudeCodeError(f"Claude returned error: {msg}")
            except json.JSONDecodeError:
                pass
        if result.returncode == 0:
            return
        # Non-zero exit
        if QUOTA_PATTERNS.search(stderr):
            raise QuotaExceeded(f"Subscription quota exhausted: {stderr.strip()}")
        if AUTH_PATTERNS.search(stderr):
            raise AuthMissing(
                f"Claude Code is not authenticated. "
                f"Run `claude setup-token` or `claude login`. ({stderr.strip()})"
            )
        raise TransientError(
            f"`claude -p` failed (exit {result.returncode}): {stderr.strip() or '<no stderr>'}"
        )

    def _parse_success(self, stdout: str) -> ClaudeResponse:
        data: dict[str, Any] = json.loads(stdout)
        usage = data.get("usage", {})
        return ClaudeResponse(
            text=data.get("result", ""),
            session_id=data.get("session_id"),
            cost_usd=data.get("total_cost_usd", 0.0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
