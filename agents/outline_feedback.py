import os
import sys
import time
sys.path.append('..')

class OutlineFeedbackProcessor:
    """
    Agent responsible for managing user feedback on the research outline and coordinating revisions.
    """
    
    def __init__(self):
        """
        Initialize the OutlineFeedbackProcessor.
        """
        pass
    
    def present_outline(self, outline_file):
        """
        Notify the user that the outline is ready for review.
        
        Args:
            outline_file (str): Path to the outline file
            
        Returns:
            None
        """
        print(f"\n[OUTLINE FEEDBACK] Research outline has been generated.")
        print(f"Please review it in the file: {outline_file}")
        print("\nOptions:")
        print("  1. Type 'accept' to proceed with article generation")
        print("  2. Type 'revise' followed by specific instructions to have the AI rewrite the outline")
        print("  3. Edit the file directly and then type 'edited' to confirm your changes")
    
    def prompt_for_feedback(self):
        """
        Ask user if outline is acceptable or needs revision.
        
        Returns:
            dict: Feedback information with action and details
        """
        while True:
            user_input = input("\n> ").strip()
            
            # Check for accept command
            if user_input.lower() == 'accept':
                return {
                    'action': 'accept',
                    'details': None
                }
            
            # Check for edited command
            elif user_input.lower() == 'edited':
                return {
                    'action': 'edited',
                    'details': None
                }
            
            # Check for revise command with instructions
            elif user_input.lower().startswith('revise '):
                revision_instructions = user_input[7:].strip()
                if not revision_instructions:
                    print("Please provide revision instructions after 'revise'.")
                    continue
                    
                return {
                    'action': 'revise',
                    'details': revision_instructions
                }
            
            # Invalid input
            else:
                print("Invalid input. Please type 'accept', 'edited', or 'revise [instructions]'.")
    
    def check_for_file_edits(self, outline_file, last_known_content):
        """
        Check if the user has made manual edits to the outline file.
        
        Args:
            outline_file (str): Path to the outline file
            last_known_content (str): Last known content of the outline
            
        Returns:
            tuple: (has_changes, new_content)
        """
        with open(outline_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        has_changes = current_content != last_known_content
        return has_changes, current_content 