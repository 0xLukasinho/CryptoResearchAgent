from dataclasses import dataclass


COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for a crypto research workflow.
Analyze the user's research query and respond with valid JSON containing:
- main_topic: The primary cryptocurrency or blockchain topic
- required_terms: Terms STRICTLY from the user's query — never add extras not in the query
"""


@dataclass(frozen=True)
class SearchPlan:
    main_topic: str
    required_terms: list[str]


class Coordinator:
    def __init__(self, backend, *, model: str):
        self._backend = backend
        self._model = model

    def plan(self, query: str) -> SearchPlan:
        result = self._backend.complete_json(
            prompt=query, model=self._model,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
        )
        terms = [
            str(t).strip() for t in result.get("required_terms", [])
            if t and isinstance(t, str) and t.strip()
        ]
        return SearchPlan(
            main_topic=result.get("main_topic") or query,
            required_terms=terms,
        )
