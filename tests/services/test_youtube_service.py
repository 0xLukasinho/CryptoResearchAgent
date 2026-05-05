import responses
from pathlib import Path

from crypto_research_agent.services.youtube import YouTubeService


def _channels_csv(tmp_path: Path) -> Path:
    f = tmp_path / "channels.csv"
    f.write_text("Name,Channel ID,YouTube URL\nFoo,UC123,https://youtube.com/@foo\n")
    return f


@responses.activate
def test_search_returns_videos(tmp_path):
    responses.add(
        responses.GET,
        "https://www.googleapis.com/youtube/v3/channels",
        json={"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://www.googleapis.com/youtube/v3/playlistItems",
        json={"items": [{
            "snippet": {
                "title": "Bitcoin ETF news",
                "publishedAt": "2026-01-01T00:00:00Z",
                "channelTitle": "Foo",
                "description": "ETF discussion",
                "resourceId": {"videoId": "vid1"},
            }
        }]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.supadata.ai/v1/youtube/transcript",
        json={"content": "transcript text", "lang": "en"},
        status=200,
    )

    svc = YouTubeService(api_key="k", supadata_key="s",
                        channels_csv=_channels_csv(tmp_path))
    videos = svc.search(
        query="Bitcoin ETF",
        required_terms=["bitcoin", "etf"],
        max_results=5,
        max_age_days=None,
        test_mode=False,
        output_dir=tmp_path / "out",
    )
    assert len(videos) == 1
    assert videos[0].title == "Bitcoin ETF news"
    assert videos[0].transcript == "transcript text"
