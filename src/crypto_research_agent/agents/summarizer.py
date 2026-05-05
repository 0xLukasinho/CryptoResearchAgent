from .analyzer import AnalyzedItem
from ..utils.logger import get_logger

logger = get_logger(__name__)


_SYSTEM_PROMPT = (
    "You are a Summarization Agent that creates markdown-formatted summaries "
    "of crypto research content."
)


class Summarizer:
    """Builds a markdown summary of analyzed articles + videos via LLM."""

    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def summarize(self, *, articles: list[AnalyzedItem], videos: list[AnalyzedItem],
                  query: str, thesis: str | None) -> str:
        relevant_articles = [a for a in articles if a.relevance_score in ("High", "Medium")]
        relevant_videos = [v for v in videos if v.relevance_score in ("High", "Medium")]

        if thesis:
            relevant_articles.sort(key=lambda x: (
                0 if x.relevance_score == "High" else 1,
                0 if x.thesis_alignment == "High" else
                (1 if x.thesis_alignment == "Medium" else 2),
            ))
        else:
            relevant_articles.sort(key=lambda x: 0 if x.relevance_score == "High" else 1)

        relevant_videos.sort(key=lambda x: 0 if x.relevance_score == "High" else 1)

        if not relevant_articles and not relevant_videos:
            return f'# AI Agent Search Results\n\n## Topic: "{query}"\n\nNo relevant content found.'

        prompt = self._build_prompt(relevant_articles, relevant_videos, query, thesis)
        try:
            response = self._backend.complete(
                prompt=prompt, model=self._model, system_prompt=_SYSTEM_PROMPT,
            )
            return response.text
        except Exception as e:
            logger.error("Summarizer LLM error: %s", e)
            return f'# AI Agent Search Results\n\n## Topic: "{query}"\n\nError generating summary: {e}'

    @staticmethod
    def _build_prompt(articles: list[AnalyzedItem], videos: list[AnalyzedItem],
                      query: str, thesis: str | None) -> str:
        content = ""
        if thesis:
            content += f"\nTHESIS DIRECTION: {thesis}\n"
        if articles:
            content += "\nRELEVANT ARTICLES:\n"
            for i, a in enumerate(articles, 1):
                thesis_block = ""
                if thesis:
                    thesis_block = (
                        f"Thesis Alignment: {a.thesis_alignment}\n"
                        f"Thesis Alignment Explanation: {a.relevance_explanation or 'Not provided'}"
                    )
                content += f"""
Article {i}:
Title: {a.title}
Author: {a.author}
Date: {a.date}
URL: {a.url}
Relevance: {a.relevance_score}
Key Insights: {", ".join(a.key_insights)}
{thesis_block}
"""
        if videos:
            content += "\nRELEVANT VIDEOS:\n"
            for i, v in enumerate(videos, 1):
                content += f"""
Video {i}:
Title: {v.title}
Channel: {v.author}
Date: {v.date}
URL: {v.url}
Relevance: {v.relevance_score}
Key Insights: {", ".join(v.key_insights)}
"""

        thesis_instr = ""
        if thesis:
            thesis_instr = (
                "Also include thesis alignment for each article:\n"
                "- **Thesis Alignment:** High/Medium/Low\n"
                "  Brief comment on how the article aligns with the thesis direction.\n"
            )

        return f"""You are the Summarization Agent, specialized in creating concise, informative summaries of crypto content.

Search Query: "{query}"
{f'Thesis Direction: "{thesis}"' if thesis else ''}

Relevant Content:
{content}

Create a markdown-formatted summary with the following structure:

# AI Agent Search Results

## Topic: "{query}"
{f'## Thesis Direction: "{thesis}"' if thesis else ''}

{'### Articles:' if articles else ''}
{'(Include numbered articles with the format below)' if articles else ''}

{'### Videos:' if videos else ''}
{'(Include numbered videos with the format below)' if videos else ''}

For each ARTICLE, use this format:
#### 1. [Article Title](link)
- **Author:** Name, Date
- **Relevance:** High/Medium
{thesis_instr}
- **Summary:** One concise paragraph (5-6 sentences).

---

For each VIDEO, use this format:
#### 1. [Video Title](link)
- **Channel:** Name, Date
- **Relevance:** High/Medium
- **Summary:** One concise paragraph (5-6 sentences).

---

Number items sequentially within each section. Include "---" separator between items.
"""
