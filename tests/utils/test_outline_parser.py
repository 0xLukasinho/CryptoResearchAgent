from crypto_research_agent.utils.outline_parser import parse_sections


def test_parse_simple_outline():
    outline = """# My Article
## 1. Introduction
- A bullet
- Another bullet

## 2. Body
- Body bullet
"""
    sections = parse_sections(outline)
    assert len(sections) == 2
    assert sections[0]["title"] == "1. Introduction"
    assert "- A bullet" in sections[0]["content"]
    assert sections[1]["title"] == "2. Body"


def test_skips_h1_title():
    outline = "# Title\n## Section A\n- x"
    sections = parse_sections(outline)
    assert len(sections) == 1
    assert sections[0]["title"] == "Section A"


def test_handles_empty_outline():
    assert parse_sections("") == []


def test_subsections_included_in_content():
    outline = """## 1. Section
### 1.1 Subsection
- bullet
### 1.2 Another sub
- bullet
"""
    sections = parse_sections(outline)
    assert len(sections) == 1
    assert "### 1.1 Subsection" in sections[0]["content"]
    assert "### 1.2 Another sub" in sections[0]["content"]
