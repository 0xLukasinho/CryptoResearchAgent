from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SectionInfo:
    title: str
    content: str


@dataclass
class _AcceptedSection:
    title: str
    content: str


class ArticleWriter:
    """Writes article sections via a stateful Conversation. Maintains an in-memory
    list of accepted sections so the article file can be rewritten cleanly on revision."""

    def __init__(self, conversation, *, output_path: Path):
        self._conv = conversation
        self._article_path = Path(output_path)
        self._title = ""
        self._accepted: list[_AcceptedSection] = []

    @property
    def accepted_sections(self) -> list[_AcceptedSection]:
        return list(self._accepted)

    @property
    def article_path(self) -> Path:
        return self._article_path

    def start_article(self, *, title: str, outline: str, research_summary: str) -> Path:
        self._title = title
        priming = f"""I'm writing a cryptocurrency research article titled "{title}".

## Article Outline
{outline}

## Research Summary
{research_summary}

I'll ask you to write each section one at a time. For each section I'll provide the outline details and relevant source materials. Write only the requested section — not the entire article.

Please confirm you're ready to begin and briefly acknowledge the writing style you'll be matching."""
        self._conv.send(priming)
        self._article_path.parent.mkdir(parents=True, exist_ok=True)
        self._article_path.write_text(f"# {title}\n\n", encoding="utf-8")
        return self._article_path

    def write_section(self, section: SectionInfo, sources: dict[str, Any]) -> str:
        prompt = self._build_section_prompt(section, sources)
        content = self._conv.send(prompt)
        self._accepted.append(_AcceptedSection(title=section.title, content=content))
        with self._article_path.open("a", encoding="utf-8") as fh:
            fh.write(content + "\n\n")
        return content

    def revise_section(self, title: str, *, instructions: str, current_content: str) -> str:
        prompt = f"""Please revise the "{title}" section based on this feedback:

{instructions}

Current version of this section:
{current_content}

Rewrite the entire section incorporating the feedback. Start with ## {title}
Maintain the same writing style and voice. Do not change other sections."""
        return self._conv.send(prompt)

    def accept_revision(self, title: str, revised_content: str) -> None:
        for s in self._accepted:
            if s.title == title:
                s.content = revised_content
                break
        else:
            self._accepted.append(_AcceptedSection(title=title, content=revised_content))
        with self._article_path.open("w", encoding="utf-8") as fh:
            fh.write(f"# {self._title}\n\n")
            for s in self._accepted:
                fh.write(s.content + "\n\n")

    def read_current_article(self) -> str:
        return self._article_path.read_text(encoding="utf-8") if self._article_path.exists() else ""

    @staticmethod
    def _build_section_prompt(section: SectionInfo, sources: dict[str, Any]) -> str:
        parts = [
            f'Please write the "{section.title}" section now.',
            "",
            "## Section Outline",
            section.content,
            "",
            "## Relevant Sources",
            ArticleWriter._format_sources(sources) or "No specific sources for this section.",
            "",
            f"Write the section in Markdown, starting with ## {section.title}",
            "Write only this section. Do not write other sections.",
        ]
        return "\n".join(parts)

    @staticmethod
    def _format_sources(sources: dict[str, Any]) -> str:
        if not sources:
            return ""
        lines: list[str] = []
        for tier, items in sources.items():
            if not items:
                continue
            lines.append(f"\n### {tier}")
            for i, src in enumerate(items, 1):
                lines.append(f"\n**Source {i}: {src.get('title', 'Untitled')}**")
                lines.append(src.get("text", ""))
                if src.get("url"):
                    lines.append(f"URL: {src['url']}")
        return "\n".join(lines)
