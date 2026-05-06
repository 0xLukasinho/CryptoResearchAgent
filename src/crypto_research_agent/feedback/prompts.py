from typing import Literal, TypedDict


Action = Literal["accept", "edited", "revise", "invalid"]


class Feedback(TypedDict):
    action: Action
    details: str | None


def parse_feedback_input(raw: str) -> Feedback:
    s = (raw or "").strip()
    if not s:
        return {"action": "invalid", "details": None}
    parts = s.split(maxsplit=1)
    head = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if head in ("accept", "1"):
        return {"action": "accept", "details": None}
    if head in ("edited", "3"):
        return {"action": "edited", "details": None}
    if head in ("revise", "2"):
        if not rest:
            return {"action": "invalid", "details": None}
        return {"action": "revise", "details": rest}
    return {"action": "invalid", "details": None}


def render_review_prompt(*, item_label: str, file_path: str) -> str:
    return f"""[FEEDBACK] {item_label} has been written.
Review it: {file_path}

  [1] accept     proceed
  [2] revise     give the AI revision instructions
  [3] edited     I edited the file directly
"""
