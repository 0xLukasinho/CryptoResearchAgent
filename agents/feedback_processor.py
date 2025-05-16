import os
import sys
import time
import re
sys.path.append('..')

class FeedbackProcessor:
    """
    Agent responsible for managing user feedback on article sections and coordination revisions.
    """
    
    def __init__(self, debug_mode=True):
        """
        Initialize the FeedbackProcessor.
        
        Args:
            debug_mode (bool): Whether to show detailed debug information
        """
        self.current_section = None
        self.current_section_index = -1
        self.debug_mode = debug_mode
    
    def log_debug(self, message):
        """Helper method to log debug messages if debug mode is enabled"""
        if self.debug_mode:
            print(f"[FEEDBACK] DEBUG: {message}")
    
    def normalize_section_title(self, title, remove_numbers=False):
        """
        Normalize section titles by optionally removing number prefixes.
        
        Args:
            title: The original section title (e.g. "1. Introduction" or "Introduction")
            remove_numbers: Whether to remove number prefixes
        
        Returns:
            Normalized title (e.g. "Introduction" if remove_numbers=True)
        """
        if remove_numbers:
            # Remove patterns like "1. ", "1.1. ", etc.
            return re.sub(r'^\s*\d+(?:\.\d+)*\.\s+', '', title)
        return title
    
    def find_section_boundaries(self, article_content, section_title):
        """
        Find the start and end of a section with flexible matching.
        
        Args:
            article_content: Full article text
            section_title: Title to search for (may include numbers)
            
        Returns:
            (start_line, end_line) tuple or (-1, -1) if not found
        """
        lines = article_content.split('\n')
        # Normalize the section title (remove numbers if present)
        normalized_title = self.normalize_section_title(section_title, remove_numbers=True)
        
        self.log_debug(f"Looking for section: '{section_title}'")
        self.log_debug(f"Normalized title: '{normalized_title}'")
        
        # Try multiple patterns in order of specificity
        patterns = [
            # Exact match as provided
            re.compile(fr'^\s*##\s+{re.escape(section_title)}', re.IGNORECASE),
            # Match without numbers
            re.compile(fr'^\s*##\s+{re.escape(normalized_title)}', re.IGNORECASE),
            # Match with numbers (if original didn't have numbers but article has them)
            re.compile(fr'^\s*##\s+\d+\.\s+{re.escape(normalized_title)}', re.IGNORECASE),
            # Fuzzy match (for titles that might have small variations)
            re.compile(fr'^\s*##\s+.*{re.escape(normalized_title)}.*', re.IGNORECASE)
        ]
        
        # Find start line
        section_start = -1
        section_pattern_used = None
        for i, line in enumerate(lines):
            for pattern in patterns:
                if pattern.match(line):
                    section_start = i
                    section_pattern_used = pattern
                    self.log_debug(f"Found section start at line {i+1}: '{line}'")
                    self.log_debug(f"Using pattern: {pattern.pattern}")
                    break
            if section_start >= 0:
                break
        
        # If we still can't find the section, try a more lenient approach with keywords
        if section_start < 0:
            self.log_debug(f"Trying keyword matching as fallback")
            keywords = normalized_title.split()
            # Only use significant keywords (longer than 3 chars)
            keywords = [k for k in keywords if len(k) > 3]
            
            if keywords:
                for i, line in enumerate(lines):
                    if line.startswith('##') and any(k.lower() in line.lower() for k in keywords):
                        section_start = i
                        self.log_debug(f"Found section by keyword at line {i+1}: '{line}'")
                        break
        
        # If found, find the end (next section or end of file)
        if section_start >= 0:
            any_section_pattern = re.compile(r'^\s*##\s+')
            section_end = len(lines) - 1
            for i in range(section_start + 1, len(lines)):
                if any_section_pattern.match(lines[i]):
                    section_end = i - 1
                    self.log_debug(f"Found section end at line {i+1}")
                    break
            return (section_start, section_end)
        
        return (-1, -1)
    
    def present_section(self, section_title, article_file):
        """
        Notify the user that a section is ready for review.
        
        Args:
            section_title (str): Title of the section
            article_file (str): Path to the article file
            
        Returns:
            None
        """
        self.current_section = section_title
        
        print(f"\n[FEEDBACK] Section '{section_title}' has been written.")
        print(f"Please review it in the article file: {article_file}")
        print("\nOptions:")
        print("  1. Type 'accept' to proceed to the next section")
        print("  2. Type 'revise' followed by specific instructions to have the AI rewrite the section")
        print("  3. Edit the file directly and then type 'edited' to confirm your changes")
    
    def prompt_for_feedback(self):
        """
        Ask user if section is acceptable or needs revision.
        
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
    
    def check_for_file_edits(self, article_file, last_known_content):
        """
        Check if the user has made manual edits to the article file.
        
        Args:
            article_file (str): Path to the article file
            last_known_content (str): Last known content of the article
            
        Returns:
            tuple: (has_changes, new_content)
        """
        with open(article_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        has_changes = current_content != last_known_content
        return has_changes, current_content
    
    def process_revision_request(self, feedback, article_writer, section_info, research_data, style_materials, fact_checker, previous_content):
        """
        Process a revision request from the user.
        
        Args:
            feedback (dict): Feedback information with action and details
            article_writer (ArticleWriterAgent): The article writer agent
            section_info (dict): Information about the section
            research_data (dict): Research data for the section
            style_materials (dict): Writing style materials
            fact_checker (FactCheckerAgent): The fact checker agent
            previous_content (str): Previous content of the article
            
        Returns:
            str: Revised section content
        """
        # Extract revision instructions
        revision_instructions = feedback.get('details', '')
        
        # Prepare system prompt
        system_prompt = "You are an expert article writer specializing in cryptocurrency research. Your task is to revise a section based on user feedback."
        
        # Create the prompt
        prompt = f"""
