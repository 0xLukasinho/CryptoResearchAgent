import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Tweet:
    title: str
    text: str
    url: str
    file_path: Path


class TweetExtractor:
    def extract(self, urls_file: Path | str, *, output_dir: Path | str) -> list[Tweet]:
        urls_file = Path(urls_file)
        if not urls_file.exists():
            logger.warning("Tweets file not found: %s", urls_file)
            return []
        urls = [u.strip() for u in urls_file.read_text(encoding="utf-8").splitlines() if u.strip()]
        out_dir = Path(output_dir) / "tweets"
        out_dir.mkdir(parents=True, exist_ok=True)

        results: list[Tweet] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            for i, url in enumerate(urls, start=1):
                text = self._extract_one(page, url)
                if not text:
                    continue
                file_path = out_dir / f"tweet_{i}.txt"
                file_path.write_text(text, encoding="utf-8")
                results.append(Tweet(title=f"Tweet {i}", text=text, url=url, file_path=file_path))
                time.sleep(1)
        return results

    def _extract_one(self, page, url: str) -> str | None:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector('[data-testid="tweetText"]', timeout=10000)
            return page.evaluate(
                'document.querySelector(\'[data-testid="tweetText"]\')?.textContent ?? null'
            )
        except Exception as e:
            logger.warning("Tweet extraction failed for %s: %s", url, e)
            return None
