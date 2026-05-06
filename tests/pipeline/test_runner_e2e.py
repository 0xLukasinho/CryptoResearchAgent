from unittest.mock import MagicMock

from crypto_research_agent.pipeline.runner import (
    PipelineRunner, RunContext, SourceConfig,
)


def test_runner_full_pipeline_with_mocks(tmp_path, monkeypatch):
    """End-to-end with all stages mocked: verifies the wiring."""
    monkeypatch.setattr("builtins.input", lambda *_: "ready")  # user content prompt
    runner = PipelineRunner.__new__(PipelineRunner)
    runner._build_coordinator = MagicMock(return_value=MagicMock(
        plan=MagicMock(return_value=MagicMock(main_topic="t", required_terms=["x"]))
    ))
    runner._build_discovery = MagicMock(return_value=MagicMock(
        run=MagicMock(return_value=([MagicMock()], [MagicMock()]))
    ))
    runner._build_synthesis = MagicMock(return_value=MagicMock(
        save_summary=MagicMock(),
        synthesize=MagicMock(return_value="# Outline\n## 1. Intro\n- bullet"),
    ))
    runner._build_writing = MagicMock(return_value=MagicMock(
        write=MagicMock(return_value=tmp_path / "article.md"),
    ))
    runner._build_user_content = MagicMock(return_value=MagicMock(
        collect=MagicMock(return_value=[]),
    ))
    runner._build_docx_export = MagicMock(return_value=MagicMock(
        export=MagicMock(return_value=tmp_path / "article.docx"),
    ))
    runner._stats = MagicMock()

    ctx = RunContext(query="q", thesis=None, output_dir=tmp_path,
                     test_mode=True, search_mode=False,
                     sources=SourceConfig(substack=True, youtube=True),
                     max_age_days=None, parallel=1)
    runner.run_with_context(ctx)
    runner._build_writing.assert_called()
