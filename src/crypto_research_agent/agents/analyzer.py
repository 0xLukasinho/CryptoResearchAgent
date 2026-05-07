from dataclasses import dataclass, field
from typing import Literal

from ..llm.errors import AuthMissing, QuotaExceeded
from ..services.substack import Article
from ..services.youtube import Video
from ..utils.logger import get_logger
from ..utils.token_utils import truncate_to_token_limit

logger = get_logger(__name__)

RelevanceScore = Literal["High", "Medium", "Low", "Error"]


@dataclass
class AnalyzedItem:
    title: str
    author: str
    date: str
    url: str
    text: str
    relevance_score: RelevanceScore
    key_insights: list[str] = field(default_factory=list)
    mentioned_projects: list[str] = field(default_factory=list)
    thesis_alignment: str = "Not Applicable"
    relevance_explanation: str = ""

    def to_legacy_dict(self) -> dict:
        return {
            "title": self.title, "author": self.author, "date": self.date, "url": self.url,
            "text": self.text, "relevance_score": self.relevance_score,
            "key_insights": self.key_insights, "mentioned_projects": self.mentioned_projects,
            "thesis_alignment": self.thesis_alignment,
            "relevance_explanation": self.relevance_explanation,
        }


class Analyzer:
    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def analyze(self, item: Article | Video,
                *, main_topic: str, thesis: str | None) -> AnalyzedItem | None:
        text_sample = truncate_to_token_limit(self._extract_text(item), self._model, 1500)
        thesis_info = f"\nThesis Direction: {thesis}" if thesis else ""
        prompt = f"""Analyze this crypto content for relevance.

Search Topic: {main_topic}{thesis_info}

Content:
Title: {item.title}
{text_sample}

CRITICAL: First check if the content is in English.
- If NOT in English, return: {{"non_english": true, "language_detected": "..."}}
- If in English, return JSON with: relevance_score (High/Medium/Low),
  relevance_explanation, key_insights (list), mentioned_projects (list),
  thesis_alignment (High/Medium/Low/Not Applicable), thesis_alignment_explanation."""

        # Per-article fault isolation: a single failed/timed-out LLM call must
        # not abort the batch. Quota/Auth errors still bubble up so the router
        # can switch to fallback or surface a config issue.
        try:
            result = self._backend.complete_json(
                prompt=prompt, model=self._model,
                system_prompt="You evaluate crypto content. Respond with valid JSON only.",
            )
        except (QuotaExceeded, AuthMissing):
            raise
        except Exception as e:
            logger.warning("Analyzer LLM call failed for %r; skipping. (%s: %s)",
                           item.title, type(e).__name__, e)
            return AnalyzedItem(
                title=item.title, author=getattr(item, "author", getattr(item, "channel", "")),
                date=item.date, url=item.url, text=self._extract_text(item),
                relevance_score="Error",
                relevance_explanation=f"LLM call failed: {type(e).__name__}",
            )
        if not result:
            return AnalyzedItem(
                title=item.title, author=getattr(item, "author", getattr(item, "channel", "")),
                date=item.date, url=item.url, text=self._extract_text(item),
                relevance_score="Error", relevance_explanation="LLM returned empty response",
            )
        if result.get("non_english"):
            logger.info("Discarding non-English: %s (%s)",
                        item.title, result.get("language_detected", "?"))
            return None
        score = result.get("relevance_score", "Low")
        if thesis and result.get("thesis_alignment") not in ("Not Applicable", "Error", None):
            score = result["thesis_alignment"]
        return AnalyzedItem(
            title=item.title,
            author=getattr(item, "author", getattr(item, "channel", "")),
            date=item.date, url=item.url, text=self._extract_text(item),
            relevance_score=score,
            key_insights=result.get("key_insights", []),
            mentioned_projects=result.get("mentioned_projects", []),
            thesis_alignment=result.get("thesis_alignment", "Not Applicable"),
            relevance_explanation=result.get("relevance_explanation", ""),
        )

    def analyze_batch(self, items, *, main_topic, thesis, test_mode=False) -> list[AnalyzedItem]:
        analyzed: list[AnalyzedItem] = []
        relevant_count = 0
        for i, item in enumerate(items):
            logger.info("Analyzing %d/%d: %s", i + 1, len(items), item.title)
            r = self.analyze(item, main_topic=main_topic, thesis=thesis)
            if r is None:
                logger.info("  -> non-English, dropped")
                continue
            logger.info("  -> relevance=%s thesis=%s insights=%d",
                        r.relevance_score, r.thesis_alignment, len(r.key_insights))
            analyzed.append(r)
            if test_mode and r.relevance_score in ("High", "Medium"):
                relevant_count += 1
                if relevant_count >= 2:
                    logger.info("Test mode: %d relevant items found, stopping", relevant_count)
                    break
        return analyzed

    def extract_insights(self, content: str) -> tuple[list[str], list[str]]:
        """Used by UserContentService — returns (key_insights, mentioned_projects)."""
        sample = truncate_to_token_limit(content, self._model, 1500)
        prompt = f"""Extract insights from this user-provided content.
{sample}

Return JSON with: key_insights (list of strings), mentioned_projects (list of strings)."""
        result = self._backend.complete_json(
            prompt=prompt, model=self._model,
            system_prompt="Respond with valid JSON only.",
        )
        return (
            result.get("key_insights", []),
            result.get("mentioned_projects", []),
        )

    @staticmethod
    def _extract_text(item) -> str:
        if isinstance(item, Article):
            return item.text or ""
        if isinstance(item, Video):
            return f"{item.description}\n\n{item.transcript or ''}"
        return ""
