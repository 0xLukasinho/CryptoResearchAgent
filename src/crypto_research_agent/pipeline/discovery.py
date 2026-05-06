from ..agents.analyzer import AnalyzedItem
from ..agents.coordinator import SearchPlan
from ..utils.filters import contains_all_required_terms
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DiscoveryStage:
    def __init__(self, *, ctx, substack_service, youtube_service, analyzer):
        self._ctx = ctx
        self._substack = substack_service
        self._youtube = youtube_service
        self._analyzer = analyzer

    def run(self, plan: SearchPlan) -> tuple[list[AnalyzedItem], list[AnalyzedItem]]:
        articles = self._discover_substack(plan) if self._ctx.sources.substack else []
        videos = self._discover_youtube(plan) if self._ctx.sources.youtube else []
        return articles, videos

    def _discover_substack(self, plan: SearchPlan) -> list[AnalyzedItem]:
        raw = list(self._substack.discover(
            max_age_days=self._ctx.max_age_days, test_mode=self._ctx.test_mode,
        ))
        logger.info("Substack: retrieved %d articles", len(raw))
        prefiltered = [
            a for a in raw if contains_all_required_terms(
                {"title": a.title, "text": a.text}, plan.required_terms,
            )
        ]
        logger.info("Substack: %d passed required-term filter", len(prefiltered))
        return [
            r for r in self._analyzer.analyze_batch(
                items=prefiltered, main_topic=plan.main_topic,
                thesis=self._ctx.thesis, test_mode=self._ctx.test_mode,
            ) if r.relevance_score in ("High", "Medium")
        ]

    def _discover_youtube(self, plan: SearchPlan) -> list[AnalyzedItem]:
        videos = self._youtube.search(
            query=self._ctx.query, required_terms=plan.required_terms,
            max_results=5, max_age_days=self._ctx.max_age_days,
            test_mode=self._ctx.test_mode, output_dir=self._ctx.output_dir,
        )
        logger.info("YouTube: %d videos with transcripts", len(videos))
        return [
            r for r in self._analyzer.analyze_batch(
                items=videos, main_topic=plan.main_topic,
                thesis=self._ctx.thesis, test_mode=self._ctx.test_mode,
            ) if r.relevance_score in ("High", "Medium")
        ]
