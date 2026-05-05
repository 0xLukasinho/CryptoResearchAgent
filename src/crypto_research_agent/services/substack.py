from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

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
