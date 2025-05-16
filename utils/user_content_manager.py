import os
import datetime
import json
import sys
sys.path.append('..')
from agents.analysis import AnalysisAgent
from utils.tweet_extractor import TweetExtractor

# Constants for file size limits (in bytes)
MAX_TEXT_FILE_SIZE = 1 * 1024 * 1024  # 1 MB for text/md files
MAX_PDF_FILE_SIZE = 10 * 1024 * 1024  # 10 MB for PDF files
MAX_CSV_FILE_SIZE = 5 * 1024 * 1024   # 5 MB for CSV files

class UserContentManager:
    def __init__(self):
        self.analysis_agent = None  # Will be initialized on first use
        self.tweet_extractor = TweetExtractor()
    
    def create_directory(self, output_dir):
        """Create and return the user content directory"""
        user_content_dir = os.path.join(output_dir, "user_content")
        os.makedirs(user_content_dir, exist_ok=True)
        return user_content_dir
    
    def prompt_user(self):
        """
        Prompt user for content addition and wait for response
        
        Returns:
            Boolean indicating whether to process user content
        """
        print("\n[USER CONTENT] You can now add your own content to enhance the research.")
        print("Supported file types:")
        print("  - Text files (.txt, .md): Maximum size 1MB")
        print("  - PDF files (.pdf): Maximum size 10MB")
        print("  - CSV files (.csv): Maximum size 5MB")
        print("  - Tweet URLs file (tweets.txt): One URL per line")
        print("\nAdd files to the 'user_content' directory in the output folder.")
        print("Type 'ready' when you've finished adding content, or 'skip' to proceed without adding content.")
        
        while True:
            user_input = input("> ").strip().lower()
            if user_input == 'ready':
                return True
            elif user_input == 'skip':
                return False
            else:
                print("Please type 'ready' when finished or 'skip' to continue without user content.")
    
    def process_content(self, user_content_dir):
        """
        Process all supported files in the directory
        
        Args:
            user_content_dir: Path to user content directory
            
        Returns:
            List of processed content items in the same format as articles/videos
        """
        user_content = []
        
        # Check if directory exists
        if not os.path.exists(user_content_dir):
            print(f"User content directory not found: {user_content_dir}")
            return user_content
        
        # Get all supported files
        files = [f for f in os.listdir(user_content_dir) 
                 if os.path.isfile(os.path.join(user_content_dir, f)) and 
                 f.lower().endswith(('.txt', '.md', '.pdf', '.csv'))]
        
        if not files:
            print("No supported files found in user content directory.")
            return user_content
        
        print(f"\n[USER CONTENT] Found {len(files)} file(s) to process.")
        
        # Check for tweets.txt file
        tweets_file = os.path.join(user_content_dir, "tweets.txt")
        tweet_content = []
        
        if os.path.exists(tweets_file):
            print(f"[TWEET EXTRACTOR] Found tweets.txt file, processing tweet URLs...")
            tweet_content = self.tweet_extractor.extract_tweets_from_file(tweets_file, user_content_dir)
            if tweet_content:
                print(f"[TWEET EXTRACTOR] Successfully processed {len(tweet_content)} tweets")
                user_content.extend(tweet_content)
            else:
                print("[TWEET EXTRACTOR] No tweets were successfully extracted")
        
        # Process each file (excluding tweets.txt which was already processed)
        for filename in files:
            if filename.lower() == "tweets.txt":
                continue  # Skip tweets.txt as it was already processed
                
            file_path = os.path.join(user_content_dir, filename)
            
            # Check file size
            file_size = os.path.getsize(file_path)
            
            # Determine size limit based on file type
            if filename.lower().endswith(('.txt', '.md')):
                max_size = MAX_TEXT_FILE_SIZE
                file_type = "text"
            elif filename.lower().endswith('.pdf'):
                max_size = MAX_PDF_FILE_SIZE
                file_type = "PDF"
            elif filename.lower().endswith('.csv'):
                max_size = MAX_CSV_FILE_SIZE
                file_type = "CSV"
            
            # Skip files that exceed size limit
            if file_size > max_size:
                print(f"Warning: Skipping {filename} - File exceeds maximum {file_type} file size of {max_size/1024/1024:.1f} MB")
                continue
            
            try:
                # Process based on file type
                if filename.lower().endswith(('.txt', '.md')):
                    content_item = self._process_text_file(file_path, filename)
                elif filename.lower().endswith('.pdf'):
                    content_item = self._process_pdf_file(file_path, filename)
                elif filename.lower().endswith('.csv'):
                    content_item = self._process_csv_file(file_path, filename)
                
                if content_item:
                    user_content.append(content_item)
                    print(f"Processed: {filename}")
            except Exception as e:
                print(f"Error processing file {filename}: {e}")
                # Skip silently on error, just log it
        
        return user_content
    
    def _process_text_file(self, file_path, filename):
        """
        Process a text or markdown file
        
        Args:
            file_path: Path to the file
            filename: Name of the file
            
        Returns:
            Processed content item or None if processing failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                print(f"Warning: File is empty: {filename}")
                return None
            
            # Extract title from filename (without extension)
            title = os.path.splitext(filename)[0]
            
            # Initialize analysis agent on first use
            if self.analysis_agent is None:
                self.analysis_agent = AnalysisAgent()
            
            # Extract insights using analysis agent
            insights = self._extract_insights(content)
            
            # Create content entry similar to article/video format
            return {
                'title': title,
                'author': 'User Provided',
                'date': datetime.datetime.now().strftime("%Y-%m-%d"),
                'url': f"file://{file_path}",  # Local file URL
                'relevance_score': 'High',     # Always high relevance
                'relevance_explanation': 'User-provided content is automatically classified as high relevance',
                'key_insights': insights.get('key_insights', ['Content provided by user']),
                'mentioned_projects': insights.get('mentioned_projects', []),
                'thesis_alignment': 'High',    # Always high thesis alignment
                'thesis_alignment_explanation': 'User-provided content is automatically aligned with thesis',
                'text': content[:5000]         # Store truncated content for reference
            }
        except Exception as e:
            print(f"Error in file processing: {e}")
            return None
    
    def _process_pdf_file(self, file_path, filename):
        """
        Process a PDF file and extract text content
        
        Args:
            file_path: Path to the file
            filename: Name of the file
            
        Returns:
            Processed content item or None if processing failed
        """
        try:
            import pdfplumber
            
            text_content = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted_text = page.extract_text() or ""
                    text_content += extracted_text + "\n\n"
            
            # Skip if no text was extracted
            if not text_content.strip():
                print(f"Warning: No text extracted from PDF: {filename}")
                return None
                
            # Extract title from filename (without extension)
            title = os.path.splitext(filename)[0]
            
            # Initialize analysis agent on first use
            if self.analysis_agent is None:
                self.analysis_agent = AnalysisAgent()
            
            # Extract insights using analysis agent
            insights = self._extract_insights(text_content)
            
            # Create content entry similar to article/video format
            return {
                'title': title,
                'author': 'User Provided',
                'date': datetime.datetime.now().strftime("%Y-%m-%d"),
                'url': f"file://{file_path}",  # Local file URL
                'relevance_score': 'High',     # Always high relevance
                'relevance_explanation': 'User-provided content is automatically classified as high relevance',
                'key_insights': insights.get('key_insights', ['Content provided by user']),
                'mentioned_projects': insights.get('mentioned_projects', []),
                'thesis_alignment': 'High',    # Always high thesis alignment
                'thesis_alignment_explanation': 'User-provided content is automatically aligned with thesis',
                'text': text_content[:5000]    # Store truncated content for reference
            }
        except ImportError:
            print(f"Error: pdfplumber library is not installed. Please install it with 'pip install pdfplumber'")
            return None
        except Exception as e:
            print(f"Error processing PDF {filename}: {e}")
            return None
            
    def _process_csv_file(self, file_path, filename):
        """
        Process a CSV file as text
        
        Args:
            file_path: Path to the file
            filename: Name of the file
            
        Returns:
            Processed content item or None if processing failed
        """
        try:
            # Try to read with UTF-8 encoding first
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data_content = f.read()
            except UnicodeDecodeError:
                # Fall back to Latin-1 if UTF-8 fails
                with open(file_path, 'r', encoding='latin-1') as f:
                    data_content = f.read()
                print(f"Note: Used latin-1 encoding for CSV file: {filename}")
            
            # Skip empty files
            if not data_content.strip():
                print(f"Warning: CSV file is empty: {filename}")
                return None
            
            # Extract title from filename (without extension)
            title = os.path.splitext(filename)[0]
            
            # Initialize analysis agent on first use
            if self.analysis_agent is None:
                self.analysis_agent = AnalysisAgent()
            
            # Extract insights with data-specific context
            insights = self._extract_insights_from_data(data_content, title)
            
            return {
                'title': title,
                'author': 'User Provided',
                'date': datetime.datetime.now().strftime("%Y-%m-%d"),
                'url': f"file://{file_path}",  # Local file URL
                'relevance_score': 'High',     # Always high relevance
                'relevance_explanation': 'User-provided data is automatically classified as high relevance',
                'key_insights': insights.get('key_insights', ['Data provided by user']),
                'mentioned_projects': insights.get('mentioned_projects', []),
                'thesis_alignment': 'High',    # Always high thesis alignment
                'thesis_alignment_explanation': 'User-provided data is automatically aligned with thesis',
                'data_content': True,          # Flag as data content
                'text': f"CSV DATA:\n\n{data_content[:5000]}"  # Include CSV preview
            }
        except Exception as e:
            print(f"Error processing CSV file {filename}: {e}")
            return None
    
    def _extract_insights_from_data(self, data_content, title):
        """
        Extract insights from tabular data with specific instruction focus
        
        Args:
            data_content: CSV data as text
            title: Title of the file
            
        Returns:
            Dictionary with key_insights and mentioned_projects
        """
        # Prepare a pseudo-article with tabular data context
        pseudo_article = {
            'title': title,
            'author': 'User',
            'date': datetime.datetime.now().strftime("%Y-%m-%d"),
            'url': 'local://user-content',
            'text': f"CSV DATA TABLE:\n\n{data_content[:8000]}"  # Add context that this is CSV data
        }
        
        # Use existing analysis logic but with a data-oriented search plan
        generic_plan = json.dumps({
            "main_topic": "Cryptocurrency data analysis",
            "keywords": ["data", "analysis", "trends", "statistics"],
            "required_terms": []
        })
        
        try:
            # Run analysis with specific focus on data interpretation
            analysis = self.analysis_agent.analyze_article(pseudo_article, generic_plan)
            
            # If analysis failed, provide defaults
            if not analysis:
                return {
                    'key_insights': ['Data provided by user'],
                    'mentioned_projects': []
                }
            
            return {
                'key_insights': analysis.get('key_insights', ['Data provided by user']),
                'mentioned_projects': analysis.get('mentioned_projects', [])
            }
        except Exception as e:
            print(f"Error extracting insights from data: {e}")
            return {
                'key_insights': ['Error analyzing data content'],
                'mentioned_projects': []
            }
    
    def _extract_insights(self, content):
        """
        Extract key insights from content using the Analysis agent
        
        Args:
            content: Text content to analyze
            
        Returns:
            Dictionary with key_insights and mentioned_projects
        """
        # Prepare a pseudo-article for analysis
        pseudo_article = {
            'title': 'User Content',
            'author': 'User',
            'date': datetime.datetime.now().strftime("%Y-%m-%d"),
            'url': 'local://user-content',
            'text': content[:8000]  # Limit to 8000 chars like in analyze_article
        }
        
        # Use existing analysis logic but with a generic search plan
        generic_plan = json.dumps({
            "main_topic": "User provided content",
            "keywords": [],
            "required_terms": []
        })
        
        try:
            # Run analysis but we only care about insights and projects
            analysis = self.analysis_agent.analyze_article(pseudo_article, generic_plan)
            
            # If analysis failed or returned None, provide defaults
            if not analysis:
                return {
                    'key_insights': ['Content provided by user'],
                    'mentioned_projects': []
                }
            
            return {
                'key_insights': analysis.get('key_insights', ['Content provided by user']),
                'mentioned_projects': analysis.get('mentioned_projects', [])
            }
        except Exception as e:
            print(f"Error extracting insights: {e}")
            return {
                'key_insights': ['Error analyzing content'],
                'mentioned_projects': []
            } 