# tests/agents/test_batch_migration.py
import sys
sys.path.insert(0, '.')
import inspect
import importlib


def _has_no_openai(module_path):
    mod = importlib.import_module(module_path)
    source = inspect.getsource(mod)
    return 'from openai' not in source and 'OpenAI(' not in source


def test_database_search_uses_claude():
    assert _has_no_openai('agents.database_search')

def test_article_retrieval_uses_claude():
    assert _has_no_openai('agents.article_retrieval')

def test_summarization_uses_claude():
    assert _has_no_openai('agents.summarization')

def test_fact_checker_uses_claude():
    assert _has_no_openai('agents.fact_checker')
