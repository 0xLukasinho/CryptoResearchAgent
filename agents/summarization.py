import sys
sys.path.append('..')
from agents.claude_agent_base import ClaudeAgentBase

class SummarizationAgent(ClaudeAgentBase):
    def __init__(self):
        super().__init__()

    def summarize_articles(self, analyzed_articles, search_plan, query):
        """Original method for articles only - kept for backward compatibility"""
        return self.summarize_combined_results(analyzed_articles, [], search_plan, query)

    def summarize_combined_results(self, analyzed_articles, analyzed_videos, search_plan, query, thesis_direction=None):
        """
        Create concise summaries of relevant articles and videos in markdown format

        Args:
            analyzed_articles: List of analyzed articles with relevance scores
            analyzed_videos: List of analyzed videos with relevance scores
            search_plan: Structured plan from the coordinator
            query: Original user query
            thesis_direction: Optional user-provided direction for the thesis

        Returns:
            Markdown formatted summaries
        """
        # Filter for medium and high relevance content
        relevant_articles = [a for a in analyzed_articles if a.get('relevance_score') in ['High', 'Medium']]
        relevant_videos = [v for v in analyzed_videos if v.get('relevance_score') in ['High', 'Medium']]

        # Sort by relevance (High first, then Medium)
        # If thesis_direction is provided, also consider thesis_alignment in sorting
        if thesis_direction:
            sorted_articles = sorted(
                relevant_articles,
                key=lambda x: (
                    0 if x.get('relevance_score') == 'High' else 1,  # First by relevance
                    0 if x.get('thesis_alignment', 'Medium') == 'High' else  # Then by thesis alignment
                    (1 if x.get('thesis_alignment', 'Medium') == 'Medium' else 2)
                )
            )
        else:
            sorted_articles = sorted(
                relevant_articles,
                key=lambda x: 0 if x.get('relevance_score') == 'High' else 1
            )

        sorted_videos = sorted(
            relevant_videos,
            key=lambda x: (
                0 if x.get('relevance_score') == 'High' else 1,  # First by relevance
                -x.get('interview_score', 0)  # Then by interview score (high to low)
            )
        )

        if not sorted_articles and not sorted_videos:
            return "# AI Agent Search Results\n\n## Topic: \"" + query + "\"\n\nNo relevant content found."

        # Format content for the prompt
        content_text = ""

        # Add thesis direction if provided
        if thesis_direction:
            content_text += f"\nTHESIS DIRECTION: {thesis_direction}\n"

        # Add article information
        if sorted_articles:
            content_text += "\nRELEVANT ARTICLES:\n"
            for i, article in enumerate(sorted_articles):
                # Include thesis alignment if provided
                thesis_info = ""
                if thesis_direction and 'thesis_alignment' in article:
                    thesis_info = f"Thesis Alignment: {article.get('thesis_alignment', 'Unknown')}\nThesis Alignment Explanation: {article.get('thesis_alignment_explanation', 'Not provided')}"

                content_text += f"""
                Article {i+1}:
                Title: {article.get('title', 'Unknown')}
                Author: {article.get('author', 'Unknown')}
                Date: {article.get('date', 'Unknown')}
                URL: {article.get('url', 'Unknown')}
                Relevance: {article.get('relevance_score', 'Unknown')}
                Key Insights: {', '.join(article.get('key_insights', []))}
                {thesis_info}
                """

        # Add video information
        if sorted_videos:
            content_text += "\nRELEVANT VIDEOS:\n"
            for i, video in enumerate(sorted_videos):
                # Add transcript information if available
                transcript_info = ""
                if 'has_transcript' in video:
                    if video.get('has_transcript'):
                        transcript_info = "Transcript: Available"
                    else:
                        transcript_info = f"Transcript: Not available ({video.get('transcript_error', 'Unknown error')})"

                content_text += f"""
                Video {i+1}:
                Title: {video.get('title', 'Unknown')}
                Channel: {video.get('channel', 'Unknown')}
                Date: {video.get('date', 'Unknown')}
                URL: {video.get('url', 'Unknown')}
                Relevance: {video.get('relevance_score', 'Unknown')}
                Interview Score: {video.get('interview_score', 'Unknown')}
                {transcript_info}
                Key Points: {', '.join(video.get('key_points', []))}
                """

        # Include thesis instruction in prompt if thesis_direction is provided
        thesis_instruction = ""
        if thesis_direction:
            thesis_instruction = """
            Also include thesis alignment for each article:
            ```
            - **Thesis Alignment:** High/Medium/Low
              Brief comment on how the article aligns with the thesis direction.
            ```

            """

        user_prompt = f"""
        You are the Summarization Agent, specialized in creating concise, informative summaries of crypto content.

        Search Query: "{query}"
        {f'Thesis Direction: "{thesis_direction}"' if thesis_direction else ''}

        Relevant Content:
        {content_text}

        Create a markdown-formatted summary with the following structure:

        ```markdown
        # AI Agent Search Results

        ## Topic: "{query}"
        {f'## Thesis Direction: "{thesis_direction}"' if thesis_direction else ''}

        {'' if not sorted_articles else '### Articles:'}

        {'(Include numbered articles with the format below)' if sorted_articles else ''}

        {'' if not sorted_videos else '### Videos:'}

        {'(Include numbered videos with the format below)' if sorted_videos else ''}
        ```

        For each ARTICLE, use this format:
        ```
        #### 1. [Article Title](link_to_article)
        - **Author:** Author Name, Date
        - **Relevance:** High/Medium
        {thesis_instruction}
        - **Summary:**
          One concise paragraph summarizing key points and relevance to the topic.

        ---
        ```

        For each VIDEO, use this format:
        ```
        #### 1. [Video Title](link_to_video)
        - **Channel:** Channel Name, Date
        - **Relevance:** High/Medium
        - **Interview:** Yes/No (based on interview score > 5)
        - **Transcript:** Available/Not available
        - **Summary:**
          One concise paragraph summarizing content and relevance.

        ---
        ```

        Number items sequentially within each section.
        Write ONE concise paragraph (5-6 sentences) for each summary.
        Include "---" separator between items.
        """

        system_prompt = "You are a Summarization Agent that creates markdown-formatted summaries of crypto research content."

        try:
            summary = self.complete(user_prompt, system_prompt, max_tokens=4000)
            return summary

        except Exception as e:
            self.logger.error(f"Error in Summarization Agent: {e}")
            # Return error in markdown format
            return f"# AI Agent Search Results\n\n## Topic: \"{query}\"\n\nError generating summary: {str(e)}"
