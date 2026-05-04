"""Shared JSON parsing helpers for LLM backends.

Used by ClaudeCodeBackend (via claude -p subprocess) and AnthropicAPIBackend
(via SDK) to parse responses that should be JSON but may contain prose around
the JSON object due to model variability.
"""
import json
import re

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_loose(text: str) -> dict:
    """Parse text as JSON, tolerantly.

    Strategy:
    1. Strict json.loads on the whole text.
    2. If that fails, regex-extract the first {...} block (greedy, supports nesting)
       and try strict json.loads on that.
    3. If both fail, return {}.

    Greedy regex is intentional: it spans the first '{' to the last '}'
    so nested objects parse correctly. Multiple top-level objects in one
    string fall through to {}, which is acceptable because callers always
    request a single JSON object via prompt instructions.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSON_OBJECT_RE.search(text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}
