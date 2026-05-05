from unittest.mock import patch, MagicMock

from crypto_research_agent.services.tweet_extractor import TweetExtractor, Tweet


def test_extract_returns_tweets_with_files(tmp_path):
    urls_file = tmp_path / "tweets.txt"
    urls_file.write_text("https://twitter.com/x/status/1\nhttps://twitter.com/y/status/2\n")
    fake_page = MagicMock()
    fake_page.evaluate.side_effect = ["First tweet text", "Second tweet text"]
    fake_browser = MagicMock()
    fake_context = MagicMock()
    fake_context.new_page.return_value = fake_page
    fake_browser.new_context.return_value = fake_context

    pw_cm = MagicMock()
    pw_cm.__enter__.return_value = MagicMock(chromium=MagicMock(launch=MagicMock(return_value=fake_browser)))
    pw_cm.__exit__.return_value = False

    extractor = TweetExtractor()
    with patch("crypto_research_agent.services.tweet_extractor.sync_playwright", return_value=pw_cm):
        with patch("time.sleep"):
            tweets = extractor.extract(urls_file, output_dir=tmp_path)
    assert len(tweets) == 2
    assert tweets[0].text == "First tweet text"
    assert (tmp_path / "tweets" / "tweet_1.txt").exists()


def test_missing_file_returns_empty(tmp_path):
    extractor = TweetExtractor()
    assert extractor.extract(tmp_path / "missing.txt", output_dir=tmp_path) == []
