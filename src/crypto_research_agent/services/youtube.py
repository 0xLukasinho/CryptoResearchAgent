from dataclasses import dataclass, field, replace
from typing import Literal


RelevanceScore = Literal["High", "Medium", "Low"]


@dataclass
class Video:
    title: str
    channel: str
    date: str
    description: str
    video_id: str
    url: str
    transcript: str | None = None
    relevance_score: RelevanceScore = "Medium"
    relevance_value: float = 0.0
    interview_score: int = 0
    key_points: list[str] = field(default_factory=list)


_INTERVIEW_KEYWORDS = ("founder", "interview", "ceo", "creator", "with", "exclusive")


def filter_by_required_terms(videos: list[Video], required_terms: list[str]) -> list[Video]:
    if not required_terms:
        return list(videos)
    terms = [t.lower() for t in required_terms if t]
    out: list[Video] = []
    for v in videos:
        title_l = v.title.lower()
        content_l = f"{title_l} {v.description.lower()}"
        if all(t in content_l for t in terms) and any(t in title_l for t in terms):
            out.append(v)
    return out


def score_relevance(video: Video, *, query: str) -> Video:
    title_l = video.title.lower()
    desc_l = video.description.lower()
    query_words = set(query.lower().split())
    title_words = set(title_l.split())
    desc_words = set(desc_l.split())

    if not query_words:
        return video

    title_match = (len(query_words & title_words) / len(query_words)) * 2.0
    desc_match = len(query_words & desc_words) / len(query_words)
    base = title_match + desc_match
    if query.lower() in title_l:
        base += 3.0

    has_interview = any(kw in title_l for kw in _INTERVIEW_KEYWORDS)
    if has_interview and title_match > 0:
        score = base * 3.5
        return replace(video, relevance_score="High", relevance_value=score, interview_score=15)
    if has_interview:
        return replace(video, relevance_score="High", relevance_value=base * 3.0, interview_score=10)
    if title_match > 1.0:
        return replace(video, relevance_score="Medium", relevance_value=base * 1.5, interview_score=5)
    return replace(video, relevance_score="Medium", relevance_value=base, interview_score=0)
