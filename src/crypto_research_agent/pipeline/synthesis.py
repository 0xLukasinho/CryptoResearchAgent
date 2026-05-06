from pathlib import Path

from ..config import OUTLINE_FILENAME, RESEARCH_RESULTS_FILENAME
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SynthesisStage:
    def __init__(self, *, ctx, summarizer, outline_writer, outline_review):
        self._ctx = ctx
        self._summarizer = summarizer
        self._outline_writer = outline_writer
        self._outline_review = outline_review

    def save_summary(self, *, articles, videos) -> Path:
        text = self._summarizer.summarize(
            articles=articles, videos=videos,
            query=self._ctx.query, thesis=self._ctx.thesis,
        )
        out = Path(self._ctx.output_dir) / RESEARCH_RESULTS_FILENAME
        out.write_text(text, encoding="utf-8")
        logger.info("Research summary saved: %s", out)
        return out

    def synthesize(self, *, articles, videos, user_content, user_content_only: bool) -> str:
        if articles or videos:
            self.save_summary(articles=articles, videos=videos)
        outline = self._outline_writer.generate(
            articles=articles, videos=videos, user_content=user_content,
            query=self._ctx.query, thesis=self._ctx.thesis,
            user_content_only=user_content_only,
        )
        outline_path = Path(self._ctx.output_dir) / OUTLINE_FILENAME
        outline_path.write_text(outline, encoding="utf-8")
        return self._outline_review.run(
            outline_path=outline_path,
            outline_writer=self._outline_writer,
            articles=articles, videos=videos, user_content=user_content,
            query=self._ctx.query, thesis=self._ctx.thesis,
        )
