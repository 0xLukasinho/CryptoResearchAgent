import re

from .logger import get_logger

logger = get_logger(__name__)


def _extract_clean_text(article: dict) -> str:
    title = (article.get("title", "") or "").lower()
    text = (article.get("text", "") or "").lower()
    combined = f"{title} {text}"
    combined = re.sub(r"[^\w\s]", " ", combined)
    return re.sub(r"\s+", " ", combined).strip()


def contains_all_required_terms(article: dict | str, required_terms: list[str]) -> bool:
    if not required_terms:
        return True
    haystack = article.lower() if isinstance(article, str) else _extract_clean_text(article)
    clean_terms = [t.lower().strip() for t in required_terms if isinstance(t, str) and t.strip()]
    if not clean_terms:
        return True
    for term in clean_terms:
        if term not in haystack:
            logger.debug("Required term not found: %r", term)
            return False
    return True


_COMMON_ENGLISH_WORDS = frozenset({
    "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was",
    "for", "on", "are", "as", "with", "his", "they", "i", "at", "be", "this",
    "have", "from", "or", "one", "had", "by", "but", "not", "what", "all", "were",
    "we", "when", "your", "can", "said", "there", "use", "an", "each", "which",
    "she", "do", "how", "their", "if", "will", "up", "other", "about", "out",
    "many", "then", "them", "these", "so", "some", "her", "would", "make", "like",
    "him", "into", "time", "has", "two", "more", "no", "way", "could", "people",
    "than", "first", "been", "who", "now", "find", "long", "down", "day", "did",
    "get", "come", "made", "may", "part",
})


def is_likely_english(text: str, threshold: float = 0.005) -> bool:
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    if not words:
        return False
    matches = sum(1 for w in words if w in _COMMON_ENGLISH_WORDS)
    return (matches / len(words)) >= threshold
