# agents/feedback_processor.py
import sys
sys.path.append('..')
from utils.logger import get_logger

logger = get_logger(__name__)


class FeedbackProcessor:
    """
    Manages user feedback on article sections and coordinates revisions.
    Sections are tracked as discrete conversation turns in ArticleWriterAgent —
    no regex boundary detection needed.
    """

    def present_section(self, section_title: str, article_file: str):
        """Notify the user that a section is ready for review."""
        logger.info(f"Section '{section_title}' ready for review")
        print(f"\n[FEEDBACK] Section '{section_title}' has been written.")
        print(f"Please review it in: {article_file}")
        print("\nOptions:")
        print("  1. Type 'accept' to proceed to the next section")
        print("  2. Type 'revise [instructions]' to have the AI rewrite the section")
        print("  3. Edit the file directly and type 'edited' to confirm your changes")

    def prompt_for_feedback(self) -> dict:
        """Ask user if section is acceptable or needs revision."""
        while True:
            user_input = input("\n> ").strip()
            if user_input.lower() == 'accept':
                return {'action': 'accept', 'details': None}
            elif user_input.lower() == 'edited':
                return {'action': 'edited', 'details': None}
            elif user_input.lower().startswith('revise '):
                instructions = user_input[7:].strip()
                if not instructions:
                    print("Please provide revision instructions after 'revise'.")
                    continue
                return {'action': 'revise', 'details': instructions}
            else:
                print("Invalid input. Please type 'accept', 'edited', or 'revise [instructions]'.")

    def check_for_file_edits(self, article_file: str, last_known_content: str):
        """Check if the user has made manual edits to the article file."""
        with open(article_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        return current_content != last_known_content, current_content

    def process_revision_request(self, feedback: dict, article_writer, section_info: dict,
                                  research_data: dict, style_materials: dict, fact_checker) -> str:
        """
        Process a revision request by delegating to article_writer.revise_section().
        The writer's conversation history provides full style and article context automatically.

        Args:
            feedback: dict with 'action' and 'details' (revision instructions)
            article_writer: ArticleWriterAgent instance holding conversation history
            section_info: dict with 'title', 'content', 'current_content'
            research_data: used only for fact-checking after revision
            style_materials: unused — style is embedded in the conversation system prompt
            fact_checker: FactCheckerAgent instance

        Returns:
            str: Revised section content
        """
        revision_instructions = feedback.get('details') or ''
        current_content = section_info.get('current_content', '')
        section_title = section_info['title']

        logger.info(f"Generating revision for section '{section_title}'")
        revised_content = article_writer.revise_section(
            section_title=section_title,
            revision_instructions=revision_instructions,
            current_content=current_content
        )

        logger.info("Fact checking revised content")
        check_results = fact_checker.check_section(
            section_content=revised_content,
            sources=research_data
        )

        if not check_results.get('accurate', False):
            logger.info("Applying factual corrections to revised content")
            revised_content = fact_checker.suggest_corrections(
                section_content=revised_content,
                check_results=check_results
            )

        return revised_content
