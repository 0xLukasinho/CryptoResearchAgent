import anthropic
import sys
sys.path.append('..')
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_TEST_MODEL, FACT_CHECKING_MODEL

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
            print(f"[ANTHROPIC] Using test model: {self.model} (more cost efficient)")
        else:
            print(f"[ANTHROPIC] Using standard model: {self.model}")
    
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
            # Use override model if provided, otherwise use the default
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
            print(f"Error generating content with Claude: {e}")
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
        system_prompt = """You are a fact checker for cryptocurrency research articles. Your task is to identify ONLY factual inaccuracies that DIRECTLY CONTRADICT the provided sources. 

IMPORTANT GUIDELINES:
1. ONLY flag statements that explicitly contradict information in the sources.
2. DO NOT flag statements that are not mentioned in the sources but could be reasonable inferences or general knowledge.
3. DO NOT flag opinions, analyses, or speculations clearly presented as such.
4. If something is not mentioned in the sources, but doesn't contradict them, DO NOT flag it.
5. Focus on substantive factual errors like incorrect numbers, dates, names, or events.

Return your response as JSON with 'accurate', 'issues', and 'corrections' keys."""
        
        # Use override model if provided, otherwise use the default
        model_to_use = model_override if model_override else self.model
        
        # Format sources for the prompt
        formatted_sources = ""
        for priority, source_list in sources.items():
            formatted_sources += f"\n## {priority} Priority Sources:\n"
            for i, source in enumerate(source_list):
                formatted_sources += f"\n### Source {i+1}:\n"
                formatted_sources += f"Title: {source.get('title', 'Untitled')}\n"
                # No truncation of source text
                formatted_sources += f"Text: {source.get('text', '')}\n"
        
        # Create the prompt
        prompt = f"""
        Review this section of a cryptocurrency article for factual accuracy, focusing ONLY on statements that DIRECTLY CONTRADICT the source materials:

        {content}

        Here are the source materials to verify against (in priority order):
        {formatted_sources}

        INSTRUCTIONS:
        1. ONLY flag statements that DIRECTLY CONTRADICT information in the sources
        2. Ignore statements not mentioned in sources if they don't contradict anything
        3. Allow for reasonable speculation, analysis, and opinion
        4. Only focus on substantive factual errors:
           - Incorrect numbers, statistics or financial data
           - Wrong names of people, projects, or organizations
           - Incorrect dates or timelines
           - Misattributed quotes
           - Incorrect technical capabilities or features

        Format your response as JSON with these keys:
        - "accurate": true/false (true if no contradictions found)
        - "issues": [list of specific contradictions found]
        - "corrections": [list of specific corrections]

        Example format:
        {{
          "accurate": false,
          "issues": ["The article claims Bitcoin was created in 2010, but sources clearly state it was created in 2008 and launched in 2009"],
          "corrections": ["Bitcoin was created in 2008 and launched in 2009 by Satoshi Nakamoto"]
        }}
        """
        
        try:
            message = self.client.messages.create(
                model=model_to_use,  # Use potentially overridden model
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            
            # Parse response as JSON if possible
            import json
            try:
                # Look for JSON in the response
                import re
                json_match = re.search(r'({.*})', response_text.replace('\n', ''))
                if json_match:
                    return json.loads(json_match.group(1))
                else:
                    # Try to parse the entire response as JSON
                    return json.loads(response_text)
            except:
                # Return as text if JSON parsing fails
                return {"accurate": False, "issues": ["Failed to parse response as JSON"], "corrections": [response_text]}
            
        except Exception as e:
            print(f"Error checking facts with Claude: {e}")
            return {"accurate": False, "issues": [f"API Error: {str(e)}"], "corrections": []} 