I need you to revise the "{section_info['title']}" section of a cryptocurrency research article based on user feedback.

== CURRENT SECTION CONTENT ==
{section_info.get('current_content', '')}

== USER FEEDBACK ==
{revision_instructions}

== SECTION OUTLINE ==
{section_info['content']}

== RESEARCH MATERIALS ==
[Research materials available but omitted for brevity]

== WRITING STYLE ==
[Style information available but omitted for brevity]

== TASK ==
Revise the section according to the user's feedback. Follow these guidelines:
1. Address all the specific points in the user's feedback
2. Maintain the existing writing style
3. Keep the section factually accurate
4. Format your response in Markdown with appropriate headings

IMPORTANT: DO NOT use triple backticks (```) in your response. These can cause formatting issues.

Write only the revised content for this section. Do not include explanations about your changes or comments about the writing process.
"""
        
        # Log revision process
        print(f"[FEEDBACK] Generating revision for section '{section_info['title']}'")
        start_time = time.time()
        
        # Generate the revised content
        revised_content = article_writer.anthropic_client.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4000
        )
        
        # Remove any triple backticks if present
        revised_content = self.clean_backticks(revised_content)
        
        # Log completion
        elapsed_time = time.time() - start_time
        print(f"[FEEDBACK] Revision generated in {elapsed_time:.2f} seconds")
        
        # Fact check the revised content
        print(f"[FEEDBACK] Fact checking revised content")
        check_results = fact_checker.check_section(
            section_content=revised_content,
            sources=research_data
        )
        
        # Apply corrections if needed
        if not check_results.get('accurate', False):
            print(f"[FEEDBACK] Applying factual corrections to revised content")
            revised_content = fact_checker.suggest_corrections(
                section_content=revised_content,
                check_results=check_results
            )
            
            # Clean up backticks again after fact checking
            revised_content = self.clean_backticks(revised_content)
        
        return revised_content
        
    def clean_backticks(self, content):
        """
        Remove triple backticks from content that might cause formatting issues.
        
        Args:
            content (str): Content that may contain backticks
            
        Returns:
            str: Cleaned content
        """
        # Handle nested markdown blocks by removing triple backticks (ensure they're properly balanced)
        if content.count('```') >= 2:
            # Only remove backticks that are likely wrapper backticks
            first_backtick = content.find('```')
            last_backtick = content.rfind('```')
            
            if first_backtick == 0 or (first_backtick > 0 and content[first_backtick-1] in ['\n', ' ']):
                content = content[:first_backtick] + content[first_backtick+3:]
                
            # Find the new last position after removing the first
            last_backtick = content.rfind('```')
            if last_backtick > 0 and (last_backtick + 3 == len(content) or content[last_backtick+3] in ['\n', ' ']):
                content = content[:last_backtick] + content[last_backtick+3:]
        
        # Check for incomplete code blocks
        if content.count('```') % 2 != 0:
            # Remove all remaining backticks to avoid unpaired backticks
            content = content.replace('```', '')
        
        return content 