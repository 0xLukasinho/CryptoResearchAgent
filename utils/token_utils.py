# utils/token_utils.py
import tiktoken

# Claude models use the same tokenizer as GPT-4
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def truncate_to_token_limit(text: str, model: str, limit: int) -> str:
    """
    Truncate text to fit within a token limit, preferring sentence boundaries.

    Args:
        text: Text to truncate
        model: Model name (reserved for future model-specific tokenizers)
        limit: Maximum number of tokens

    Returns:
        Truncated text that fits within the token limit
    """
    tokens = _TOKENIZER.encode(text)
    if len(tokens) <= limit:
        return text

    truncated = _TOKENIZER.decode(tokens[:limit])

    # Try to end at a sentence boundary in the latter 30% of the text
    for delimiter in ('. ', '.\n', '? ', '! '):
        pos = truncated.rfind(delimiter)
        if pos > len(truncated) * 0.7:
            return truncated[:pos + 1]

    return truncated
