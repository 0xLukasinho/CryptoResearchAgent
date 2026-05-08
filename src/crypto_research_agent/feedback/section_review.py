from pathlib import Path

from .prompts import parse_feedback_input, render_review_prompt, safe_input
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _extract_section_from_article(article_path: Path, section_title: str) -> str | None:
    """Read the article file and return the full content of `## {section_title}`,
    including its heading line, until the next `## ` heading or EOF.

    Returns None if the file doesn't exist or the section heading isn't found.
    Used by the 'edited' feedback path to capture user manual edits and
    persist them through later accept_revision rewrites.
    """
    if not article_path.exists():
        return None
    text = article_path.read_text(encoding="utf-8")
    target = f"## {section_title}"
    in_section = False
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if stripped == target:
            in_section = True
            out.append(line)
            continue
        if in_section and stripped.startswith("## "):
            break  # next section starts
        if in_section:
            out.append(line)
    if not out:
        return None
    return "".join(out).rstrip()


class SectionReview:
    def run(self, *, section_title: str, section_content: str,
            article_writer, sources) -> str:
        print(render_review_prompt(item_label=f"Section '{section_title}'",
                                    file_path=str(article_writer.article_path)))
        current = section_content
        while True:
            # EOF → accept current section, exit the loop cleanly
            raw = safe_input("> ", on_eof="accept")
            fb = parse_feedback_input(raw)
            if fb["action"] == "accept":
                return current
            if fb["action"] == "edited":
                # User claims they manually edited the file. Re-read this
                # section from disk and persist via accept_revision so that
                # any later accept_revision call (which rewrites the entire
                # file from the in-memory _accepted list) does not silently
                # overwrite the user's edits.
                updated = _extract_section_from_article(
                    Path(article_writer.article_path), section_title
                )
                if updated is not None and updated != current:
                    article_writer.accept_revision(section_title, updated)
                    logger.info("Manual edits to '%s' detected (%d -> %d chars); persisted",
                                section_title, len(current), len(updated))
                    return updated
                logger.info("'%s' marked edited but no changes detected", section_title)
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
