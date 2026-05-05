from ..utils.logger import get_logger

logger = get_logger(__name__)


_SHARED_GUIDELINES = """You are an expert cryptocurrency researcher creating outlines.

Guidelines:
- Numbered main sections (## 1. Title, ## 2. Title)
- Numbered subsections (### 1.1 Title)
- Bullet points within subsections
- Source citations in [Title] brackets
- Number of sections fits the content; do NOT default to 5

Format:
# Research Article Outline: [Title]
## 1. Introduction
- Hook
- Thesis
## N. Conclusion
- Implications
"""


class OutlineWriter:
    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def generate(self, *, articles, videos, user_content, query: str,
                 thesis: str | None, user_content_only: bool) -> str:
        sys_prompt = self._build_system_prompt(
            has_user_content=bool(user_content),
            user_content_only=user_content_only,
        )
        user_prompt = self._build_user_prompt(
            articles, videos, user_content, query, thesis, current_outline=None,
            instructions=None,
        )
        return self._backend.complete(prompt=user_prompt, model=self._model,
                                       system_prompt=sys_prompt).text

    def revise(self, *, current: str, instructions: str,
               articles, videos, user_content, query: str,
               thesis: str | None) -> str:
        sys_prompt = self._build_system_prompt(has_user_content=bool(user_content),
                                                 user_content_only=False,
                                                 is_revision=True)
        user_prompt = self._build_user_prompt(
            articles, videos, user_content, query, thesis,
            current_outline=current, instructions=instructions,
        )
        return self._backend.complete(prompt=user_prompt, model=self._model,
                                       system_prompt=sys_prompt).text

    def _build_system_prompt(self, *, has_user_content: bool,
                              user_content_only: bool,
                              is_revision: bool = False) -> str:
        prompt = _SHARED_GUIDELINES
        if user_content_only:
            prompt += "\nNo Substack/YouTube content found. Use ONLY user-provided content."
        if has_user_content:
            prompt += "\nIntegrate user-provided content thoroughly. Cite [User Content Title]."
        if is_revision:
            prompt += "\nAddress the user's revision instructions while preserving format."
        return prompt

    def _build_user_prompt(self, articles, videos, user_content, query,
                           thesis, current_outline, instructions) -> str:
        parts = [f"# Research Query\n{query}"]
        if thesis:
            parts.append(f"# Thesis Direction\n{thesis}")
        if current_outline:
            parts.append(f"# Current Outline\n{current_outline}")
        if instructions:
            parts.append(f"# Revision Instructions\n{instructions}")
        parts.append(f"# Research Sources\n{self._format_sources(articles, videos)}")
        if user_content:
            parts.append(f"# User Content\n{self._format_user_content(user_content)}")
        return "\n\n".join(parts)

    @staticmethod
    def _format_sources(articles, videos) -> str:
        out = ""
        if videos:
            out += f"## Videos ({len(videos)})\n"
            for i, v in enumerate(videos, 1):
                out += f"{i}. **{v.title}** by {getattr(v, 'channel', '?')}\n"
        if articles:
            out += f"\n## Articles ({len(articles)})\n"
            for i, a in enumerate(articles, 1):
                out += f"{i}. **{a.title}** by {a.author}\n"
                for ins in (a.key_insights or [])[:3]:
                    out += f"   - {ins}\n"
        return out or "No sources."

    @staticmethod
    def _format_user_content(user_content) -> str:
        out = ""
        for i, c in enumerate(user_content, 1):
            out += f"### User Content {i}: {c.title} ({c.file_type})\n"
            for ins in (c.key_insights or [])[:5]:
                out += f"- {ins}\n"
        return out
