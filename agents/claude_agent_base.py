# agents/claude_agent_base.py
import json
import re
import sys
sys.path.append('..')
from agents.anthropic_client import AnthropicClient
from config import CLAUDE_FAST_MODEL
from utils.logger import get_logger
from utils.retry import retry_on_rate_limit


class ClaudeAgentBase:
    """
    Base class for agents using Claude Haiku for cost-efficient tasks.
    Provides JSON completion, retry handling, and structured logging.
    Subclasses can override self.model to use a different model.
    """

    def __init__(self, test_mode=False):
        self.client = AnthropicClient(test_mode=test_mode)
        self.model = CLAUDE_FAST_MODEL
        self.logger = get_logger(self.__class__.__name__)

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def complete(self, prompt: str, system_prompt: str = "", max_tokens: int = 2000) -> str:
        """Generate a text response."""
        return self.client.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            model_override=self.model
        )

    def complete_json(self, prompt: str, system_prompt: str = "", max_tokens: int = 2000) -> dict:
        """
        Generate a JSON response, parsing and returning as a dict.
        Appends a strict JSON-only instruction to the system prompt.
        """
        json_system = (
            system_prompt
            + "\n\nYou MUST respond with valid JSON only. "
            "No explanation, no markdown fences, no commentary. Just the raw JSON object."
        )
        response = self.complete(prompt, json_system, max_tokens)

        # Direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Extract JSON object from mixed response
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        self.logger.error(f"Failed to parse JSON response: {response[:200]}")
        return {}
