from pathlib import Path

from .prompts import parse_feedback_input, render_review_prompt, safe_input


class OutlineReview:
    def run(self, *, outline_path: Path, outline_writer,
            articles, videos, user_content, query: str, thesis: str | None) -> str:
        outline_path = Path(outline_path)
        print(render_review_prompt(item_label="Outline", file_path=str(outline_path)))
        current = outline_path.read_text(encoding="utf-8")
        while True:
            # EOF → accept current outline, exit the loop cleanly
            raw = safe_input("> ", on_eof="accept")
            fb = parse_feedback_input(raw)
            if fb["action"] == "accept":
                return current
            if fb["action"] == "edited":
                current = outline_path.read_text(encoding="utf-8")
                return current
            if fb["action"] == "revise":
                revised = outline_writer.revise(
                    current=current, instructions=fb["details"],
                    articles=articles, videos=videos, user_content=user_content,
                    query=query, thesis=thesis,
                )
                outline_path.write_text(revised, encoding="utf-8")
                current = revised
                print(render_review_prompt(item_label="Revised outline",
                                            file_path=str(outline_path)))
                continue
            print("Invalid input. Use [1] accept / [2] revise <instructions> / [3] edited")
