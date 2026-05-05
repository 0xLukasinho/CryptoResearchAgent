import re
import datetime
from pathlib import Path


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SLUG_DROP_CHARS = re.compile(r"['’]")  # apostrophes — drop without replacement


def sanitize_query_slug(query: str, *, max_length: int = 60) -> str:
    s = (query or "").lower()
    s = _SLUG_DROP_CHARS.sub("", s)
    s = _SLUG_NON_ALNUM.sub("_", s).strip("_")
    if not s:
        return "query"
    return s[:max_length].rstrip("_") or "query"


def build_output_dir(parent: Path, query: str) -> Path:
    """Return a unique output directory path of form <parent>/<slug>_YYYY-MM-DD_HHMMSS[_<n>]."""
    slug = sanitize_query_slug(query)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = parent / f"{slug}_{timestamp}"
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = parent / f"{slug}_{timestamp}_{counter}"
        if not candidate.exists():
            return candidate
        counter += 1
