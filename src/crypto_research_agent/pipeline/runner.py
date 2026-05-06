from dataclasses import dataclass
from pathlib import Path

from ..agents.analyzer import Analyzer
from ..agents.article_writer import ArticleWriter
from ..agents.coordinator import Coordinator
from ..agents.outline_writer import OutlineWriter
from ..agents.style_learner import StyleLearner
from ..agents.summarizer import Summarizer
from ..config import (
    ANTHROPIC_API_KEY, CLOUDCONVERT_API_KEY, SUBSTACK_CSV, SUPADATA_API_KEY,
    WRITING_INSTRUCTIONS_FILE, WRITING_SAMPLES_DIR, YOUTUBE_API_KEY, YOUTUBE_CSV,
    get_model_for_role,
)
from ..feedback.outline_review import OutlineReview
from ..feedback.prompts import safe_input
from ..feedback.section_review import SectionReview
from ..llm.api_backend import AnthropicAPIBackend
from ..llm.claude_code import ClaudeCodeBackend
from ..llm.conversation import Conversation
from ..llm.router import LLMRouter
from ..services.docx_export import DocxExporter
from ..services.substack import SubstackService
from ..services.user_content import UserContentService
from ..services.youtube import YouTubeService
from ..utils.logger import get_logger
from ..utils.outline_parser import parse_sections
from .discovery import DiscoveryStage
from .synthesis import SynthesisStage
from .writing import WritingStage

logger = get_logger(__name__)


@dataclass(frozen=True)
class SourceConfig:
    substack: bool
    youtube: bool


@dataclass
class RunContext:
    query: str
    thesis: str | None
    output_dir: Path
    test_mode: bool
    search_mode: bool
    sources: SourceConfig
    max_age_days: int | None
    parallel: int = 1


class PipelineRunner:
    """Top-level orchestrator. Composes pipeline stages, owns LLMRouter."""

    def __init__(self):
        from .stats import RunStats
        self._stats = RunStats()

    def run_with_context(self, ctx: RunContext) -> None:
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        router = self._build_router()
        coordinator = self._build_coordinator(ctx, router)
        plan = coordinator.plan(ctx.query)
        logger.info("Plan: %s", plan)

        discovery = self._build_discovery(ctx, router)
        articles, videos = discovery.run(plan)

        if not articles and not videos:
            if not self._user_wants_to_continue_with_user_content():
                return

        if ctx.search_mode:
            self._build_synthesis(ctx, router).save_summary(articles=articles, videos=videos)
            return

        user_content_svc = self._build_user_content(ctx, router)
        user_content = (
            user_content_svc.collect(ctx.output_dir / "user_content")
            if self._user_wants_to_add_content() else []
        )

        synthesis = self._build_synthesis(ctx, router)
        outline = synthesis.synthesize(
            articles=articles, videos=videos, user_content=user_content,
            user_content_only=not (articles or videos),
        )

        writing = self._build_writing(ctx, router, plan_main_topic=plan.main_topic,
                                       research_summary="")
        writing.write(
            outline=outline, sections=parse_sections(outline),
            articles=articles, videos=videos, user_content=user_content,
            research_summary="",
            user_content_only=not (articles or videos),
        )

        exporter = self._build_docx_export(ctx)
        if exporter is not None:
            exporter.convert_markdown_to_docx(ctx.output_dir / "article.md")
        self._print_run_summary(ctx, router)

    # ---- Builder methods (extracted for test isolation) ----

    def _build_router(self) -> LLMRouter:
        primary = ClaudeCodeBackend()
        router = LLMRouter(primary=primary)
        router.set_fallback_factory(self._fallback_factory)
        router.on_quota_exhausted = self._prompt_quota_exhausted
        return router

    def _fallback_factory(self, choice: str):
        return AnthropicAPIBackend(api_key=ANTHROPIC_API_KEY)

    @staticmethod
    def _prompt_quota_exhausted() -> str:
        print("\n[QUOTA] Your Claude Max subscription quota is exhausted.")
        print("        Continue using the Anthropic API (pay-per-token)?")
        print("\n  [1] Continue with Opus")
        print("  [2] Continue with Sonnet")
        print("  [3] Abort\n")
        while True:
            # EOF (non-interactive stdin) → abort to avoid an infinite retry loop
            choice = safe_input("> ", on_eof="3").strip()
            if choice == "1":
                return "opus"
            if choice == "2":
                return "sonnet"
            if choice == "3":
                return "abort"
            print("Invalid. Pick 1/2/3.")

    def _build_coordinator(self, ctx, router):
        return Coordinator(router, model=get_model_for_role("fast", test_mode=ctx.test_mode))

    def _build_discovery(self, ctx, router):
        analyzer = Analyzer(router, model=get_model_for_role("fast", test_mode=ctx.test_mode))
        return DiscoveryStage(
            ctx=ctx,
            substack_service=SubstackService(SUBSTACK_CSV),
            youtube_service=YouTubeService(api_key=YOUTUBE_API_KEY,
                                             supadata_key=SUPADATA_API_KEY,
                                             channels_csv=YOUTUBE_CSV),
            analyzer=analyzer,
        )

    def _build_synthesis(self, ctx, router):
        return SynthesisStage(
            ctx=ctx,
            summarizer=Summarizer(router,
                                   model=get_model_for_role("fast", test_mode=ctx.test_mode)),
            outline_writer=OutlineWriter(router,
                                          model=get_model_for_role("premium",
                                                                     test_mode=ctx.test_mode)),
            outline_review=OutlineReview(),
        )

    def _build_writing(self, ctx, router, *, plan_main_topic, research_summary):
        style_learner = StyleLearner(
            router, model=get_model_for_role("premium", test_mode=ctx.test_mode),
            samples_dir=WRITING_SAMPLES_DIR, instructions_file=WRITING_INSTRUCTIONS_FILE,
        )

        def factory(card, output_path):
            sys_prompt = self._build_writer_system_prompt(card)
            conv = Conversation(router,
                                model=get_model_for_role("premium", test_mode=ctx.test_mode),
                                system_prompt=sys_prompt)
            return ArticleWriter(conv, output_path=output_path)

        return WritingStage(
            ctx=ctx, style_learner=style_learner,
            article_writer_factory=factory, section_review=SectionReview(),
        )

    def _build_user_content(self, ctx, router):
        analyzer = Analyzer(router, model=get_model_for_role("fast", test_mode=ctx.test_mode))
        return UserContentService(analyzer=analyzer)

    def _build_docx_export(self, ctx):
        if not CLOUDCONVERT_API_KEY:
            return None
        return DocxExporter(api_key=CLOUDCONVERT_API_KEY)

    @staticmethod
    def _build_writer_system_prompt(card) -> str:
        return f"""You are a respected crypto analyst writing a research article.

{card.format_for_prompt()}

CRITICAL: Every section you write and every revision you make MUST match the writing style above.
Match the example excerpts' rhythm, vocabulary, and tone precisely.
Do not use generic AI writing patterns."""

    @staticmethod
    def _user_wants_to_continue_with_user_content() -> bool:
        print("\n[NOTICE] No relevant content from Substack or YouTube.")
        print("  [1] Abort   [2] Continue with your own materials")
        return safe_input("> ").strip() == "2"

    @staticmethod
    def _user_wants_to_add_content() -> bool:
        print("\n[USER CONTENT] Add files to user_content/, then 'ready', or 'skip' to continue without.")
        return safe_input("> ").strip().lower() == "ready"

    def _print_run_summary(self, ctx, router):
        print(self._stats.format_summary(query_label=ctx.output_dir.name))
