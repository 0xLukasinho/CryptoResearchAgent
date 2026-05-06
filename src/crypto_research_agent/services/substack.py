import datetime
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import requests

from ..utils.csv_loader import load_substack_urls
from ..utils.html import html_to_text
from ..utils.logger import get_logger

logger = get_logger(__name__)

_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_HEADERS = {"User-Agent": _USER_AGENT}


@dataclass(frozen=True)
class Article:
    title: str
    author: str
    date: str
    text: str
    url: str


class _Newsletter:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        if not urlparse(self.url).scheme:
            self.url = f"https://{self.url}"
        self._api = f"{self.url}/api/v1"

    def get_posts(self, *, limit: int = 25, offset: int = 0,
                  sorting: str = "new") -> list["_Post"]:
        params = {"sort": sorting, "limit": limit, "offset": offset}
        try:
            r = requests.get(f"{self._api}/posts", headers=_HEADERS,
                             params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("Failed to fetch posts from %s: %s", self.url, e)
            return []
        post_list = data.get("posts", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        posts: list[_Post] = []
        for entry in post_list:
            if not isinstance(entry, dict):
                continue
            url = entry.get("canonical_url") or (
                f"{self.url}/p/{entry['slug']}" if "slug" in entry else None
            )
            if url:
                p = _Post(url)
                p._cached_data = entry
                posts.append(p)
        return posts


class _Post:
    def __init__(self, url: str):
        parsed = urlparse(url if "://" in url else f"https://{url}")
        self.url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        path_parts = parsed.path.strip("/").split("/")
        self.slug = path_parts[-1].split("?")[0].split("#")[0] \
            if len(path_parts) >= 2 and path_parts[-2] == "p" else ""
        self._endpoint = f"{parsed.scheme}://{parsed.netloc}/api/v1/posts/{self.slug}"
        self._cached_data: dict[str, Any] | None = None

    def get_metadata(self) -> dict[str, Any]:
        if self._cached_data is None:
            try:
                r = requests.get(self._endpoint, headers=_HEADERS, timeout=30)
                r.raise_for_status()
                self._cached_data = r.json()
            except Exception as e:
                logger.warning("Failed to fetch post metadata for %s: %s", self.url, e)
                self._cached_data = {}
        return self._cached_data

    def get_content(self) -> str | None:
        data = self.get_metadata()
        for field in ("body_html", "content", "html", "body"):
            if data.get(field):
                return data[field]
        return None


class SubstackService:
    """Discover and fetch Substack posts. Consolidates legacy DatabaseSearch + ArticleRetrieval + API client."""

    PAGE_SIZE = 25

    def __init__(self, csv_path: Path | str, *, request_delay: float = 0.05):
        self._urls = load_substack_urls(Path(csv_path))
        self._delay = request_delay
        logger.info("Loaded %d Substack URLs from %s", len(self._urls), csv_path)

    def discover(self, *, max_age_days: int | None,
                 test_mode: bool) -> Iterator[Article]:
        """Yield articles across all configured Substacks."""
        articles_per_substack = 10 if test_mode else 200
        max_substacks = 30 if test_mode else len(self._urls)
        total = min(max_substacks, len(self._urls))
        mode_label = "TEST" if test_mode else "FULL"
        logger.info(
            "Discovery starting (%s mode): iterating %d/%d substacks, "
            "max %d articles per substack",
            mode_label, total, len(self._urls), articles_per_substack,
        )
        for i, url in enumerate(self._urls[:max_substacks], start=1):
            logger.info("[%d/%d] %s", i, total, url)
            articles = self.fetch_posts(url, max_articles=articles_per_substack,
                                         max_age_days=max_age_days)
            logger.info("  -> %d articles fetched (after age filter)", len(articles))
            yield from articles
            time.sleep(self._delay)
        logger.info("Discovery complete: walked %d substacks", total)

    def fetch_posts(self, newsletter_url: str, *, max_articles: int,
                     max_age_days: int | None) -> list[Article]:
        nl = self._make_newsletter(newsletter_url)
        articles: list[Article] = []
        offset = 0
        while True:
            batch = nl.get_posts(limit=self.PAGE_SIZE, offset=offset, sorting="new")
            if not batch:
                break
            for post in batch:
                article = self._post_to_article(post)
                if article is None:
                    continue
                if max_age_days is not None and self._is_too_old(article, max_age_days):
                    continue
                articles.append(article)
                if len(articles) >= max_articles:
                    return articles
            if len(batch) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE
            time.sleep(self._delay)
        return articles

    def _make_newsletter(self, url: str) -> _Newsletter:
        return _Newsletter(url)

    @staticmethod
    def _post_to_article(post: _Post) -> Article | None:
        meta = post.get_metadata()
        if not meta:
            return None
        body = post.get_content() or ""
        description = meta.get("description") or ""
        # Substack returns body as HTML — strip markup so Analyzer LLM can read
        # content directly instead of wasting tokens on tags.
        body_text = html_to_text(body)
        description_text = html_to_text(description)
        return Article(
            title=meta.get("title", "Unknown Title"),
            author=meta.get("byline", "Unknown Author"),
            date=meta.get("post_date", ""),
            text=f"{description_text}\n\n{body_text}".strip(),
            url=meta.get("canonical_url", post.url),
        )

    @staticmethod
    def _is_too_old(article: Article, max_age_days: int) -> bool:
        if not article.date:
            return False
        try:
            d = datetime.datetime.fromisoformat(article.date.replace("Z", "+00:00"))
        except ValueError:
            try:
                d = datetime.datetime.strptime(article.date, "%Y-%m-%d")
                d = d.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                return False
        delta = datetime.datetime.now(datetime.timezone.utc) - d
        return delta.days > max_age_days
