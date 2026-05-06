import json
from pathlib import Path
from typing import Callable

from ..agents.article_writer import SectionInfo
from ..config import ARTICLE_FILENAME, STYLE_CARD_FILENAME
from ..utils.logger import get_logger

logger = get_logger(__name__)


def relevant_sources_for(section_title: str, articles, videos, user_content,
                          *, user_content_only: bool) -> dict:
    keywords = [w for w in section_title.lower().split() if len(w) > 3]
    out: dict[str, list] = {
        "User Content": [
            {"title": c.title, "text": c.text, "url": c.url}
            for c in (user_content or [])
        ],
        "YouTube": [], "High Relevance Articles": [], "Medium Relevance Articles": [],
    }
    if user_content_only:
        return out
    for v in videos:
        title = v.title.lower()
        if v.relevance_score == "High" or any(k in title for k in keywords):
            out["YouTube"].append({"title": v.title, "text": " ".join(v.key_insights), "url": v.url})
    for a in articles:
        title = a.title.lower()
        text = a.text.lower()
        if a.relevance_score == "High" or any(k in title or k in text for k in keywords):
            out["High Relevance Articles"].append({"title": a.title, "text": a.text, "url": a.url})
        elif a.relevance_score == "Medium":
            out["Medium Relevance Articles"].append({"title": a.title, "text": a.text, "url": a.url})
    return out


class WritingStage:
    def __init__(self, *, ctx, style_learner,
                 article_writer_factory: Callable, section_review):
        self._ctx = ctx
        self._style_learner = style_learner
        self._article_writer_factory = article_writer_factory
        self._section_review = section_review

    def write(self, *, outline: str, sections: list[dict],
              articles, videos, user_content, research_summary: str,
              user_content_only: bool) -> Path:
        materials = self._style_learner.get_raw_materials()
        card = self._style_learner.generate_style_card(materials)
        card_path = Path(self._ctx.output_dir) / STYLE_CARD_FILENAME
        card_path.write_text(json.dumps(card.to_dict(), indent=2), encoding="utf-8")
        logger.info("Style card saved: %s", card_path)

        article_path = Path(self._ctx.output_dir) / ARTICLE_FILENAME
        writer = self._article_writer_factory(card=card, output_path=article_path)
        writer.start_article(title=self._ctx.query, outline=outline,
                              research_summary=research_summary)

        for section in sections:
            sources = relevant_sources_for(
                section["title"], articles, videos, user_content,
                user_content_only=user_content_only,
            )
            content = writer.write_section(
                SectionInfo(title=section["title"], content=section["content"]),
                sources,
            )
            self._section_review.run(
                section_title=section["title"], section_content=content,
                article_writer=writer, sources=sources,
            )
        return article_path
