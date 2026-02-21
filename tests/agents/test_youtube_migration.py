# tests/agents/test_youtube_migration.py
import sys
sys.path.insert(0, '.')
import inspect


def test_youtube_agent_has_no_openai():
    import agents.youtube_search as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source
