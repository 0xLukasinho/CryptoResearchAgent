from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    """Strip HTML markup and return plain text. Empty/non-HTML input returns
    the input unchanged (after whitespace normalization)."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    # Drop noisy elements entirely (their text isn't useful for analysis)
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Normalize whitespace: collapse runs of blank lines to a single newline
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    return cleaned
