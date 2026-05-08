import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from ._json import parse_json_loose
from .errors import AuthMissing, ClaudeCodeError, QuotaExceeded, TransientError
from .types import ClaudeResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


QUOTA_PATTERNS = re.compile(
    r"(usage limit|quota exceeded|rate limit|credit balance)", re.IGNORECASE,
)
AUTH_PATTERNS = re.compile(r"(not authenticated|setup-token|unauthorized)", re.IGNORECASE)
# Anthropic infra is sometimes capacity-constrained — these are RETRYABLE.
# claude -p reports them as JSON `is_error: true` with a result message like
# "API Error: Repeated 529 Overloaded errors. The API is at capacity..." or
# 503/504/timeout text. Classify as TransientError so the retry loop kicks in.
TRANSIENT_PATTERNS = re.compile(
    r"(529|overload|capacity|503|504|temporarily unavailable|"
    r"timed?\s*out|connection reset|connection refused|"
    r"server error|internal error|bad gateway|gateway timeout)",
    re.IGNORECASE,
)


class ClaudeCodeBackend:
    """Primary LLM backend — invokes `claude -p` subprocess for subscription billing."""

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, *, claude_executable: str = "claude",
                 timeout: int = DEFAULT_TIMEOUT_SECONDS,
                 max_retries: int = 2,
                 retry_base_delay: float = 1.0):
        self._claude = claude_executable
        self._resolved_claude: str | None = None
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    def _resolve_executable(self) -> str:
        """Resolve `claude` to a full path via shutil.which (respects Windows
        PATHEXT, so .cmd/.bat shims from npm-global installs are found)."""
        if self._resolved_claude is not None:
            return self._resolved_claude
        resolved = shutil.which(self._claude)
        if resolved is None:
            raise AuthMissing(
                f"Claude Code CLI ({self._claude!r}) not found on PATH. "
                "Install from https://claude.com/download and run `claude setup-token`."
            )
        self._resolved_claude = resolved
        return resolved

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
        resume_session: str | None = None,
    ) -> ClaudeResponse:
        last_err: TransientError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._invoke_once(
                    prompt, model=model,
                    system_prompt=system_prompt,
                    resume_session=resume_session,
                )
            except TransientError as e:
                last_err = e
                if attempt < self._max_retries:
                    delay = self._retry_base_delay * (4 ** attempt)
                    time.sleep(delay)
                    continue
                raise
        # Unreachable
        raise last_err  # type: ignore[misc]

    def _invoke_once(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str,
        resume_session: str | None,
    ) -> ClaudeResponse:
        # System prompts can contain newlines, which break cmd.exe argv parsing
        # when claude is installed as a .cmd shim (e.g. npm-global on Windows).
        # Write to a temp file and use --append-system-prompt-file instead.
        sys_prompt_file: str | None = None
        if system_prompt and not resume_session:
            fd, sys_prompt_file = tempfile.mkstemp(suffix=".txt", text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(system_prompt)
            except Exception:
                os.close(fd) if fd else None
                raise

        try:
            # Prompt is piped via stdin instead of passed as argv. This avoids:
            #   (a) Windows command-line length limit (~32KB) when articles are large
            #   (b) cmd.exe argv breakage on newlines / quotes when invoked via .cmd shim
            cmd = self._build_command(
                model=model, sys_prompt_file=sys_prompt_file,
                resume_session=resume_session,
            )
            cmd[0] = self._resolve_executable()
            # CRITICAL: claude -p prefers ANTHROPIC_API_KEY over OAuth/subscription
            # when both are present — and python-dotenv loads ANTHROPIC_API_KEY
            # from .env into our process env, so without this every call would
            # bill against the user's API credit instead of their Claude Max
            # subscription. Strip the key from the subprocess env to force
            # OAuth/subscription billing. The AnthropicAPIBackend (only used as
            # an explicit user-confirmed fallback on quota) reads it directly.
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            try:
                result = subprocess.run(
                    cmd, input=prompt, env=env,
                    capture_output=True, text=True, encoding="utf-8",
                    timeout=self._timeout, check=False,
                )
            except FileNotFoundError as e:
                # We resolved + cached the claude path upfront via shutil.which.
                # A FileNotFoundError from subprocess.run after that is almost
                # always a transient Windows process-creation hiccup (antivirus
                # interference, file lock, momentary EBUSY on the .cmd shim) —
                # NOT a real install/auth issue. Classify as TransientError so
                # the retry loop kicks in instead of aborting the whole pipeline.
                if self._resolved_claude is not None:
                    raise TransientError(
                        f"subprocess.run raised FileNotFoundError despite "
                        f"resolved claude path {self._resolved_claude!r}: {e}. "
                        "Likely a transient Windows process-creation hiccup."
                    ) from e
                raise AuthMissing(
                    "Claude Code CLI not found on PATH. Install from "
                    "https://claude.com/download and run `claude setup-token`."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise ClaudeCodeError(
                    f"`claude -p` timed out after {self._timeout}s"
                ) from e
        finally:
            if sys_prompt_file:
                try:
                    os.unlink(sys_prompt_file)
                except OSError:
                    pass

        self._raise_on_errors(result)
        return self._parse_success(result.stdout)

    def complete_json(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
    ) -> dict:
        strict = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "You MUST respond with valid JSON only. "
            "No explanation, no markdown fences, no commentary. Just the raw JSON object."
        )
        response = self.complete(prompt=prompt, model=model, system_prompt=strict)
        parsed = parse_json_loose(response.text)
        if not parsed and response.text.strip():
            logger.warning(
                "complete_json: failed to parse response as JSON (model=%s); raw=%r",
                model, response.text[:300],
            )
        return parsed

    def _build_command(self, *, model: str, sys_prompt_file: str | None,
                       resume_session: str | None) -> list[str]:
        cmd = [
            self._claude, "-p",
            "--output-format", "json",
            "--tools", "",
            "--model", model,
        ]
        # NOTE: do NOT add --fallback-model — claude -p routes the fallback
        # call through the Anthropic API (not the subscription), so without
        # API credit it returns "Credit balance is too low" and crashes.
        # Overload resilience comes from our TransientError retry loop instead,
        # which retries the same model on subscription billing.
        if sys_prompt_file and not resume_session:
            cmd.extend(["--append-system-prompt-file", sys_prompt_file])
        if resume_session:
            cmd.extend(["--resume", resume_session])
        # NB: prompt is NOT appended — it's piped via stdin in _invoke_once.
        return cmd

    def _raise_on_errors(self, result: subprocess.CompletedProcess) -> None:
        stderr = result.stderr or ""
        # JSON-level error (returncode may be 0)
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                if data.get("is_error"):
                    msg = data.get("result") or ""
                    if QUOTA_PATTERNS.search(msg):
                        raise QuotaExceeded(f"Subscription quota exhausted: {msg}")
                    if AUTH_PATTERNS.search(msg):
                        raise AuthMissing(
                            f"Claude Code is not authenticated. "
                            f"Run `claude setup-token` or `claude login`. ({msg})"
                        )
                    if TRANSIENT_PATTERNS.search(msg):
                        raise TransientError(f"Transient API error: {msg}")
                    raise ClaudeCodeError(f"Claude returned error: {msg}")
            except json.JSONDecodeError as e:
                if result.returncode == 0:
                    raise ClaudeCodeError(
                        f"`claude -p` returned malformed JSON despite exit 0: "
                        f"{result.stdout[:200]!r}"
                    ) from e
                # else: fall through to returncode-based classification below
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
        # Default for non-zero exits without specific patterns: transient.
        # The retry loop will attempt up to max_retries more times.
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
