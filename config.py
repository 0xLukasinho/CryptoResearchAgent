import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# API Configuration - Load from environment variables
SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")
CLOUDCONVERT_API_KEY = os.environ.get("CLOUDCONVERT_API_KEY", "")  # Added CloudConvert API key

# Anthropic API Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # Recommend using environment variable for security

# Claude model constants — change these to upgrade all agents at once
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"    # Cost-efficient: coordination, analysis, search
CLAUDE_QUALITY_MODEL = "claude-sonnet-4-6"          # High quality: writing, outlines, style

# Backward compatibility aliases
ANTHROPIC_MODEL = CLAUDE_QUALITY_MODEL
ANTHROPIC_TEST_MODEL = CLAUDE_FAST_MODEL

# Outline Generation Models
OUTLINE_MODEL = CLAUDE_QUALITY_MODEL  # Use Claude 3.5 Sonnet for standard outline generation
OUTLINE_TEST_MODEL = CLAUDE_FAST_MODEL  # Use Claude 3 Haiku for test mode outline generation

# Outline Generation Settings
OUTLINE_FILE_NAME = "research_outline.md"

# Article Writer Configuration
WRITING_SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "input/writing_samples")
WRITING_INSTRUCTIONS_FILE = os.path.join(os.path.dirname(__file__), "input/writing_instructions.txt")
ARTICLE_FILENAME = "article.md"

# Article limit for testing
ARTICLE_LIMIT = 15

# Input and output directories
INPUT_DIR = "input"
OUTPUT_DIR = "output"

# File paths
CSV_PATH = os.path.join(INPUT_DIR, "Substacks.csv")
YOUTUBE_CSV_PATH = os.path.join(INPUT_DIR, "YouTubes.csv")

# SupaData API Configuration
SUPADATA_BASE_URL = "https://api.supadata.ai/v1"
SUPADATA_TRANSCRIPT_ENDPOINT = "/youtube/transcript"
SUPADATA_REQUEST_DELAY = 1.2  # Increased from 0.7 to reduce 429 errors
SUPADATA_MAX_TRANSCRIPTS = 5  # Maximum number of transcripts per search

# CloudConvert Configuration
CLOUDCONVERT_BASE_URL = "https://api.cloudconvert.com/v2"  # Base URL for CloudConvert API

# YouTube API Configuration
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_MAX_RESULTS_PER_PAGE = 50  # Maximum results per API request

# ... rest of the file remains unchanged ...
