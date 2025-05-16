import os
import sys
import json
import time
import re
sys.path.append('..')
from config import ARTICLE_FILENAME
from agents.anthropic_client import AnthropicClient

class ArticleWriterAgent:
    """
    Agent responsible for generating article sections based on the outline and research.
    """
    
    def __init__(self, anthropic_client):
        """
        Initialize the ArticleWriterAgent.
        
        Args:
            anthropic_client: Instance of AnthropicClient
        """
        self.anthropic_client = anthropic_client
        self.article_title = ""
        self.article_file = None
        self.article_content = ""
    
    def initialize_article(self, title, query_output_dir):
        """
        Initialize the article file with the title.
        
        Args:
            title (str): The title of the article
            query_output_dir (str): Directory where article will be saved
            
        Returns:
            str: Path to the created article file
        """
        self.article_title = title
        self.article_file = os.path.join(query_output_dir, ARTICLE_FILENAME)
        
        # Create article file with title
        with open(self.article_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
        
        self.article_content = f"# {title}\n\n"
        return self.article_file
    
    def retrieve_relevant_sources(self, section_title, article_results, video_results, user_content, user_content_only=False):
        """
        Gather research materials relevant to a specific section.
        
        Args:
            section_title (str): Title of the section to gather materials for
            article_results (list): List of article results from research
            video_results (list): List of video results from research
            user_content (list): List of user-provided content
            user_content_only (bool): Flag indicating only user content is available
            
        Returns:
            dict: Organized sources by priority
        """
        # Keywords to match from section title (simplified approach)
        keywords = section_title.lower().split()
        
        # Organize sources by priority
        sources = {
            "User Content": [],
            "YouTube": [],
            "High Relevance Articles": [],
            "Medium Relevance Articles": []
        }
        
        # Process user content (highest priority)
        for content in user_content:
            # All user content is included regardless of matching
            sources["User Content"].append(content)
        
        # If we're in user_content_only mode, we skip processing API content
        if not user_content_only:
            # Process YouTube videos
            for video in video_results:
                # Check if any keyword matches the video title or key points
                title = video.get('title', '').lower()
                key_points = ' '.join(video.get('key_points', [])).lower()
                matches = any(keyword in title or keyword in key_points for keyword in keywords)
                
                if video.get('relevance_score') == 'High' or matches:
                    sources["YouTube"].append({
                        'title': video.get('title', 'Untitled Video'),
                        'text': (
                            f"Video by {video.get('channel', 'Unknown')} ({video.get('date', 'Unknown date')})\n"
                            f"Key points: {' '.join(video.get('key_points', ['No key points available']))}\n"
                            f"URL: {video.get('url', 'No URL')}"
                        ),
                        'relevance': video.get('relevance_score', 'Unknown')
                    })
            
            # Process articles
            for article in article_results:
                # Check if any keyword matches the article title or content
                title = article.get('title', '').lower()
                text = article.get('text', '').lower()
                matches = any(keyword in title or keyword in text for keyword in keywords)
                
                if article.get('relevance_score') == 'High' or matches:
                    sources["High Relevance Articles"].append({
                        'title': article.get('title', 'Untitled Article'),
                        'text': article.get('text', 'No content available'),
                        'url': article.get('url', 'No URL'),
                        'relevance': article.get('relevance_score', 'Unknown')
                    })
                elif article.get('relevance_score') == 'Medium':
                    sources["Medium Relevance Articles"].append({
                        'title': article.get('title', 'Untitled Article'),
                        'text': article.get('text', 'No content available'),
                        'url': article.get('url', 'No URL'),
                        'relevance': article.get('relevance_score', 'Unknown')
                    })
        
        # Report on relevant sources found
        total_sources = sum(len(sources[key]) for key in sources)
        print(f"[ARTICLE WRITER] Found {total_sources} relevant sources for section '{section_title}':")
        for key, values in sources.items():
            print(f"  - {key}: {len(values)} items")
        
        return sources
    
    def extract_sources_from_outline(self, section_info):
        """
        Extract specific source references from the outline section.
        
        Args:
            section_info (dict): Information about the section (title, content)
            
        Returns:
            list: List of source indices mentioned in the outline
        """
        source_references = []
        content_lines = section_info['content'].split('\n')
        
        # Regular expression to find source references like [Source 3, Source 7] or [3, 7]
        source_patterns = [
            r'\[Source\s+(\d+(?:\s*,\s*\d+)*)\]',  # [Source 3, Source 7]
            r'\[Sources?\s+(\d+(?:\s*,\s*\d+)*)\]', # [Sources 3, 7]
            r'\[(\d+(?:\s*,\s*\d+)*)\]'             # [3, 7]
        ]
        
        for line in content_lines:
            for pattern in source_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    # Split comma-separated numbers and convert to integers
                    nums = [int(num.strip()) for num in match.split(',')]
                    source_references.extend(nums)
        
        # Remove duplicates and sort
        return sorted(list(set(source_references)))
    
    def filter_section_specific_sources(self, section_info, research_data):
        """
        Filter sources to only include those specifically referenced in the outline.
        If no specific sources are referenced, fall back to keyword matching.
        
        Args:
            section_info (dict): Information about the section (title, content)
            research_data (dict): All research data organized by priority
            
        Returns:
            dict: Filtered research data with only section-relevant sources
        """
        # Extract specific source references from outline
        source_indices = self.extract_sources_from_outline(section_info)
        
        # Always include all user content
        filtered_data = {}
        if "User Content" in research_data:
            filtered_data["User Content"] = research_data["User Content"]
        
        # If we found specific source references
        if source_indices:
            print(f"[ARTICLE WRITER] Found {len(source_indices)} specific source references in outline")
            
            # Create flat list of all sources with their indices
            all_sources = []
            for priority, sources in research_data.items():
                if priority == "User Content":
                    continue  # Already included
                
                for i, source in enumerate(sources):
                    all_sources.append((i + 1, priority, source))  # 1-indexed to match outline references
            
            # Add referenced sources to appropriate categories
            for index, priority, source in all_sources:
                if index in source_indices:
                    if priority not in filtered_data:
                        filtered_data[priority] = []
                    filtered_data[priority].append(source)
        else:
            # Fallback: Use keyword matching if no specific references found
            print("[ARTICLE WRITER] No specific source references found, using keyword matching")
            section_title = section_info['title'].lower()
            section_content = section_info['content'].lower()
            
            # Extract keywords from section title and content
            stop_words = {'and', 'the', 'in', 'of', 'to', 'a', 'for', 'on', 'with', 'as'}
            keywords = []
            
            # Extract potential keywords from title (more important)
            for word in section_title.split():
                if word.lower() not in stop_words and len(word) > 3:
                    keywords.append(word.lower())
            
            # Add keywords from content
            for line in section_content.split('\n'):
                for word in line.split():
                    if word.lower() not in stop_words and len(word) > 3 and word.lower() not in keywords:
                        keywords.append(word.lower())
            
            # For each priority level, filter sources by keywords
            for priority, sources in research_data.items():
                if priority == "User Content":
                    continue  # Already handled
                    
                filtered_sources = []
                for source in sources:
                    title = source.get('title', '').lower()
                    
                    # Check if source title contains any keywords
                    if any(keyword in title for keyword in keywords):
                        filtered_sources.append(source)
                
                if filtered_sources:
                    filtered_data[priority] = filtered_sources
        
        # If we still have too few sources, include high relevance sources anyway
        if sum(len(sources) for _, sources in filtered_data.items() if _ != "User Content") < 3:
            if "High Relevance Articles" in research_data:
                filtered_data["High Relevance Articles"] = research_data["High Relevance Articles"][:5]  # Limit to top 5
        
        # Log source selection results
        for priority, sources in filtered_data.items():
            print(f"[ARTICLE WRITER] Using {len(sources)} {priority} for fact checking")
        
        return filtered_data
    
    def log_source_mapping(self, sources):
        """
        Log a mapping of source indices to their titles for reference.
        
        Args:
            sources (dict): Dictionary of sources organized by priority
        """
        print("[ARTICLE WRITER] Source index mapping:")
        index = 1  # 1-indexed to match outline references
        
        for priority, source_list in sources.items():
            for source in source_list:
                title = source.get('title', 'Untitled')
                print(f"  Source {index}: {title} ({priority})")
                index += 1
    
    def generate_section(self, section_info, research_data, style_materials, previous_content=""):
        """
        Generate a section of the article.
        
        Args:
            section_info (dict): Information about the section (title, content)
            research_data (dict): Research data organized by priority
            style_materials (dict): Writing style materials (samples & instructions)
            previous_content (str): Previous sections of the article
            
        Returns:
            str: Generated section content
        """
        # Prepare system prompt
        system_prompt = "You are a respected crypto analyst with deep technical understanding and market experience. Your writing balances objective analysis with selective personal insights. You're known for delivering information-dense, contrarian perspectives that challenge mainstream views when warranted. Use first-person perspective selectively and naturally, primarily when expressing genuine opinions or relevant experiences. Present balanced analysis that acknowledges both strengths and limitations of projects. Your analysis connects relevant data points to identify patterns others miss, while maintaining a conversational but authoritative tone. When writing, prioritize factual accuracy, information density, and insights that shift reader perspectives."
        
        # Helper function to estimate tokens in text with improved accuracy
        def estimate_tokens(text):
            """More accurate token count estimator based on GPT tokenization rules"""
            # Count words (rough approximation)
            word_count = len(text.split())
            # Count non-space characters
            char_count = len(text.replace(" ", ""))
            # Estimate based on both factors (words are ~1.3 tokens, chars are ~0.25 tokens)
            return int((word_count * 1.3) + (char_count * 0.25)) // 4
        
        # Format writing samples for the prompt
        writing_samples_text = ""
        total_sample_tokens = 0
        samples_added = 0  # Explicit counter for added samples
        sample_token_budget = 30000  # Increased from 15000 to 30000 tokens
        
        if style_materials.get('samples'):
            available_samples = style_materials.get('samples', [])
            print(f"[ARTICLE WRITER] Processing style materials with {len(available_samples)} available samples")
            
            # Log information about each available sample
            for idx, sample in enumerate(available_samples):
                content_length = len(sample.get('content', ''))
                estimated_tokens = estimate_tokens(sample.get('content', ''))
                print(f"[ARTICLE WRITER] Sample {idx+1}: {sample.get('filename', 'Unnamed')} ({content_length} chars, ~{estimated_tokens} tokens)")
            
            # Sort samples by length (shortest first) to maximize variety if we hit token limits
            samples = sorted(available_samples, key=lambda x: len(x.get('content', '')))
            remaining_token_budget = sample_token_budget
            priority_count = min(2, len(samples))  # Try to include at least 2 samples
            
            # First pass: Add the priority samples (ensure we include at least 2 if available)
            for i, sample in enumerate(samples[:priority_count]):
                sample_content = sample.get('content', '')
                estimated_tokens = estimate_tokens(sample_content)
                
                # If we can't fit even one priority sample, truncate it
                if i == 0 and estimated_tokens > sample_token_budget:
                    truncated_length = int((sample_token_budget * 4) * 0.9)  # Convert back to chars, leave room for markers
                    sample_content = sample_content[:truncated_length] + "\n\n[Sample truncated due to length]"
                    estimated_tokens = estimate_tokens(sample_content)
                    print(f"[ARTICLE WRITER] Truncated first sample to fit token budget")
                
                # For large samples that would exceed budget but we want to include (priority samples)
                if samples_added < priority_count and estimated_tokens > remaining_token_budget and remaining_token_budget > 1000:
                    # Calculate how much content we can include
                    chars_to_keep = int((remaining_token_budget * 4) * 0.9)  # 90% of available budget
                    truncated_content = sample_content[:chars_to_keep] + "\n\n[... Sample truncated due to length ...]"
                    truncated_tokens = estimate_tokens(truncated_content)
                    
                    # Add the truncated sample
                    writing_samples_text += f"\n--- Complete Article: {sample.get('filename', 'Unnamed')} (TRUNCATED) ---\n\n"
                    writing_samples_text += truncated_content + "\n\n"
                    total_sample_tokens += truncated_tokens
                    remaining_token_budget -= truncated_tokens
                    samples_added += 1
                    print(f"[ARTICLE WRITER] Added truncated priority sample: {sample.get('filename', 'Unnamed')} ({truncated_tokens} tokens)")
                    continue
                
                # If this is a priority sample and it fits, add it
                if samples_added < priority_count and estimated_tokens <= remaining_token_budget:
                    writing_samples_text += f"\n--- Complete Article: {sample.get('filename', 'Unnamed')} ---\n\n"
                    writing_samples_text += sample_content + "\n\n"
                    total_sample_tokens += estimated_tokens
                    remaining_token_budget -= estimated_tokens
                    samples_added += 1
                    print(f"[ARTICLE WRITER] Added priority sample: {sample.get('filename', 'Unnamed')} ({estimated_tokens} tokens)")
            
            # Second pass: Add additional samples if budget allows
            if samples_added >= priority_count:
                for sample in samples[priority_count:]:
                    sample_content = sample.get('content', '')
                    estimated_tokens = estimate_tokens(sample_content)
                    
                    if estimated_tokens > remaining_token_budget:
                        writing_samples_text += f"\n[Additional samples omitted due to token limitations]"
                        print(f"[ARTICLE WRITER] Skipping sample {sample.get('filename', 'Unnamed')} ({estimated_tokens} tokens) as it would exceed the token budget")
                        break
                        
                    writing_samples_text += f"\n--- Complete Article: {sample.get('filename', 'Unnamed')} ---\n\n"
                    writing_samples_text += sample_content + "\n\n"
                    total_sample_tokens += estimated_tokens
                    remaining_token_budget -= estimated_tokens
                    samples_added += 1
                    print(f"[ARTICLE WRITER] Added additional sample: {sample.get('filename', 'Unnamed')} ({estimated_tokens} tokens)")
            
            # Report on samples used with accurate counter
            print(f"[ARTICLE WRITER] Using {samples_added} complete articles as style samples (~{total_sample_tokens} tokens)")
        
        # Format writing instructions
        writing_instructions_text = style_materials.get('instructions', '')
        
        # Format research materials
        research_materials = ""
        for priority, sources in research_data.items():
            if sources:
                research_materials += f"\n--- {priority} ---\n"
                for i, source in enumerate(sources):
                    research_materials += f"\nSource {i+1}: {source.get('title', 'Untitled')}\n"
                    
                    # Use full source text without truncation
                    source_text = source.get('text', '')
                    
                    research_materials += source_text + "\n"
                    if source.get('url'):
                        research_materials += f"URL: {source.get('url')}\n"
        
        # Prepare sections for the prompt
        samples_section = ""
        if writing_samples_text:
            samples_section = "== WRITING STYLE SAMPLES (YOU MUST MATCH THIS STYLE PRECISELY) ==\n" + writing_samples_text + "\n"
            
        instructions_section = ""
        if writing_instructions_text:
            instructions_section = "== WRITING STYLE INSTRUCTIONS ==\n" + writing_instructions_text + "\n"
        
        # Create the prompt
        prompt = f"""
I need you to write the "{section_info['title']}" section of a cryptocurrency research article.

Here is the outline for this section:
{section_info['content']}

{samples_section}
{instructions_section}
== PREVIOUS ARTICLE CONTENT ==
{previous_content}

== RESEARCH MATERIALS ==
{research_materials}

== TASK ==
Write the "{section_info['title']}" section of the article. Follow these guidelines:
1. Use the writing style from the provided samples, particularly the balanced approach to first-person perspective and the conversational but authoritative tone
2. Follow any specific writing instructions
3. Focus on the outlined section topic
4. Incorporate information from the research materials, prioritizing higher-priority sources
5. Format your response in Markdown with appropriate headings (use h2 for the section title)
6. Maintain continuity with the previous content
7. Make sure your writing is factually accurate, well-organized, and engaging
8. Use first-person perspective selectively and naturally, not in every paragraph
9. If any tweet is included in the sources for this section, refer to it in your text and include the tweet at the end of the section in italics as a placeholder for later screenshot insertion

Write only the content for this section. Format in Markdown.
"""
        
        # Log section generation start
        print(f"[ARTICLE WRITER] Generating section: {section_info['title']}")
        start_time = time.time()
        
        # Get the generated content
        section_content = self.anthropic_client.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4000
        )
        
        # Log section generation completion
        elapsed_time = time.time() - start_time
        print(f"[ARTICLE WRITER] Section generation completed in {elapsed_time:.2f} seconds")
        
        # Ensure section content starts with the proper heading
        if not section_content.strip().startswith("##"):
            section_content = f"## {section_info['title']}\n\n{section_content}"
        
        return section_content
    
    def append_section(self, section_content):
        """
        Append a section to the article file.
        
        Args:
            section_content (str): Content of the section to append
            
        Returns:
            str: Path to the updated article file
        """
        if not self.article_file:
            raise ValueError("Article file not initialized. Call initialize_article() first.")
        
        # Append to file
        with open(self.article_file, 'a', encoding='utf-8') as f:
            f.write(section_content + "\n\n")
        
        # Update in-memory content
        self.article_content += section_content + "\n\n"
        
        return self.article_file
    
    def read_current_article(self):
        """
        Read the current state of the article file.
        
        Returns:
            str: Current content of the article
        """
        if not self.article_file or not os.path.exists(self.article_file):
            return ""
        
        with open(self.article_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.article_content = content
        return content
    
    def generate_and_check_section(self, section_info, research_data, style_materials, fact_checker, previous_content=""):
        """
        Generate a section of the article and verify its factual accuracy.
        
        Args:
            section_info (dict): Information about the section (title, content)
            research_data (dict): Research data organized by priority
            style_materials (dict): Writing style materials (samples & instructions)
            fact_checker (FactCheckerAgent): Instance of the fact checker
            previous_content (str): Previous sections of the article
            
        Returns:
            str: Generated and fact-checked section content
        """
        # Log source mapping for reference
        self.log_source_mapping(research_data)
        
        # Generate the initial section using all research data
        section_content = self.generate_section(
            section_info=section_info,
            research_data=research_data,
            style_materials=style_materials,
            previous_content=previous_content
        )
        
        # Filter sources to only those relevant for this section
        section_specific_sources = self.filter_section_specific_sources(section_info, research_data)
        
        # Log filtered source selection
        total_sources = sum(len(sources) for sources in section_specific_sources.values())
        print(f"[ARTICLE WRITER] Using {total_sources} section-specific sources for fact checking")
        
        # Fact check the section with filtered sources
        print(f"[ARTICLE WRITER] Fact checking section: {section_info['title']}")
        check_results = fact_checker.check_section(
            section_content=section_content,
            sources=section_specific_sources
        )
        
        # Apply corrections if needed
        if not check_results.get('accurate', False):
            print(f"[ARTICLE WRITER] Applying factual corrections to section: {section_info['title']}")
            section_content = fact_checker.suggest_corrections(
                section_content=section_content,
                check_results=check_results
            )
        
        return section_content 