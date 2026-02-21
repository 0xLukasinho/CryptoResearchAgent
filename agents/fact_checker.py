import sys
import json
import time
import re
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase

class FactCheckerAgent(ClaudeAgentBase):
    """
    Agent responsible for verifying the factual accuracy of article sections against research sources.
    """

    def __init__(self, anthropic_client=None):
        """
        Initialize the FactCheckerAgent.

        Args:
            anthropic_client: Unused; kept for backward compatibility with main.py call signature.
        """
        super().__init__()
        self.logger.info(f"[FACT CHECKER] Using Claude model {self.model} for fact checking")

    def check_section(self, section_content, sources):
        """
        Verify the accuracy of a section against research sources.

        Args:
            section_content (str): The content of the section to check
            sources (dict): Dictionary of sources organized by priority

        Returns:
            dict: Fact checking results and corrections
        """
        self.logger.info("[FACT CHECKER] Starting fact check for section")
        start_time = time.time()

        system_prompt = """You are a fact checker for cryptocurrency research articles. Your task is to identify ONLY factual inaccuracies that DIRECTLY CONTRADICT the provided sources.

IMPORTANT GUIDELINES:
1. ONLY flag statements that explicitly contradict information in the sources.
2. DO NOT flag statements that are not mentioned in the sources but could be reasonable inferences or general knowledge.
3. DO NOT flag opinions, analyses, or speculations clearly presented as such.
4. If something is not mentioned in the sources, but doesn't contradict them, DO NOT flag it.
5. Focus on substantive factual errors like incorrect numbers, dates, names, or events.

Return your response as JSON with 'accurate', 'issues', and 'corrections' keys."""

        # Format sources for the prompt
        formatted_sources = ""
        for priority, source_list in sources.items():
            formatted_sources += f"\n## {priority} Priority Sources:\n"
            for i, source in enumerate(source_list):
                formatted_sources += f"\n### Source {i+1}:\n"
                formatted_sources += f"Title: {source.get('title', 'Untitled')}\n"
                formatted_sources += f"Text: {source.get('text', '')}\n"

        user_prompt = f"""
        Review this section of a cryptocurrency article for factual accuracy, focusing ONLY on statements that DIRECTLY CONTRADICT the source materials:

        {section_content}

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

        result = self.complete_json(user_prompt, system_prompt, max_tokens=1000)

        # Ensure result has the expected structure
        if not result:
            result = {"accurate": False, "issues": ["Failed to parse response as JSON"], "corrections": []}

        # Log completion
        elapsed_time = time.time() - start_time
        self.logger.info(f"[FACT CHECKER] Fact checking completed in {elapsed_time:.2f} seconds")

        # Log findings
        is_accurate = result.get('accurate', False)
        issues = result.get('issues', [])

        if is_accurate:
            self.logger.info("[FACT CHECKER] Section is factually accurate")
        else:
            self.logger.info(f"[FACT CHECKER] Found {len(issues)} factual issues")
            for i, issue in enumerate(issues):
                self.logger.info(f"  Issue {i+1}: {issue}")

        return result

    def suggest_corrections(self, section_content, check_results):
        """
        Generate corrected section content based on fact-checking results.

        Args:
            section_content (str): Original section content
            check_results (dict): Results from fact checking

        Returns:
            str: Corrected section content or original if no corrections needed
        """
        # If accurate, no corrections needed
        if check_results.get('accurate', False):
            return section_content

        # Get issues and corrections
        issues = check_results.get('issues', [])
        corrections = check_results.get('corrections', [])

        # Log corrections
        self.logger.info(f"[FACT CHECKER] Applying {len(corrections)} corrections")

        # Extract section heading
        heading_match = re.match(r'^(#+\s+.*?)(?:\n|$)', section_content)
        original_heading = heading_match.group(1) if heading_match else None

        # For simple cases, construct a system prompt to fix the section
        system_prompt = """You are a fact checker for cryptocurrency research articles.
