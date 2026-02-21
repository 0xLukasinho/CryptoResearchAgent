import time
import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase
from utils.substack_api_client import SubstackAPIClient
import random

class ArticleRetrievalAgent(ClaudeAgentBase):
    def __init__(self):
        super().__init__()
        self.substack_client = SubstackAPIClient()

    def process_urls(self, urls, search_plan, test_mode=False, max_age_days=None):
        """
        Process Substack URLs and retrieve articles via the API

        Args:
            urls: List of Substack URLs
            search_plan: Structured plan from the coordinator
            test_mode: If True, continue until finding relevant articles
            max_age_days: Maximum age of articles in days

        Returns:
            List of article content dictionaries
        """
        if test_mode:
            # Limit articles and Substacks in test mode
            articles_per_substack = 10
            max_substacks = 30  # Limit to 30 Substacks in test mode
            self.logger.info("TESTING MODE: Searching for relevant articles")
            self.logger.info(f"Will retrieve up to {articles_per_substack} articles per Substack")
        else:
            self.logger.info("Processing all Substacks...")
            articles_per_substack = 200
            max_substacks = len(urls)
            self.logger.info(f"Will retrieve up to {articles_per_substack} articles per Substack (with pagination)")

        if max_age_days is not None:
            self.logger.info(f"Filtering for articles newer than {max_age_days} days")

        # Retrieve articles from each URL
        all_articles = []
        processed_urls = 0
        error_count = 0  # Track consecutive errors for adaptive pausing

        # Process URLs until we hit our Substack limit
        for url in urls[:max_substacks]:
            processed_urls += 1
            self.logger.info(f"Checking Substack {processed_urls}/{max_substacks}: {url}")

            # Add a short pause between Substacks
            if processed_urls > 1:
                time.sleep(0.5)  # Half-second pause between Substacks

            # Use the Substack API client to get articles
            articles = self.substack_client.get_newsletter_posts(
                url,
                max_articles=articles_per_substack,
                max_age_days=max_age_days
            )

            # Real rate limit detection - only count as an error if the API returned nothing
            # AND we got no filtering summary (which would mean it was just filtered by date)
            if not articles and not hasattr(self.substack_client, 'last_had_age_filtering'):
                error_count += 1
                if error_count > 5:
                    self.logger.info("Multiple consecutive errors detected. Taking a longer break...")
                    time.sleep(3)  # Take a break after 5 consecutive errors
                    error_count = 0  # Reset after the break
            else:
                error_count = max(0, error_count - 1)  # Decrease error count on success

            # Add all articles to our list
            all_articles.extend(articles)

        self.logger.info(f"Retrieved {len(all_articles)} articles from {processed_urls} Substacks")
        return all_articles
