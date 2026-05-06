from crypto_research_agent.utils.html import html_to_text


def test_strips_basic_tags():
    out = html_to_text("<p>Hello <strong>world</strong></p>")
    assert "Hello" in out
    assert "world" in out
    assert "<" not in out


def test_drops_script_and_style():
    out = html_to_text(
        "<p>visible</p><script>alert('x')</script><style>.a{}</style>"
    )
    assert "visible" in out
    assert "alert" not in out
    assert ".a" not in out


def test_collapses_whitespace_and_blank_lines():
    out = html_to_text("<div>line1</div>\n\n\n<div>line2</div>")
    assert out == "line1\nline2"


def test_empty_input_returns_empty():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_non_html_text_passes_through():
    out = html_to_text("just plain text")
    assert "plain text" in out


def test_preserves_link_text():
    out = html_to_text('<a href="https://x.com">click here</a>')
    assert "click here" in out
