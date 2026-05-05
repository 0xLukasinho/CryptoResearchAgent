from unittest.mock import MagicMock

from crypto_research_agent.agents.coordinator import Coordinator, SearchPlan


def test_plan_returns_search_plan_with_main_topic_and_terms():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "main_topic": "Bitcoin ETF",
        "required_terms": ["bitcoin", "etf"],
    }
    coord = Coordinator(backend, model="m")
    plan = coord.plan("Bitcoin ETF inflows")
    assert isinstance(plan, SearchPlan)
    assert plan.main_topic == "Bitcoin ETF"
    assert plan.required_terms == ["bitcoin", "etf"]


def test_plan_falls_back_when_llm_returns_garbage():
    backend = MagicMock()
    backend.complete_json.return_value = {}
    coord = Coordinator(backend, model="m")
    plan = coord.plan("something")
    assert plan.main_topic == "something"
    assert plan.required_terms == []


def test_plan_filters_invalid_terms():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "main_topic": "x",
        "required_terms": ["bitcoin", "", None, "etf"],
    }
    coord = Coordinator(backend, model="m")
    plan = coord.plan("q")
    assert plan.required_terms == ["bitcoin", "etf"]
