from crypto_research_agent.pipeline.runner import RunContext, SourceConfig


def test_run_context_holds_fields(tmp_path):
    ctx = RunContext(
        query="bitcoin", thesis=None, output_dir=tmp_path,
        test_mode=False, search_mode=False,
        sources=SourceConfig(substack=True, youtube=True),
        max_age_days=None, parallel=1,
    )
    assert ctx.query == "bitcoin"
    assert ctx.sources.substack
