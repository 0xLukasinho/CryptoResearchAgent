import os
import sys
import json
import re
sys.path.append('..')
from config import WRITING_SAMPLES_DIR, WRITING_INSTRUCTIONS_FILE, CLAUDE_QUALITY_MODEL
import docx  # For handling .docx files
from agents.anthropic_client import AnthropicClient
from utils.logger import get_logger
from utils.token_utils import truncate_to_token_limit

class StyleLearningAgent:
    """
    Agent responsible for collecting and passing on user's writing samples and instructions.
    """
    
    def __init__(self):
        """
        Initialize the StyleLearningAgent.
        """
        self.sample_files = []
        self.has_instructions = False
        self.anthropic_client = AnthropicClient()
        self.logger = get_logger(__name__)
    
    def prompt_for_samples(self):
        """
        Prompt the user to add writing samples and instructions.
        
        Returns:
            bool: True if user confirms, False otherwise
        """
        self.logger.info("\n[ARTICLE WRITER] Style Learning Setup")
        self.logger.info(f"Please add writing samples (.txt or .docx files) to: {WRITING_SAMPLES_DIR}")
        self.logger.info(f"Please create or edit writing instructions at: {WRITING_INSTRUCTIONS_FILE}")
        self.logger.info("These will help Claude write in your preferred style.")
        self.logger.info("Type 'continue' when you've added your samples and instructions.")
        
        while True:
            user_input = input("> ").strip().lower()
            if user_input == 'continue':
                return True
            else:
                self.logger.info("Type 'continue' when you're ready to proceed.")
    
    def load_samples(self):
        """
        Load all .txt and .docx files from the samples directory.
        
        Returns:
            list: Paths to all sample files
        """
        if not os.path.exists(WRITING_SAMPLES_DIR):
            raise FileNotFoundError(f"Writing samples directory not found: {WRITING_SAMPLES_DIR}")
        
        # Get all .txt and .docx files in the directory
        sample_files = []
        for filename in os.listdir(WRITING_SAMPLES_DIR):
            if (filename.endswith('.txt') and filename != 'README.txt') or filename.endswith('.docx'):
                sample_files.append(os.path.join(WRITING_SAMPLES_DIR, filename))
        
        self.sample_files = sample_files
        return sample_files
    
    def read_docx(self, file_path):
        """
        Extract text from a .docx file.
        
        Args:
            file_path (str): Path to the .docx file
            
        Returns:
            str: Extracted text content
        """
        try:
            doc = docx.Document(file_path)
            content = []
            
            # Extract text from paragraphs
            for para in doc.paragraphs:
                content.append(para.text)
            
            return '\n'.join(content)
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {e}")
            return f"[Error extracting content from {os.path.basename(file_path)}: {str(e)}]"
    
    def load_instructions(self):
        """
        Load writing instructions from file.
        
        Returns:
            str: Content of the instructions file or None if not found
        """
        if not os.path.exists(WRITING_INSTRUCTIONS_FILE):
            self.logger.info(f"No writing instructions file found at: {WRITING_INSTRUCTIONS_FILE}")
            return None
        
        with open(WRITING_INSTRUCTIONS_FILE, 'r', encoding='utf-8') as f:
            instructions = f.read()
        
        self.has_instructions = bool(instructions.strip())
        return instructions if self.has_instructions else None
    
    def get_raw_style_materials(self):
        """
        Get the raw text from all samples and instructions.
        
        Returns:
            dict: Raw text materials with 'samples' and 'instructions' keys
        """
        # Load sample files
        sample_files = self.load_samples()
        
        # Read content from each sample file
        samples_content = []
        for file_path in sample_files:
            try:
                if file_path.endswith('.docx'):
                    # Handle Word documents
                    content = self.read_docx(file_path)
                    filename = os.path.basename(file_path)
                    samples_content.append({
                        'filename': filename,
                        'content': content
                    })
                else:
                    # Handle text files
                    with open(file_path, 'r', encoding='utf-8') as f:
                        filename = os.path.basename(file_path)
                        content = f.read()
                        samples_content.append({
                            'filename': filename,
                            'content': content
                        })
            except Exception as e:
                self.logger.error(f"Error reading sample file {file_path}: {e}")
        
        # Load instructions
        instructions_content = self.load_instructions()
        
        # Report on what was found
        self.logger.info(f"[ARTICLE WRITER] Found {len(samples_content)} writing samples")
        total_chars = sum(len(sample['content']) for sample in samples_content)
        self.logger.info(f"[ARTICLE WRITER] Total content size: {total_chars} characters across all samples")

        for sample in samples_content:
            content_length = len(sample['content'])
            is_docx = sample['filename'].endswith('.docx')
            file_type = "Word document" if is_docx else "text file"
            words = len(sample['content'].split())
            self.logger.info(f"  - {sample['filename']} ({content_length} chars, ~{words} words, {file_type})")

        if instructions_content:
            self.logger.info(f"[ARTICLE WRITER] Found writing instructions ({len(instructions_content)} chars)")
        else:
            self.logger.info("[ARTICLE WRITER] No writing instructions found")
        
        return {
            'samples': samples_content,
            'instructions': instructions_content
        }

    def generate_style_card(self, style_materials: dict) -> dict:
        """
        Generate a structured JSON style card from writing samples and instructions.
        Called once per session; result is embedded in every article generation prompt.

        Args:
            style_materials: dict with 'samples' (list of {filename, content}) and
                             'instructions' (str or None from writing_instructions.txt)

        Returns:
            dict with keys: tone, sentence_patterns, vocabulary, paragraph_structure,
                            section_openings, transitions, example_excerpts
        """
        samples = style_materials.get('samples', [])
        instructions = style_materials.get('instructions', '')

        samples_text = ""
        for sample in samples:
            content = truncate_to_token_limit(sample.get('content', ''), CLAUDE_QUALITY_MODEL, 3000)
            samples_text += f"\n--- {sample.get('filename', 'sample')} ---\n{content}\n"

        instructions_section = (
            f"\nExplicit writing instructions from the author:\n{instructions}"
            if instructions else ""
        )

        prompt = f"""Analyze these writing samples and produce a structured style card that captures the author's voice precisely.

{samples_text}{instructions_section}

Return a JSON object with exactly these keys:
- "tone": string describing overall tone (e.g. "analytical but conversational, avoids hype")
- "sentence_patterns": string describing sentence structure patterns
- "vocabulary": object with "preferred" (list of characteristic words/phrases) and "avoided" (list of words to avoid)
- "paragraph_structure": string describing how paragraphs are typically structured
- "section_openings": string describing how sections typically begin
- "transitions": list of characteristic transition phrases used by this author
- "example_excerpts": list of 3-5 verbatim excerpts that best represent the author's voice at its most characteristic

Focus on what makes this voice distinctive and reproducible."""

        system = (
            "You are a writing style analyst. Extract precise, actionable style characteristics "
            "from writing samples. Respond with valid JSON only."
        )

        response = self.anthropic_client.generate_content(
            prompt=prompt,
            system_prompt=system,
            max_tokens=2000,
            model_override=CLAUDE_QUALITY_MODEL
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        self.logger.error("Failed to parse style card JSON, using fallback")
        return {
            "tone": "analytical and informative",
            "sentence_patterns": "clear and direct",
            "vocabulary": {"preferred": [], "avoided": []},
            "paragraph_structure": "structured with clear points",
            "section_openings": "direct assertions",
            "transitions": [],
            "example_excerpts": []
        }

    def format_style_card_for_prompt(self, style_card: dict) -> str:
        """
        Format a style card dict into a string for embedding in system prompts.

        Args:
            style_card: dict from generate_style_card()

        Returns:
            str: Formatted style guide ready for system prompt injection
        """
        vocab = style_card.get('vocabulary', {})
        preferred = ', '.join(vocab.get('preferred', [])) or 'none specified'
        avoided = ', '.join(vocab.get('avoided', [])) or 'none specified'
        transitions = ', '.join(f'"{t}"' for t in style_card.get('transitions', [])) or 'none specified'

        excerpts_text = ""
        for excerpt in style_card.get('example_excerpts', []):
            excerpts_text += f"\n> {excerpt}\n"

        return f"""## Writing Style Guide

**Tone:** {style_card.get('tone', '')}
**Sentence patterns:** {style_card.get('sentence_patterns', '')}
**Paragraph structure:** {style_card.get('paragraph_structure', '')}
**Section openings:** {style_card.get('section_openings', '')}
**Preferred transitions:** {transitions}
**Vocabulary to use:** {preferred}
**Vocabulary to avoid:** {avoided}

## Example Excerpts from the Author's Writing
{excerpts_text}
Match this voice precisely. Every section you write — including rewrites — must sound like these excerpts."""