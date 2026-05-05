import datetime
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import requests

from ..config import (
    YOUTUBE_API_BASE_URL, SUPADATA_BASE_URL, SUPADATA_TRANSCRIPT_ENDPOINT,
    SUPADATA_REQUEST_DELAY,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


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


class YouTubeService:
    """Search a curated list of YouTube channels, filter by required terms,
    fetch transcripts for top relevance matches."""

    YOUTUBE_REQUEST_DELAY = 0.3

    def __init__(self, *, api_key: str, supadata_key: str, channels_csv: Path | str):
        self._api_key = api_key
        self._supadata_key = supadata_key
        self._channels = pd.read_csv(channels_csv) if Path(channels_csv).exists() else pd.DataFrame()

    def search(self, *, query: str, required_terms: list[str], max_results: int,
               max_age_days: int | None, test_mode: bool, output_dir: Path) -> list[Video]:
        if self._channels.empty:
            return []
        chans = self._channels.head(2) if test_mode else self._channels
        all_videos: list[Video] = []
        for _, channel in chans.iterrows():
            videos = self._channel_videos(
                channel_id=channel.get("Channel ID", ""),
                channel_url=channel.get("YouTube URL", ""),
                max_age_days=max_age_days,
            )
            all_videos.extend(videos)
            if test_mode and len(filter_by_required_terms(all_videos, required_terms)) >= 2:
                break

        filtered = filter_by_required_terms(all_videos, required_terms)
        scored = sorted(
            (score_relevance(v, query=query) for v in filtered),
            key=lambda v: v.relevance_value,
            reverse=True,
        )[:max_results]

        return self._with_transcripts(scored, output_dir=output_dir)

    def _channel_videos(self, *, channel_id: str, channel_url: str,
                         max_age_days: int | None) -> list[Video]:
        if not channel_id or not channel_id.startswith("UC"):
            logger.debug("Skipping channel with no Channel ID: %s", channel_url)
            return []
        playlist_id = self._get_uploads_playlist(channel_id)
        if not playlist_id:
            return []
        return self._playlist_videos(playlist_id, max_age_days=max_age_days)

    def _get_uploads_playlist(self, channel_id: str) -> str | None:
        time.sleep(self.YOUTUBE_REQUEST_DELAY)
        r = requests.get(
            f"{YOUTUBE_API_BASE_URL}/channels",
            params={"key": self._api_key, "part": "contentDetails", "id": channel_id},
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning("YouTube channels endpoint error %s", r.status_code)
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def _playlist_videos(self, playlist_id: str, *,
                          max_age_days: int | None) -> list[Video]:
        videos: list[Video] = []
        page_token: str | None = None
        for _ in range(4):  # max 4 pages = 200 videos
            time.sleep(self.YOUTUBE_REQUEST_DELAY)
            params: dict[str, Any] = {
                "key": self._api_key,
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            r = requests.get(f"{YOUTUBE_API_BASE_URL}/playlistItems", params=params, timeout=30)
            if r.status_code != 200:
                break
            data = r.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                published = snippet.get("publishedAt", "")
                if max_age_days is not None and published:
                    try:
                        d = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
                        if (datetime.datetime.now(datetime.timezone.utc) - d).days > max_age_days:
                            continue
                    except ValueError:
                        pass
                vid = snippet.get("resourceId", {}).get("videoId", "")
                videos.append(Video(
                    title=snippet.get("title", ""),
                    channel=snippet.get("channelTitle", ""),
                    date=published,
                    description=snippet.get("description", ""),
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                ))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return videos

    def _with_transcripts(self, videos: list[Video], *, output_dir: Path) -> list[Video]:
        out: list[Video] = []
        for v in videos:
            transcript = self._fetch_transcript(v.video_id)
            if transcript is None:
                continue
            v_with = replace(v, transcript=transcript)
            self._save_transcript(v_with, output_dir=output_dir)
            out.append(v_with)
        return out

    def _fetch_transcript(self, video_id: str) -> str | None:
        if not video_id:
            return None
        time.sleep(SUPADATA_REQUEST_DELAY)
        r = requests.get(
            f"{SUPADATA_BASE_URL}{SUPADATA_TRANSCRIPT_ENDPOINT}",
            headers={"x-api-key": self._supadata_key},
            params={"text": "true", "videoId": video_id},
            timeout=30,
        )
        if r.status_code != 200:
            logger.info("No transcript for %s (status %s)", video_id, r.status_code)
            return None
        return r.json().get("content")

    def _save_transcript(self, video: Video, *, output_dir: Path) -> None:
        if not video.transcript:
            return
        out = Path(output_dir) / "transcripts"
        out.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[\\/*?:\"<>|]", "_", video.title)[:100]
        (out / f"{safe}_transcript.txt").write_text(video.transcript, encoding="utf-8")
