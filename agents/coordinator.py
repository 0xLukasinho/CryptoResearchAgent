# agents/coordinator.py
import json
import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase


class CoordinatorAgent(ClaudeAgentBase):

    def ask(self, query: str) -> str:
        """
        Process the user's research query and return a structured JSON plan string.

        Returns JSON with: main_topic, subtopics, keywords, search_strategy,
        required_terms, competing_projects
        """
        system = """You are the Coordinator Agent orchestrating a crypto research workflow.
Analyze the user's research request and extract key information.

You MUST respond with valid JSON containing:
- main_topic: The primary cryptocurrency or blockchain topic
- subtopics: List of related subtopics to explore
- keywords: List of important keywords for searching
- search_strategy: Brief explanation of search approach
- required_terms: Terms STRICTLY from the user's query — never add extras not in the query
- competing_projects: Major competing projects that would be OFF-TOPIC if they are the main subject"""

        result = self.complete_json(query, system, max_tokens=1000)
        return json.dumps(result)

    def synthesize_final_results(self, analysis_results: str) -> str:
        """Synthesize final results from all agents into a readable report."""
        prompt = f"""Based on the crypto research results, create a final comprehensive report.

Analysis Results:
{analysis_results}

Format the report with:
1. An executive summary of key findings
2. A categorized list of the most relevant articles
3. Brief highlights of the most important insights
4. Suggestions for further research"""

        system = "You are the Coordinator Agent synthesizing research results into a clear, actionable report."
        return self.complete(prompt, system, max_tokens=2000)
