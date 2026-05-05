from typing import TypedDict


class Section(TypedDict):
    title: str
    content: str


def parse_sections(outline_content: str) -> list[Section]:
    sections: list[Section] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in outline_content.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            if current_title is not None:
                sections.append({"title": current_title, "content": "\n".join(current_lines)})
            current_title = line[3:].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections.append({"title": current_title, "content": "\n".join(current_lines)})
    return sections
