import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
SUBSTACK_CSV = INPUT_DIR / "Substacks.csv"
YOUTUBE_CSV = INPUT_DIR / "YouTubes.csv"
WRITING_SAMPLES_DIR = INPUT_DIR / "writing_samples"
WRITING_INSTRUCTIONS_FILE = INPUT_DIR / "writing_instructions.txt"

# Model constants
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_PREMIUM_MODEL = "claude-opus-4-7"
CLAUDE_SONNET_MODEL = "claude-sonnet-4-6"

# External API keys for non-Claude services. NOTE: ANTHROPIC_API_KEY is
# intentionally NOT loaded here — see ClaudeCodeBackend's env-scrub for the
# rationale. Loading it would risk routing claude -p calls through the
# Anthropic API instead of the Claude Max subscription.
SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")
CLOUDCONVERT_API_KEY = os.environ.get("CLOUDCONVERT_API_KEY", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# SupaData
SUPADATA_BASE_URL = "https://api.supadata.ai/v1"
SUPADATA_TRANSCRIPT_ENDPOINT = "/youtube/transcript"
SUPADATA_REQUEST_DELAY = 1.2
SUPADATA_MAX_TRANSCRIPTS = 5

# CloudConvert
CLOUDCONVERT_BASE_URL = "https://api.cloudconvert.com/v2"

# YouTube Data API
YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_MAX_RESULTS_PER_PAGE = 50

# Article output
ARTICLE_FILENAME = "article.md"
OUTLINE_FILENAME = "research_outline.md"
RESEARCH_RESULTS_FILENAME = "research_results.md"
STYLE_CARD_FILENAME = "style_card.json"


def get_model_for_role(role: str, *, test_mode: bool) -> str:
    """Resolve model ID for a role, honoring test mode (Haiku for everything)."""
    if test_mode:
        return CLAUDE_FAST_MODEL
    return {
        "fast": CLAUDE_FAST_MODEL,
        "premium": CLAUDE_PREMIUM_MODEL,
    }[role]
