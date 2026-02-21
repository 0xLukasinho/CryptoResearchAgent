import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase
from utils.substack_api_client import SubstackAPIClient
import json
import random

class DatabaseSearchAgent(ClaudeAgentBase):
    def __init__(self):
        super().__init__()
        self.substack_client = SubstackAPIClient()

    def search(self, query, search_plan, substack_data):
        """
        Return a sample of Substacks without filtering

        Args:
            query: Original user query
            search_plan: Structured plan from the coordinator
            substack_data: DataFrame with Substack data

        Returns:
            List of Substack URLs
        """
        # Get all valid URLs
        all_urls = substack_data['Substack URL'].dropna().tolist()

        # Filter out empty strings and clean URLs
        valid_urls = []
        for url in all_urls:
            if url and isinstance(url, str) and len(url) > 5:
                # Ensure proper URL format
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                valid_urls.append(url)

        self.logger.info(f"Found {len(valid_urls)} total Substacks with valid URLs")

        # For test mode & debugging, shuffle the URLs to get a random sample
        random.shuffle(valid_urls)

        return valid_urls
