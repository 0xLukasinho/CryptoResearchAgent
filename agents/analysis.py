# agents/analysis.py
import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase
from utils.token_utils import truncate_to_token_limit
from config import CLAUDE_FAST_MODEL


class AnalysisAgent(ClaudeAgentBase):

    def analyze_article(self, article: dict, search_plan: str, thesis_direction: str = None) -> dict:
        """Analyze a single article for relevance and key insights."""
        title = article.get('title', 'Unknown Title')
        date = article.get('date', 'Unknown Date')
        author = article.get('author', 'Unknown Author')
        text = article.get('text', '')
        url = article.get('url', '')

        # Use token-accurate truncation instead of hardcoded char count
        text_sample = truncate_to_token_limit(text, CLAUDE_FAST_MODEL, 1500)
        thesis_info = f"\nThesis Direction: {thesis_direction}" if thesis_direction else ""

        prompt = f"""Analyze this crypto article for relevance.

Search Plan: {search_plan}{thesis_info}

Article:
Title: {title}
Author: {author}
Date: {date}
URL: {url}

Text:
{text_sample}

CRITICAL: First check if the article is in English.
- If NOT in English, return ONLY: {{"non_english": true, "language_detected": "language name"}}
- If in English, return JSON with keys: relevance_score (High/Medium/Low), relevance_explanation, key_insights (list of strings), mentioned_projects (list), thesis_alignment (High/Medium/Low/Not Applicable), thesis_alignment_explanation

Relevance scoring: High = article is directly about the topic with substantial info. Medium = topic is present but not main focus. Low = only mentioned in passing or primarily about competing projects."""

        system = "You are an Article Analysis Agent evaluating crypto content. Respond with valid JSON only."
        result = self.complete_json(prompt, system, max_tokens=800)

        if not result:
            return {
                'title': title, 'author': author, 'date': date, 'url': url,
                'relevance_score': 'Error', 'relevance_explanation': 'Analysis failed',
                'key_insights': [], 'mentioned_projects': [],
                'thesis_alignment': 'Error', 'thesis_alignment_explanation': 'Analysis failed'
            }

        if result.get('non_english'):
            self.logger.info(f"Discarding non-English article: '{title}' ({result.get('language_detected', 'unknown')})")
            return None

        result.update({'title': title, 'author': author, 'date': date, 'url': url})

        # When thesis provided, use thesis alignment as the relevance score
        if thesis_direction and result.get('thesis_alignment') not in ('Not Applicable', 'Error', None):
            result['relevance_score'] = result['thesis_alignment']

        return result

    def analyze_articles(self, articles: list, search_plan: str, thesis_direction: str = None, test_mode: bool = False) -> list:
        """Analyze multiple articles for relevance."""
        analyzed = []
        relevant_count = 0

        for i, article in enumerate(articles):
            self.logger.info(f"Analyzing article {i+1}/{len(articles)}: {article.get('title', 'Unknown')}")
            result = self.analyze_article(article, search_plan, thesis_direction)

            if result is not None:
                analyzed.append(result)
                if test_mode and result.get('relevance_score') in ('High', 'Medium'):
                    relevant_count += 1
                    if relevant_count >= 2:
                        self.logger.info(f"Test mode: found {relevant_count} relevant articles, stopping early")
                        break

        return analyzed