Your task is to correct ONLY factual inaccuracies in the provided text while maintaining the original style and structure.
IMPORTANT: Preserve the exact writing style, including personal voice, sentence structure, tone, and any stylistic elements.
If the original uses first-person perspective, questions to readers, or specific patterns, maintain these in your corrections.
CRITICAL: If the text has a markdown heading (e.g., ## Heading), make sure to preserve it EXACTLY as it appears in the original.
DO NOT add qualifiers like "according to the sources" or "it appears that" unless they were in the original text.
DO NOT use triple backticks (```) in your response - they can cause formatting issues."""

        # Create a prompt that outlines the issues and needed corrections
        issues_text = "\n".join([f"- {issue}" for issue in issues])
        corrections_text = "\n".join([f"- {correction}" for correction in corrections])

        # Emphasize preserving the heading
        heading_instruction = ""
        if original_heading:
            heading_instruction = f"""
EXTREMELY IMPORTANT: The section begins with this exact heading:
```
{original_heading}
```
You MUST preserve this heading EXACTLY as shown above, maintaining the same format, spacing, and style.
"""

        user_prompt = f"""
        Please correct the following article section to fix ONLY the factual inaccuracies that DIRECTLY CONTRADICT the source materials.

        == ORIGINAL SECTION ==
        {section_content}

        == FACTUAL CONTRADICTIONS TO FIX ==
        {issues_text}

        == NEEDED CORRECTIONS ==
        {corrections_text}

        == HEADING PRESERVATION ==
        {heading_instruction}

        == TASK ==
        1. Correct ONLY the factual inaccuracies identified above that directly contradict sources
        2. CRITICAL: Maintain the EXACT original writing style, voice, and tone
           - If the original uses first-person perspective ("I", "we"), your correction must too
           - If the original addresses the reader directly or uses questions, your correction must too
           - Match the sentence structure, vocabulary level, and stylistic elements precisely
        3. Keep the same markdown formatting
        4. NEVER change the section heading - preserve it exactly as in the original
        5. Return the complete corrected section (not just the changes)
        6. DO NOT add qualifiers like "according to the sources" or "it appears that" unless they were in the original text
        7. DO NOT use triple backticks (```) in your response - they can cause formatting issues

        Do not include any explanations or notes about your corrections. Return only the corrected section content.
        """

        corrected_content = self.complete(user_prompt, system_prompt, max_tokens=4000)

        # Clean any backticks from the response
        corrected_content = self.clean_backticks(corrected_content)

        # Verify the heading is preserved, if not, restore it
        if original_heading:
            corrected_heading_match = re.match(r'^(#+\s+.*?)(?:\n|$)', corrected_content)
            if not corrected_heading_match or corrected_heading_match.group(1) != original_heading:
                # Heading is missing or incorrect, restore it
                rest_of_content = corrected_content
                if corrected_heading_match:
                    # Remove the incorrect heading
                    rest_of_content = corrected_content.replace(corrected_heading_match.group(0), "", 1).lstrip()
                # Add the original heading back
                corrected_content = f"{original_heading}\n\n{rest_of_content}"
                self.logger.info("[FACT CHECKER] Restored original section heading format")

        self.logger.info("[FACT CHECKER] Section corrected")
        return corrected_content

    def clean_backticks(self, content):
        """
        Remove triple backticks from content that might cause formatting issues.

        Args:
            content (str): Content that may contain backticks

        Returns:
            str: Cleaned content
        """
        # Handle nested markdown blocks by removing triple backticks (ensure they're properly balanced)
        if content.count('```') >= 2:
            # Only remove backticks that are likely wrapper backticks
            first_backtick = content.find('```')
            last_backtick = content.rfind('```')

            if first_backtick == 0 or (first_backtick > 0 and content[first_backtick-1] in ['\n', ' ']):
                content = content[:first_backtick] + content[first_backtick+3:]

            # Find the new last position after removing the first
            last_backtick = content.rfind('```')
            if last_backtick > 0 and (last_backtick + 3 == len(content) or content[last_backtick+3] in ['\n', ' ']):
                content = content[:last_backtick] + content[last_backtick+3:]

        # Check for incomplete code blocks
        if content.count('```') % 2 != 0:
            # Remove all remaining backticks to avoid unpaired backticks
            content = content.replace('```', '')

        return content
