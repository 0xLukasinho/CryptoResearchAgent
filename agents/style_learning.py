import os
import sys
sys.path.append('..')
from config import WRITING_SAMPLES_DIR, WRITING_INSTRUCTIONS_FILE
import docx  # For handling .docx files

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
    
    def prompt_for_samples(self):
        """
        Prompt the user to add writing samples and instructions.
        
        Returns:
            bool: True if user confirms, False otherwise
        """
        print("\n[ARTICLE WRITER] Style Learning Setup")
        print(f"Please add writing samples (.txt or .docx files) to: {WRITING_SAMPLES_DIR}")
        print(f"Please create or edit writing instructions at: {WRITING_INSTRUCTIONS_FILE}")
        print("These will help Claude write in your preferred style.")
        print("Type 'continue' when you've added your samples and instructions.")
        
        while True:
            user_input = input("> ").strip().lower()
            if user_input == 'continue':
                return True
            else:
                print("Type 'continue' when you're ready to proceed.")
    
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
            print(f"Error extracting text from {file_path}: {e}")
            return f"[Error extracting content from {os.path.basename(file_path)}: {str(e)}]"
    
    def load_instructions(self):
        """
        Load writing instructions from file.
        
        Returns:
            str: Content of the instructions file or None if not found
        """
        if not os.path.exists(WRITING_INSTRUCTIONS_FILE):
            print(f"No writing instructions file found at: {WRITING_INSTRUCTIONS_FILE}")
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
                print(f"Error reading sample file {file_path}: {e}")
        
        # Load instructions
        instructions_content = self.load_instructions()
        
        # Report on what was found
        print(f"[ARTICLE WRITER] Found {len(samples_content)} writing samples")
        total_chars = sum(len(sample['content']) for sample in samples_content)
        print(f"[ARTICLE WRITER] Total content size: {total_chars} characters across all samples")
        
        for sample in samples_content:
            content_length = len(sample['content'])
            is_docx = sample['filename'].endswith('.docx')
            file_type = "Word document" if is_docx else "text file"
            words = len(sample['content'].split())
            print(f"  - {sample['filename']} ({content_length} chars, ~{words} words, {file_type})")
        
        if instructions_content:
            print(f"[ARTICLE WRITER] Found writing instructions ({len(instructions_content)} chars)")
        else:
            print("[ARTICLE WRITER] No writing instructions found")
        
        return {
            'samples': samples_content,
            'instructions': instructions_content
        } 