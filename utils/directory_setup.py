import os
import sys
sys.path.append('..')
from config import WRITING_SAMPLES_DIR, WRITING_INSTRUCTIONS_FILE

def setup_article_writer_directories():
    """
    Create all necessary directories for the article writer feature.
    """
    # Create writing samples directory if it doesn't exist
    os.makedirs(WRITING_SAMPLES_DIR, exist_ok=True)
    
    # Create a README.txt in the writing samples directory to guide users
    readme_path = os.path.join(WRITING_SAMPLES_DIR, "README.txt")
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(
                "Place your writing samples in this directory.\n"
                "These will be used to help the AI learn your writing style.\n"
                "Files can be either text (.txt) or Word (.docx) format.\n"
                "Note: Word files will need to be processed with additional tools in Phase 2.\n"
            )
    
    # Create a template writing_instructions.txt if it doesn't exist
    if not os.path.exists(WRITING_INSTRUCTIONS_FILE):
        with open(WRITING_INSTRUCTIONS_FILE, "w", encoding="utf-8") as f:
            f.write(
                "# Writing Style Instructions\n\n"
                "Provide detailed instructions about your preferred writing style here.\n\n"
                "Examples:\n"
                "- Tone (formal/casual/technical)\n"
                "- Sentence length preferences\n"
                "- Use of analogies or metaphors\n"
                "- Preferred formatting style\n"
                "- Citation preferences\n"
                "- Any specific phrases or terms to use/avoid\n"
            ) 