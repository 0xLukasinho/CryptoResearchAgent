from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from ..utils.logger import get_logger

logger = get_logger(__name__)

FileType = Literal["text", "pdf", "csv", "tweet"]

_MAX_BYTES = {
    "text": 1 * 1024 * 1024,
    "pdf": 10 * 1024 * 1024,
    "csv": 5 * 1024 * 1024,
}


@dataclass
class UserContent:
    title: str
    author: str
    text: str
    url: str
    file_type: FileType
    key_insights: list[str] = field(default_factory=list)
    mentioned_projects: list[str] = field(default_factory=list)


class UserContentService:
    """Collects user-supplied files (txt/md/pdf/csv) and runs analyzer for insights."""

    def __init__(self, *, analyzer):
        self._analyzer = analyzer

    def collect(self, content_dir: Path | str) -> list[UserContent]:
        content_dir = Path(content_dir)
        if not content_dir.exists():
            return []
        out: list[UserContent] = []
        for path in sorted(content_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name.lower() == "tweets.txt":
                continue  # processed separately by TweetExtractor
            handler = self._dispatch(path)
            if handler is None:
                continue
            try:
                item = handler(path)
                if item is not None:
                    out.append(item)
            except Exception as e:
                logger.warning("Failed to process %s: %s", path.name, e)
        return out

    def _dispatch(self, path: Path) -> Callable[[Path], UserContent | None] | None:
        suffix = path.suffix.lower()
        if suffix in (".txt", ".md"):
            return self._process_text
        if suffix == ".pdf":
            return self._process_pdf
        if suffix == ".csv":
            return self._process_csv
        return None

    def _check_size(self, path: Path, file_type: str) -> bool:
        if path.stat().st_size > _MAX_BYTES[file_type]:
            logger.warning("Skipping %s: exceeds %d bytes", path.name, _MAX_BYTES[file_type])
            return False
        return True

    def _process_text(self, path: Path) -> UserContent | None:
        if not self._check_size(path, "text"):
            return None
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return None
        insights, projects = self._analyzer.extract_insights(content)
        return UserContent(
            title=path.stem, author="User Provided",
            text=content[:5000], url=f"file://{path}", file_type="text",
            key_insights=insights, mentioned_projects=projects,
        )

    def _process_pdf(self, path: Path) -> UserContent | None:
        if not self._check_size(path, "pdf"):
            return None
        import pdfplumber
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n\n"
        if not text.strip():
            return None
        insights, projects = self._analyzer.extract_insights(text)
        return UserContent(
            title=path.stem, author="User Provided",
            text=text[:5000], url=f"file://{path}", file_type="pdf",
            key_insights=insights, mentioned_projects=projects,
        )

    def _process_csv(self, path: Path) -> UserContent | None:
        if not self._check_size(path, "csv"):
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")
        if not content.strip():
            return None
        insights, projects = self._analyzer.extract_insights(content[:8000])
        return UserContent(
            title=path.stem, author="User Provided",
            text=f"CSV DATA:\n\n{content[:5000]}", url=f"file://{path}", file_type="csv",
            key_insights=insights, mentioned_projects=projects,
        )
