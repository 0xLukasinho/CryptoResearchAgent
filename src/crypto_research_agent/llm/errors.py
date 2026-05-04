class ClaudeCodeError(Exception):
    """Base for all LLM backend errors."""


class QuotaExceeded(ClaudeCodeError):
    """Subscription quota is exhausted; caller should fall back to API."""


class AuthMissing(ClaudeCodeError):
    """No valid auth — user needs to run `claude setup-token` or set ANTHROPIC_API_KEY."""


class TransientError(ClaudeCodeError):
    """Network or timeout error; retry may help."""
