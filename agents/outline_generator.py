import sys
import os
sys.path.append('..')
from config import CLAUDE_QUALITY_MODEL, CLAUDE_FAST_MODEL
import json
import re
import tiktoken
from agents.anthropic_client import AnthropicClient
from utils.logger import get_logger

logger = get_logger(__name__)

class OutlineGeneratorAgent:
    """Agent for generating research article outlines"""
    
    def __init__(self, test_mode=False):
        # Initialize the Anthropic client instead of OpenAI
        self.test_mode = test_mode
        self.anthropic_client = AnthropicClient(test_mode=self.test_mode)
        self.model = CLAUDE_FAST_MODEL if test_mode else CLAUDE_QUALITY_MODEL
        
        # We don't need tiktoken encoding for Claude models
        
    def generate_outline(self, article_results, video_results, user_content=None, query="", thesis_direction=None, output_dir=None, user_content_only=False):
        """
        Generate a research article outline based on data and user content
        
        Args:
            article_results: List of processed article results
            video_results: List of processed video results
            user_content: Optional user provided content
            query: The original search query
            thesis_direction: Optional direction or focus for the research thesis
            output_dir: Directory to save results
            user_content_only: Flag indicating that only user content is available
            
        Returns:
            A string containing the markdown research outline
        """
        logger.info(f"\n[OUTLINE] Generating research article outline for '{query}'...")
        
        # Combine article and video results into a single research results structure
        research_results = {
            'title': query,
            'articles': article_results,
            'videos': video_results
        }
        
        # Format content for the prompt
        formatted_results = self._format_research_results(research_results)
        
        # Format user content if provided
        user_content_text = ""
        if user_content and len(user_content) > 0:
            user_content_text = self._format_user_content(user_content)
        
        # Create the system prompt
        system_prompt = self._create_system_prompt(has_user_content=(user_content is not None), user_content_only=user_content_only)
        
        # Add thesis direction if provided
        thesis_direction_text = ""
        if thesis_direction:
            thesis_direction_text = f"\n# Thesis Direction\n\nThe research should focus on the following direction or perspective: {thesis_direction}\n"
        
        user_prompt = f"""
# Research Query
{query}
{thesis_direction_text}
# Research Results

{formatted_results}

# User Provided Content
{user_content_text if user_content_text else "No user content provided."}
"""
        
        logger.info(f"Generating research article outline using {self.model}...")
        try:
            # Use the Anthropic client to generate the outline
            outline_content = self.anthropic_client.generate_content(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=4000,
                model_override=self.model
            )
            
            # Return the outline content
            return outline_content
            
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            return f"# Research Outline\n\nError generating outline: {e}"
    
    def _format_research_results(self, research_results):
        """Format research results for the prompt"""
        if not research_results:
            return "No research results available."
        
        formatted_content = ""
        
        if 'title' in research_results:
            formatted_content += f"## Research Topic: {research_results['title']}\n\n"
        
        if 'videos' in research_results and research_results['videos']:
            videos = research_results['videos']
            formatted_content += f"### Key Video Sources ({len(videos)})\n\n"
            
            for i, video in enumerate(videos, 1):
                title = video.get('title', 'Untitled')
                author = video.get('author', 'Unknown')
                relevance = video.get('relevance_score', 'Unknown')
                url = video.get('url', '#')
                
                formatted_content += f"{i}. **{title}** by {author} (Relevance: {relevance})\n"
                
                # Add key insights if available
                if 'key_insights' in video and video['key_insights']:
                    formatted_content += "   - Key insights:\n"
                    for insight in video['key_insights'][:3]:  # Limit to top 3
                        formatted_content += f"     - {insight}\n"
                
                formatted_content += "\n"
        
        if 'articles' in research_results and research_results['articles']:
            articles = research_results['articles']
            formatted_content += f"### Key Article Sources ({len(articles)})\n\n"
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', 'Untitled')
                author = article.get('author', 'Unknown')
                relevance = article.get('relevance_score', 'Unknown')
                url = article.get('url', '#')
                
                formatted_content += f"{i}. **{title}** by {author} (Relevance: {relevance})\n"
                
                # Add key insights if available
                if 'key_insights' in article and article['key_insights']:
                    formatted_content += "   - Key insights:\n"
                    for insight in article['key_insights'][:3]:  # Limit to top 3
                        formatted_content += f"     - {insight}\n"
                
                formatted_content += "\n"
        
        return formatted_content
    
    def _format_user_content(self, user_content):
        """
        Format user provided content for the prompt
        
        Args:
            user_content: List of user content items
            
        Returns:
            Formatted user content as a string
        """
        if not user_content:
            return "No user content provided."
        
        formatted_content = f"The user has provided {len(user_content)} content items:\n\n"
        
        for i, content_item in enumerate(user_content, 1):
            title = content_item.get('title', 'Untitled')
            url = content_item.get('url', '')
            file_type = "PDF" if url.lower().endswith('.pdf') else "CSV" if url.lower().endswith('.csv') else "Text"
            
            formatted_content += f"### User Content {i}: {title} ({file_type})\n\n"
            
            # Add key insights if available
            if 'key_insights' in content_item and content_item['key_insights']:
                formatted_content += "#### Key points:\n"
                for insight in content_item['key_insights']:
                    formatted_content += f"- {insight}\n"
                formatted_content += "\n"
            
            # Format content based on file type
            if 'data_content' in content_item and content_item['data_content']:
                # Handle CSV/tabular data content differently
                formatted_content += "#### CSV Data Preview:\n```\n"
                # Get text content, removing the CSV DATA prefix
                csv_content = content_item.get('text', '')
                if csv_content.startswith("CSV DATA:"):
                    csv_content = re.sub(r'^CSV DATA:\s*\n+', '', csv_content)
                
                # Add a readable preview of the data (first few rows)
                lines = csv_content.split('\n')
                preview_lines = 10 if len(lines) > 10 else len(lines)
                formatted_content += '\n'.join(lines[:preview_lines])
                formatted_content += "\n```\n\n"
                formatted_content += "_Note: This is tabular data provided by the user for analysis._\n\n"
            elif url.lower().endswith('.pdf'):
                # Handle PDF content
                formatted_content += "#### Content Preview:\n"
                preview = content_item.get('text', '')[:1500]  # Shorter preview for PDFs
                # Truncate at last complete sentence if possible
                last_sentence = preview.rfind('.')
                if last_sentence > len(preview) * 0.7:  # If we can find a sentence break in the latter part
                    preview = preview[:last_sentence+1]
                formatted_content += f"{preview}...\n\n"
                formatted_content += "_Note: This is PDF content provided by the user._\n\n"
            else:
                # Regular text content
                formatted_content += "#### Content Preview:\n"
                preview = content_item.get('text', '')[:2000]  # More text for regular content
                # Truncate at last complete sentence if possible
                last_sentence = preview.rfind('.')
                if last_sentence > len(preview) * 0.7:  # If we can find a sentence break in the latter part
                    preview = preview[:last_sentence+1]
                formatted_content += f"{preview}...\n\n"
            
            # Add any mentioned projects
            if 'mentioned_projects' in content_item and content_item['mentioned_projects']:
                formatted_content += "#### Mentioned Projects/Entities:\n"
                for project in content_item['mentioned_projects']:
                    formatted_content += f"- {project}\n"
                formatted_content += "\n"
            
            # Add citation info
            formatted_content += f"[User Content {i}: {title}]\n\n"
        
        return formatted_content
    
    def _create_system_prompt(self, has_user_content=False, user_content_only=False):
        """Create the system prompt for the outline generation"""
        system_prompt = """You are an expert cryptocurrency and blockchain researcher tasked with creating a comprehensive research outline.

Your task is to create a detailed, well-structured research outline based on the provided materials. 
This outline will serve as the foundation for a comprehensive article that explores the subject in depth.

Guidelines:
1. Create a logical structure with main numbered sections and subsections (e.g., "## 1. Introduction", "### 1.1 Background")
2. Include key arguments, evidence, and insights from the provided materials
3. Identify the most important themes, debates, and findings
4. Organize information in a flow that tells a coherent story
5. Begin with an introduction that provides context and ends with a conclusion that synthesizes the findings
6. Include SPECIFIC CITATIONS to the source materials where appropriate by adding the source title in square brackets after each point

IMPORTANT: 
- The exact number of sections and subsections should be determined by the research material content
- Choose section titles and organization that best fit the topic and materials
- You are NOT required to follow the example structure literally - it's provided to show the formatting only
- The number of sections and subsections each section has should be based on what makes sense for the content and the research material and user added content we work with

Format the outline in Markdown using the following format and structure:
```
# Research Article Outline: [Title]

## 1. Introduction
- Hook with a contrarian or surprising perspective
- Clear thesis statement with a position, not just topic description
- Brief roadmap of key points that will support the thesis

## 2. [First Main Section Title]
### 2.1 [First Subsection Title]
- Key point with supporting evidence [Source Title]
- Another important point [Source Title]
- Add points as needed based on the content

### 2.2 [Second Subsection Title]
- Key point with supporting evidence [Source Title]
- Another important point [Source Title]
- Add points as needed based on the content

### 2.3 [Third Subsection Title if neeed]

... Additional sections and subsections as needed based on content ...

## N. Conclusion
### N.1 [First Conclusion Subsection]
- Future implications of the findings. What do they mean for the future?

```

When citing sources, use the exact title of the article, video, or user content in square brackets. For example: "- Layer 2 solutions improve scalability [Ethereum Is Winning—So Why Is ETH Still Undervalued?]"

For user-provided content, cite it as [User Content Title]."""

        if user_content_only:
            system_prompt += """

IMPORTANT NOTE: The system did not find any relevant content from Substack or YouTube sources for this query. 
You will ONLY have the user-provided content to work with. This is perfectly fine - your task is to create 
a comprehensive outline based exclusively on the user's own research materials.

SPECIAL INSTRUCTIONS FOR USER-CONTENT-ONLY MODE:
1. Draw exclusively from the user's provided materials to create the outline
2. Be thorough in extracting and organizing information from these materials
3. The user-provided content should be treated as authoritative sources
4. If the user content seems limited, create a logical structure that could be expanded upon
5. Suggest areas where additional research might be valuable, but focus primarily on what is provided"""

        if has_user_content:
            system_prompt += """

For user content integration:
7. Pay special attention to user-provided content, which contains personal research or data
8. Integrate user content with the research materials to create a more comprehensive outline
9. For PDF content, treat it as authoritative source material and reference it accordingly with the title in square brackets
10. For CSV/tabular data, suggest how this data can be used to support key points or create visualizations
11. When mentioning data from CSV files, suggest specific relationships or patterns, and include the CSV filename in square brackets

Additionally, ONLY IF the user added a CSV file to user added content, add a section at the end titled:
```
## Suggested Data Visualizations
- Visualization type: Description of what the visualization would show [CSV Filename]
- Another visualization type: Description of what this would display [CSV Filename]
```"""

        system_prompt += """

CRITICAL: You MUST maintain the exact formatting structure shown above with:
1. Numbered main sections (## 1. Title, ## 2. Title, etc.) - the exact number of sections should be based on the content
2. Numbered subsections (### 1.1 Title, ### 1.2 Title, etc.) - the number of subsections per section should be determined by the content
3. Bullet points for each item within subsections
4. Source citations in square brackets after points where applicable

This specific formatting (not the exact number of sections or subsections) is required for compatibility with our research system."""

        return system_prompt
    
    def revise_outline(self, current_outline, revision_instructions, article_results, video_results, user_content=None, query="", thesis_direction=None):
        """
        Revise the current outline based on user instructions
        
        Args:
            current_outline (str): The current outline text
            revision_instructions (str): User's instructions for revision
            article_results, video_results, user_content: Source materials
            query (str): Original research query
            thesis_direction (str, optional): Thesis guidance
            
        Returns:
            str: Revised outline content
        """
        logger.info(f"\n[OUTLINE] Revising research article outline based on feedback...")
        
        # Format content for the prompt
        formatted_results = self._format_research_results({
            'title': query,
            'articles': article_results,
            'videos': video_results
        })
        
        # Format user content if provided
        user_content_text = ""
        if user_content and len(user_content) > 0:
            user_content_text = self._format_user_content(user_content)
        
        # Create system prompt with the same formatting requirements as the original
        system_prompt = """You are an expert cryptocurrency and blockchain researcher tasked with revising a research outline.

Your task is to revise an existing outline based on user feedback while maintaining the required structure and formatting. 
The outline serves as the foundation for a comprehensive article.

Guidelines:
1. Address the specific revision instructions from the user
2. Maintain the logical structure with main numbered sections and subsections (e.g., "## 1. Introduction", "### 1.1 Background")
3. Include key arguments, evidence, and insights from the provided materials
4. Organize information in a flow that tells a coherent story
5. Include SPECIFIC CITATIONS to the source materials where appropriate by adding the source title in square brackets after each point
6. Where appropriate, include sections that compare different viewpoints or approaches to the topic
7. Consider sections that might suggest forward-looking implications or predictions
8. For each major section, try to identify at least one point that offers a unique insight or perspective

IMPORTANT: 
- Feel free to adjust the number of sections and subsections as appropriate for the content
- You may add or remove sections and subsections based on the revision instructions
- Use your judgment to organize the content most effectively
- The example below shows formatting only, not a required structure

IMPORTANT ABOUT STRUCTURE:
- Do not default to a 5-section structure
- The number of sections should be determined by what makes sense for the specific topic
- Some topics may need 3-4 sections, some may need 5, others may need 6-8 sections
- Example: A simple topic might use [Introduction, Background, Key Developments, Conclusion]
- Example: A complex topic might use [Introduction, Historical Context, Technical Aspects, Regulatory Landscape, Market Adoption, Challenges, Future Outlook, Conclusion]

OUTLINE STRUCTURE TIPS:
- When possible, organize sections to support a clear argument or perspective rather than just categorizing information
- Consider including a "Challenges" or "Limitations" section to provide balanced analysis
- If the topic is controversial, try to include different viewpoints while maintaining a coherent structure
- Where possible, maintain or enhance sections that provide unique insights or perspectives
- Consider if the outline would benefit from sections comparing different approaches or viewpoints

Format the outline in Markdown using the following format:
```
# Research Article Outline: [Title]

## 1. Introduction
- Hook with a contrarian or surprising perspective
- Clear thesis statement with a position, not just topic description
- Brief roadmap of key points that will support the thesis

... Additional sections and subsections as needed ...

## N. Conclusion
### N.1 [First Conclusion Subsection]
- Future implications of the findings. What do they mean for the future?
```

When citing sources, use the exact title of the article, video, or user content in square brackets. For example: "- Layer 2 solutions improve scalability [Ethereum Is Winning—So Why Is ETH Still Undervalued?]"

CRITICAL: You MUST maintain the following formatting elements:
1. Numbered main sections (## 1. Title, ## 2. Title, etc.)
2. Numbered subsections (### 1.1 Title, ### 1.2 Title, etc.)
3. Bullet points for each item within subsections
4. Source citations in square brackets after points where applicable

The exact number and content of sections should be determined by the research material and revision instructions."""
        
        # Create the revision prompt
        user_prompt = f"""
I need you to revise a research outline for a cryptocurrency article based on user feedback.

== ORIGINAL QUERY ==
{query}

== CURRENT OUTLINE ==
{current_outline}

== USER REVISION INSTRUCTIONS ==
{revision_instructions}

== RESEARCH MATERIALS ==
{formatted_results}

== USER PROVIDED CONTENT ==
{user_content_text if user_content_text else "No user content provided."}

== TASK ==
Revise the outline according to the user's feedback. Follow these guidelines:
1. Address all the specific points in the user's feedback
2. Maintain the EXACT SAME FORMAT as the original outline with:
   - Numbered sections (## 1. Title, ## 2. Title)
   - Numbered subsections (### 1.1 Title, ### 1.2 Title)
   - Bullet points for content
   - Source citations in square brackets after points
3. Ensure the revised outline is well-organized and comprehensive
4. Consider all the research materials when making revisions
5. Feel free to adjust the number of sections or subsections based on what makes the most sense for the content

Return only the revised outline content. Do not include explanations or comments about your changes.
"""
        
        try:
            # Use the Anthropic client to generate the revised outline
            revised_outline = self.anthropic_client.generate_content(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=4000,
                model_override=self.model
            )
            
            return revised_outline
            
        except Exception as e:
            logger.error(f"Error revising outline: {e}")
            return current_outline
    
    def save_outline(self, outline_content, output_dir, outline_filename="research_outline.md"):
        """
        Save the outline content to a file
        
        Args:
            outline_content: String containing the outline markdown
            output_dir: Directory to save the outline
            outline_filename: Filename for the outline file
            
        Returns:
            Path to the saved file or None if save failed
        """
        outline_path = os.path.join(output_dir, outline_filename)
        
        try:
            with open(outline_path, 'w', encoding='utf-8') as f:
                f.write(outline_content)
            logger.info(f"Research outline saved to {outline_path}")
            return outline_path
        except Exception as e:
            logger.error(f"Error saving outline: {e}")
            return None 