import anthropic
import sys
sys.path.append('..')
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_TEST_MODEL
from utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicClient:
    """
    Client for interacting with Anthropic's Claude API.
    """

    def __init__(self, test_mode=False):
        """
        Initialize the Anthropic client with the API key from config.

        Args:
            test_mode (bool): Whether to use the test model (Haiku) for cheaper operation
        """
        if not ANTHROPIC_API_KEY:
            raise ValueError("Anthropic API key is missing. Please set ANTHROPIC_API_KEY in config.py or as an environment variable.")

        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_TEST_MODEL if test_mode else ANTHROPIC_MODEL
        self.test_mode = test_mode

        if self.test_mode:
            logger.info(f"[ANTHROPIC] Using test model: {self.model} (more cost efficient)")
        else:
            logger.info(f"[ANTHROPIC] Using standard model: {self.model}")

    def generate_content(self, prompt, system_prompt="", max_tokens=4000, model_override=None):
        """
        Generate content using Claude.

        Args:
            prompt (str): The user prompt
            system_prompt (str, optional): System instructions for Claude
            max_tokens (int, optional): Maximum tokens to generate
            model_override (str, optional): Override the default model for this call

        Returns:
            str: Generated content from Claude
        """
        try:
            model_to_use = model_override if model_override else self.model

            message = self.client.messages.create(
                model=model_to_use,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating content with Claude: {e}")
            return f"Error: {str(e)}"

    def generate_with_history(self, messages, system_prompt="", max_tokens=4000, model_override=None):
        """
        Generate content using a full conversation history (multi-turn).

        Args:
            messages (list): List of role/content dicts for the conversation history
            system_prompt (str): System instructions for Claude
            max_tokens (int): Maximum tokens to generate
            model_override (str): Override the default model for this call

        Returns:
            str: Generated content from Claude
        """
        model_to_use = model_override if model_override else self.model
        try:
            message = self.client.messages.create(
                model=model_to_use,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating content with history: {e}")
            return f"Error: {str(e)}"

    def check_facts(self, content, sources, max_tokens=2000, model_override=None):
        """
        Use Claude to check facts in content against sources.

        Args:
            content (str): The content to fact-check
            sources (dict): Dictionary of sources to check against
            max_tokens (int, optional): Maximum tokens to generate
            model_override (str, optional): Override the default model for this call

        Returns:
            dict: Fact-checking results from Claude
        """
        system_prompt = (
            "You are a fact checker for cryptocurrency research articles. "
            "Your task is to identify ONLY factual inaccuracies that DIRECTLY CONTRADICT the provided sources. "
            "IMPORTANT GUIDELINES: "
            "1. ONLY flag statements that explicitly contradict information in the sources. "
            "2. DO NOT flag statements not in the sources if they do not contradict them. "
            "3. DO NOT flag opinions, analyses, or speculations clearly presented as such. "
            "4. Focus on substantive factual errors like incorrect numbers, dates, names, or events. "
            "Return your response as JSON with accurate, issues, and corrections keys."
        )

        model_to_use = model_override if model_override else self.model

        formatted_sources = ""
        for priority, source_list in sources.items():
            formatted_sources += chr(10) + "## " + str(priority) + " Priority Sources:" + chr(10)
            for i, source in enumerate(source_list):
                formatted_sources += chr(10) + "### Source " + str(i + 1) + ":" + chr(10)
                formatted_sources += "Title: " + source.get("title", "Untitled") + chr(10)
                formatted_sources += "Text: " + source.get("text", "") + chr(10)

        prompt = (
            "Review this section of a cryptocurrency article for factual accuracy, "
            "focusing ONLY on statements that DIRECTLY CONTRADICT the source materials:" + chr(10) + chr(10)
            + content + chr(10) + chr(10)
            + "Here are the source materials to verify against (in priority order):" + chr(10)
            + formatted_sources
        )

        try:
            message = self.client.messages.create(
                model=model_to_use,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text

            import json
            import re
            try:
                json_match = re.search(r"({.*})", response_text.replace(chr(10), ""))
                if json_match:
                    return json.loads(json_match.group(1))
                else:
                    return json.loads(response_text)
            except Exception:
                return {"accurate": False, "issues": ["Failed to parse response as JSON"], "corrections": [response_text]}

        except Exception as e:
            logger.error(f"Error checking facts with Claude: {e}")
            return {"accurate": False, "issues": [f"API Error: {str(e)}"], "corrections": []}
