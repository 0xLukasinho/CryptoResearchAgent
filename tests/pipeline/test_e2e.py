import pytest


@pytest.mark.skip(reason="E2E test scaffolding; flesh out after all stages stable")
def test_e2e_pipeline_writes_all_outputs(tmp_path, monkeypatch, fake_llm):
    """Full run with all LLM and HTTP calls mocked."""
    pass
