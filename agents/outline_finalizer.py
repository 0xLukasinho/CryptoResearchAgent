import os
import sys
sys.path.append('..')
from config import OUTLINE_FILE_NAME

class OutlineFinalizerAgent:
    """
    Agent responsible for confirming and parsing the user-modified outline.
    """
    
    def __init__(self):
        """
        Initialize the OutlineFinalizerAgent.
        """
        pass
    
    def prompt_for_outline_confirmation(self, outline_path):
        """
        Prompt the user to review and confirm the outline.
        
        Args:
            outline_path (str): Path to the outline file
            
        Returns:
            bool: True if user confirms, False otherwise
        """
        print(f"\n[ARTICLE WRITER] Your outline has been created at {outline_path}")
        print("Please review and make any necessary changes directly to the file.")
        print("IMPORTANT: Make sure to SAVE your changes (Ctrl+S) before continuing.")
        print("Type 'continue' when you're ready to proceed with article writing.")
        
        while True:
            user_input = input("> ").strip().lower()
            if user_input == 'continue':
                # Additional reminder to ensure file is saved
                print("Did you save your changes to the outline? (Type 'yes' to confirm)")
                save_confirmation = input("> ").strip().lower()
                if save_confirmation == 'yes':
                    return True
                else:
                    print("Please save your changes and then type 'continue' again.")
            else:
                print("Type 'continue' when you're ready to proceed.")
    
    def read_outline(self, outline_path):
        """
        Read the outline file from disk.
        
        Args:
            outline_path (str): Path to the outline file
            
        Returns:
            str: Content of the outline file
        """
        if not os.path.exists(outline_path):
            raise FileNotFoundError(f"Outline file not found: {outline_path}")
        
        with open(outline_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def parse_sections(self, outline_content):
        """
        Parse the outline content to extract sections.
        
        Args:
            outline_content (str): Content of the outline file
            
        Returns:
            list: List of section dictionaries with 'title' and 'content' keys
        """
        sections = []
        current_section = None
        section_content = []
        
        # Split outline into lines
        lines = outline_content.split('\n')
        
        for line in lines:
            # Check for headings (# for title, ## for sections)
            if line.startswith('# '):
                # This is the title, skip
                continue
            elif line.startswith('## '):
                # If we were processing a section, save it
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(section_content)
                    })
                
                # Start a new section
                current_section = line[3:].strip()  # Remove the '## ' prefix
                section_content = []
            elif current_section:
                # Add content to current section
                section_content.append(line)
        
        # Add the last section if there is one
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(section_content)
            })
        
        return sections
    
    def finalize_outline(self, query_output_dir):
        """
        Main method to handle the outline finalization process.
        
        Args:
            query_output_dir (str): Directory containing the outline
            
        Returns:
            list: List of parsed sections from the outline
        """
        outline_path = os.path.join(query_output_dir, OUTLINE_FILE_NAME)
        
        # Prompt user to confirm outline
        confirmed = self.prompt_for_outline_confirmation(outline_path)
        
        if not confirmed:
            return None
        
        # Read and parse the outline
        outline_content = self.read_outline(outline_path)
        sections = self.parse_sections(outline_content)
        
        print(f"[ARTICLE WRITER] Outline finalized with {len(sections)} sections.")
        for i, section in enumerate(sections):
            print(f"  {i+1}. {section['title']}")
        
        return sections 