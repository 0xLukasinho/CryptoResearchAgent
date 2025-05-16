from openai import OpenAI
import sys
sys.path.append('..')
from config import OPENAI_API_KEY, MODEL
import json

class AnalysisAgent:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = MODEL
    
    def analyze_article(self, article, search_plan, thesis_direction=None):
        """
        Analyze a single article for relevance and key insights
        
        Args:
            article: Article content dictionary
            search_plan: Structured plan from the coordinator
            thesis_direction: Optional user-provided direction for the thesis
            
        Returns:
            Analysis results with relevance score and reasoning
        """
        # Extract article info
        title = article.get('title', 'Unknown Title')
        date = article.get('date', 'Unknown Date')
        author = article.get('author', 'Unknown Author')
        text = article.get('text', '')
        url = article.get('url', '')
        
        # Use only the first 8000 characters of text to avoid token limits
        text_sample = text[:8000] + "..." if len(text) > 8000 else text
        
        # Add thesis information if provided
        thesis_info = f"\nThesis Direction: {thesis_direction}" if thesis_direction else ""
        
        # Fix the f-string with newlines
        relevance_guidelines_thesis = """- High relevance: Article directly addresses the thesis question with substantial insights
- Medium relevance: Article partially addresses the thesis with some relevant points
- Low relevance: Article mentions concepts related to the thesis but provides little direct insight"""

        relevance_guidelines_general = """- High relevance: Article is DIRECTLY about the search topic and contains substantial information related to it.
- Medium relevance: Article clearly discusses the search topic but may not be the main focus.
- Low relevance: Article only mentions the search topic in passing OR is PRIMARILY focused on other cryptocurrencies/projects not directly related to the query."""

        prompt = f"""
        You are the Article Analysis Agent, specialized in assessing crypto articles for relevance.
        
        Search Plan: {search_plan}{thesis_info}
        
        Article:
        Title: {title}
        Author: {author}
        Date: {date}
        URL: {url}
        
        Text Sample:
        {text_sample}
        
        CRITICAL INSTRUCTION: First determine if this article is written in English.
        - If the article is NOT in English, RETURN ONLY: {{"non_english": true, "language_detected": "name of detected language"}}
        - Do not analyze non-English content further

        CRITICAL INSTRUCTION FOR RELEVANCE SCORING:
        {f"Since a thesis direction is provided, relevance score MUST be determined SOLELY based on how well the article addresses the thesis topic, NOT the general search topic. The thesis is: '{thesis_direction}'" if thesis_direction else ""}
        
        If the article IS in English, analyze it and provide:
        1. Relevance score (High, Medium, Low) to the search plan and thesis direction - BE STRICT when determining the PRIMARY focus of the article
        2. Brief explanation of why it's relevant or not
        3. 2-3 key insights from the article related to the search topics
        4. Any specific crypto projects, technologies, or trends mentioned
        5. Thesis alignment score (High, Medium, Low) - how well the article supports or relates to the specified thesis direction
        6. Brief explanation of how the article aligns with or contradicts the thesis

        Relevance scoring guidelines:
        {relevance_guidelines_thesis if thesis_direction else relevance_guidelines_general}

        Format your response as a JSON object with keys: 'relevance_score', 'relevance_explanation', 'key_insights', 'mentioned_projects', 'thesis_alignment', 'thesis_alignment_explanation'

        Note: If no thesis direction was provided, set 'thesis_alignment' to 'Not Applicable' and 'thesis_alignment_explanation' to 'No thesis direction specified'.
        """
        
        messages = [
            {"role": "system", "content": "You are an Article Analysis Agent that evaluates crypto content for relevance and extracts key insights."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Check if article was identified as non-English
            if 'non_english' in analysis and analysis['non_english']:
                print(f"Discarding non-English article: '{title}' (detected as {analysis.get('language_detected', 'unknown')})")
                return None  # Return None for non-English content to be filtered out

            # Continue with normal processing for English content
            # Add article metadata to analysis
            analysis['title'] = title
            analysis['author'] = author
            analysis['date'] = date
            analysis['url'] = url
            
            # Adjust overall relevance based on thesis alignment if thesis was provided
            if thesis_direction and 'thesis_alignment' in analysis and analysis['thesis_alignment'] != 'Not Applicable':
                # When thesis is provided, make thesis alignment the PRIMARY determinant of relevance
                original_relevance = analysis['relevance_score']
                analysis['relevance_score'] = analysis['thesis_alignment']
                
                if original_relevance != analysis['relevance_score']:
                    analysis['relevance_explanation'] += f" (Relevance score adjusted to match thesis alignment: {analysis['thesis_alignment']})"
            
            return analysis
            
        except Exception as e:
            print(f"Error analyzing article: {e}")
            return {
                'title': title,
                'author': author,
                'date': date,
                'url': url,
                'relevance_score': 'Error',
                'relevance_explanation': f'Analysis failed: {str(e)}',
                'key_insights': ['Analysis error'],
                'mentioned_projects': [],
                'thesis_alignment': 'Error',
                'thesis_alignment_explanation': f'Analysis failed: {str(e)}'
            }
    
    def analyze_articles(self, articles, search_plan, thesis_direction=None, test_mode=False):
        """
        Analyze multiple articles for relevance
        
        Args:
            articles: List of article content dictionaries
            search_plan: Structured plan from the coordinator
            thesis_direction: Optional user-provided direction for the thesis
            test_mode: If True, stop after finding 2 relevant articles
            
        Returns:
            List of analyzed articles with relevance scores
        """
        analyzed_articles = []
        relevant_count = 0
        
        for i, article in enumerate(articles):
            print(f"Analyzing article {i+1}/{len(articles)}: {article.get('title', 'Unknown')}")
            analysis = self.analyze_article(article, search_plan, thesis_direction)
            
            if analysis is not None:  # Only add if not None (filtered out non-English)
                analyzed_articles.append(analysis)
                
                # In test mode, if we found enough relevant articles, stop early
                if test_mode and analysis.get('relevance_score') in ['High', 'Medium']:
                    relevant_count += 1
                    print(f"Found relevant article {relevant_count}/2")
                    if relevant_count >= 2:
                        print(f"TESTING MODE: Found {relevant_count} relevant articles, stopping early")
                        break
        
        return analyzed_articles 