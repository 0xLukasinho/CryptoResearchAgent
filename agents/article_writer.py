# agents/article_writer.py
import os
import sys
import time
sys.path.append('..')
from config import ARTICLE_FILENAME, CLAUDE_QUALITY_MODEL
from utils.logger import get_logger
from utils.retry import retry_on_rate_limit

logger = get_logger(__name__)


class ArticleWriterAgent:
    """
    Stateful agent that writes a full article in a single Claude conversation thread.
    All sections and revisions happen within the same conversation, so the model
    always has full context of what it has already written when generating or revising.
    """

    def __init__(self, anthropic_client):
        self.anthropic_client = anthropic_client
        self.article_title = ""
        self.article_file = None
        self.conversation_history = []
        self.system_prompt = ""
        # Track accepted sections for clean file reconstruction on revision
        self.accepted_sections = []  # list of {'title': str, 'content': str}

    def start_article(self, title: str, query_output_dir: str, style_card_str: str,
                      outline: str, research_summary: str) -> str:
        """
        Initialize the article conversation with full context.
        Must be called before write_section().

        Args:
            title: Article title
            query_output_dir: Directory to save the article file
            style_card_str: Formatted style card from StyleLearningAgent.format_style_card_for_prompt()
            outline: Full article outline text
            research_summary: Condensed research summary from SummarizationAgent

        Returns:
            str: Path to the created article file
        """
        self.article_title = title
        self.article_file = os.path.join(query_output_dir, ARTICLE_FILENAME)

        self.system_prompt = f"""You are a respected crypto analyst writing a research article.

{style_card_str}

CRITICAL: Every section you write and every revision you make MUST match the writing style above.
The example excerpts show exactly how the author writes — match their rhythm, vocabulary, and tone precisely.
Do not use generic AI writing patterns. Write as this specific author writes."""

        initial_message = f"""I'm writing a cryptocurrency research article titled "{title}".

## Article Outline
{outline}

## Research Summary
{research_summary}

I'll ask you to write each section one at a time. For each section I'll provide the outline details and relevant source materials. Write only the requested section — not the entire article.

Please confirm you're ready to begin and briefly acknowledge the writing style you'll be matching."""

        self.conversation_history = [{"role": "user", "content": initial_message}]

        # Prime the conversation — this acknowledgment locks in the style context
        ack = self.anthropic_client.generate_with_history(
            messages=self.conversation_history,
            system_prompt=self.system_prompt,
            max_tokens=200,
            model_override=CLAUDE_QUALITY_MODEL
        )
        self.conversation_history.append({"role": "assistant", "content": ack})
        logger.info(f"Article conversation initialized for: {title}")

        with open(self.article_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")

        return self.article_file

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def write_section(self, section_info: dict, relevant_sources: dict) -> str:
        """
        Write a section using the ongoing conversation thread.
        The model has full context of all prior sections when writing.

        Args:
            section_info: dict with 'title' and 'content' (outline for this section)
            relevant_sources: dict of sources organized by priority tier

        Returns:
            str: Generated section content (Markdown)
        """
        sources_text = self._format_sources(relevant_sources)

        user_message = f"""Please write the "{section_info['title']}" section now.

## Section Outline
{section_info['content']}

## Relevant Sources for This Section
{sources_text}

Write the section in Markdown, starting with ## {section_info['title']}
Write only this section. Do not write other sections."""

        self.conversation_history.append({"role": "user", "content": user_message})

        logger.info(f"Generating section: {section_info['title']}")
        start = time.time()

        section_content = self.anthropic_client.generate_with_history(
            messages=self.conversation_history,
            system_prompt=self.system_prompt,
            max_tokens=4000,
            model_override=CLAUDE_QUALITY_MODEL
        )

        self.conversation_history.append({"role": "assistant", "content": section_content})
        logger.info(f"Section '{section_info['title']}' generated in {time.time() - start:.2f}s")

        # Append to file
        with open(self.article_file, 'a', encoding='utf-8') as f:
            f.write(section_content + "\n\n")

        # Track for revision reconstruction
        self.accepted_sections.append({'title': section_info['title'], 'content': section_content})

        return section_content

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def revise_section(self, section_title: str, revision_instructions: str,
                       current_content: str) -> str:
        """
        Revise a section within the ongoing conversation.
        The model sees the entire article written so far when rewriting.

        Args:
            section_title: Title of the section to revise
            revision_instructions: User's feedback
            current_content: The current version of the section

        Returns:
            str: Revised section content (Markdown)
        """
        user_message = f"""Please revise the "{section_title}" section based on this feedback:

{revision_instructions}

Current version of this section:
{current_content}

Rewrite the entire section incorporating the feedback. Start with ## {section_title}
Maintain the same writing style and voice. Do not change other sections."""

        self.conversation_history.append({"role": "user", "content": user_message})

        logger.info(f"Revising section: {section_title}")
        start = time.time()

        revised = self.anthropic_client.generate_with_history(
            messages=self.conversation_history,
            system_prompt=self.system_prompt,
            max_tokens=4000,
            model_override=CLAUDE_QUALITY_MODEL
        )

        self.conversation_history.append({"role": "assistant", "content": revised})
        logger.info(f"Revision of '{section_title}' generated in {time.time() - start:.2f}s")

        return revised

    def accept_revision(self, section_title: str, revised_content: str):
        """
        Accept a revision and rewrite the article file from the accepted sections list.
        No regex needed — sections are tracked as discrete objects.

        Args:
            section_title: Title of the section that was revised
            revised_content: The accepted revised content
        """
        for section in self.accepted_sections:
            if section['title'] == section_title:
                section['content'] = revised_content
                break

        # Rewrite entire file from accepted sections list
        with open(self.article_file, 'w', encoding='utf-8') as f:
            f.write(f"# {self.article_title}\n\n")
            for section in self.accepted_sections:
                f.write(section['content'] + "\n\n")

        logger.info(f"Article file updated with revision to: {section_title}")

    def retrieve_relevant_sources(self, section_title: str, article_results: list,
                                   video_results: list, user_content: list,
                                   user_content_only: bool = False) -> dict:
        """Gather research materials relevant to a specific section."""
        keywords = [w for w in section_title.lower().split() if len(w) > 3]
        sources = {
            "User Content": list(user_content),
            "YouTube": [],
            "High Relevance Articles": [],
            "Medium Relevance Articles": []
        }

        if not user_content_only:
            for video in video_results:
                title = video.get('title', '').lower()
                key_points = ' '.join(video.get('key_points', [])).lower()
                if video.get('relevance_score') == 'High' or any(k in title or k in key_points for k in keywords):
                    sources["YouTube"].append({
                        'title': video.get('title', 'Untitled Video'),
                        'text': (
                            f"Video by {video.get('channel', 'Unknown')} ({video.get('date', 'Unknown date')})\n"
                            f"Key points: {' '.join(video.get('key_points', []))}\n"
                            f"URL: {video.get('url', '')}"
                        ),
                        'relevance': video.get('relevance_score', 'Unknown')
                    })

            for article in article_results:
                title = article.get('title', '').lower()
                text = article.get('text', '').lower()
                if article.get('relevance_score') == 'High' or any(k in title or k in text for k in keywords):
                    sources["High Relevance Articles"].append({
                        'title': article.get('title', 'Untitled'),
                        'text': article.get('text', ''),
                        'url': article.get('url', ''),
                        'relevance': article.get('relevance_score', 'Unknown')
                    })
                elif article.get('relevance_score') == 'Medium':
                    sources["Medium Relevance Articles"].append({
                        'title': article.get('title', 'Untitled'),
                        'text': article.get('text', ''),
                        'url': article.get('url', ''),
                        'relevance': article.get('relevance_score', 'Unknown')
                    })

        total = sum(len(v) for v in sources.values())
        logger.info(f"Found {total} relevant sources for section '{section_title}'")
        return sources

    def read_current_article(self) -> str:
        """Read the current state of the article file."""
        if not self.article_file or not os.path.exists(self.article_file):
            return ""
        with open(self.article_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _format_sources(self, sources: dict) -> str:
        """Format sources dict into a prompt-ready string."""
        if not sources:
            return "No specific sources for this section."
        text = ""
        for priority, source_list in sources.items():
            if source_list:
                text += f"\n### {priority}\n"
                for i, source in enumerate(source_list):
                    text += f"\n**Source {i+1}: {source.get('title', 'Untitled')}**\n"
                    text += source.get('text', '') + "\n"
                    if source.get('url'):
                        text += f"URL: {source.get('url')}\n"
        return text or "No specific sources for this section."
