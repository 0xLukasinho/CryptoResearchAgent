from .prompts import parse_feedback_input, render_review_prompt
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SectionReview:
    def run(self, *, section_title: str, section_content: str,
            article_writer, sources) -> str:
        print(render_review_prompt(item_label=f"Section '{section_title}'",
                                    file_path=str(article_writer.article_path)))
        current = section_content
        while True:
            raw = input("> ")
            fb = parse_feedback_input(raw)
            if fb["action"] == "accept":
                return current
            if fb["action"] == "edited":
                logger.info("Manual edits accepted")
                return current
            if fb["action"] == "revise":
                revised = article_writer.revise_section(
                    section_title, instructions=fb["details"], current_content=current,
                )
                article_writer.accept_revision(section_title, revised)
                current = revised
                print(render_review_prompt(
                    item_label=f"Revised section '{section_title}'",
                    file_path=str(article_writer.article_path),
                ))
                continue
            print("Invalid input. Use [1] accept / [2] revise <instructions> / [3] edited")
