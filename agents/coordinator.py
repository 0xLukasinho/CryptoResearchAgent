from openai import OpenAI
import sys
sys.path.append('..')
from config import OPENAI_API_KEY, MODEL
import json

class CoordinatorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = MODEL
        self.conversation_history = []
        
    def add_to_history(self, role, content):
        """Add a message to the conversation history"""
        self.conversation_history.append({"role": role, "content": content})
    
    def ask(self, query):
        """
        Process the initial user query and coordinate the workflow
        
        Args:
            query: User's research question
            
        Returns:
            Parsed plan for research
        """
        system_prompt = """
        You are the Coordinator Agent, responsible for orchestrating a crypto research workflow.
        Your job is to:
        1. Understand the user's crypto research request
        2. Break it down into a plan with steps for other specialized agents
        3. Extract important keywords, topics, and crypto terms from the query
        
        Format your response as a JSON-like structure with:
        - main_topic: The primary cryptocurrency or blockchain topic being researched
        - subtopics: List of related subtopics or aspects to explore
        - keywords: List of important keywords for database searching
        - search_strategy: Brief explanation of the search approach
        - required_terms: List of terms STRICTLY TAKEN DIRECTLY from the user's query. NEVER add additional terms that weren't explicitly mentioned by the user. For example, if the query is just "Bitcoin", the only required term should be ["Bitcoin"].
        - competing_projects: List of major competing projects that would be considered OFF-TOPIC if they are the PRIMARY focus of an article/video (not just mentioned for comparison).
        
        Be precise and use ONLY words that appear in the original query for required_terms.
        For competing_projects, identify which major competing projects would be considered off-topic for this specific query when they are the main subject of content.
        """
        
        self.add_to_history("system", system_prompt)
        self.add_to_history("user", query)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            self.add_to_history("assistant", result)
            
            return result
        
        except Exception as e:
            print(f"Error in Coordinator Agent: {e}")
            return None
    
    def synthesize_final_results(self, analysis_results):
        """
        Synthesize final results from all agents to present to the user
        
        Args:
            analysis_results: List of analyzed and summarized articles
            
        Returns:
            Final formatted report for the user
        """
        prompt = f"""
        Based on the crypto research results provided, create a final comprehensive report.
        
        Analysis Results:
        {analysis_results}
        
        Format the report with:
        1. An executive summary of key findings
        2. A categorized list of the most relevant articles
        3. Brief highlights of the most important insights found
        4. Suggestions for further research
        
        The report should be easy to read and actionable for a crypto researcher.
        """
        
        messages = [
            {"role": "system", "content": "You are the Coordinator Agent synthesizing final research results into a clear, actionable report."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            
            result = response.choices[0].message.content
            return result
            
        except Exception as e:
            print(f"Error synthesizing final results: {e}")
            return "Error generating final report." 