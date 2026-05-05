from unittest.mock import MagicMock

from crypto_research_agent.services.user_content import UserContentService


def test_collect_processes_text_files(tmp_path):
    (tmp_path / "note.txt").write_text("This is a research note about Bitcoin.")
    analyzer = MagicMock()
    analyzer.extract_insights.return_value = (["insight 1"], ["Bitcoin"])
    svc = UserContentService(analyzer=analyzer)
    items = svc.collect(tmp_path)
    assert len(items) == 1
    assert items[0].file_type == "text"
    assert items[0].title == "note"
    assert items[0].mentioned_projects == ["Bitcoin"]


def test_collect_skips_oversize_files(tmp_path):
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB > 1 MB text limit
    analyzer = MagicMock()
    svc = UserContentService(analyzer=analyzer)
    assert svc.collect(tmp_path) == []


def test_collect_handles_empty_dir(tmp_path):
    svc = UserContentService(analyzer=MagicMock())
    assert svc.collect(tmp_path) == []
