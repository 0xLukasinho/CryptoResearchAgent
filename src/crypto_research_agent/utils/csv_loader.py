from pathlib import Path

import pandas as pd

from .logger import get_logger

logger = get_logger(__name__)


def load_substack_urls(csv_path: Path) -> list[str]:
    if not Path(csv_path).exists():
        logger.warning("Substack CSV not found: %s", csv_path)
        return []
    df = pd.read_csv(csv_path)
    raw = df["Substack URL"].dropna().tolist() if "Substack URL" in df.columns else []
    cleaned: list[str] = []
    for url in raw:
        if not isinstance(url, str) or len(url) <= 5:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        cleaned.append(url)
    return cleaned


def load_youtube_channels(csv_path: Path) -> pd.DataFrame:
    if not Path(csv_path).exists():
        logger.warning("YouTube CSV not found: %s", csv_path)
        return pd.DataFrame()
    return pd.read_csv(csv_path)
