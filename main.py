import argparse
import sys
import pandas as pd
import json
import os
import re
import traceback
from config import CSV_PATH, YOUTUBE_CSV_PATH, OUTPUT_DIR, OUTLINE_FILE_NAME, CLOUDCONVERT_API_KEY
from utils.csv_handler import load_substack_data
from utils.article_filter import contains_all_required_terms
from agents.coordinator import CoordinatorAgent
from agents.database_search import DatabaseSearchAgent
from agents.article_retrieval import ArticleRetrievalAgent
from agents.analysis import AnalysisAgent
from agents.summarization import SummarizationAgent
from agents.youtube_search import YouTubeAgent
from agents.outline_generator import OutlineGeneratorAgent
from utils.user_content_manager import UserContentManager
from agents.outline_finalizer import OutlineFinalizerAgent
from agents.anthropic_client import AnthropicClient
from utils.directory_setup import setup_article_writer_directories
from agents.style_learning import StyleLearningAgent
from agents.article_writer import ArticleWriterAgent
from agents.fact_checker import FactCheckerAgent
from agents.feedback_processor import FeedbackProcessor
from agents.outline_feedback import OutlineFeedbackProcessor
from agents.cloud_convert import CloudConvertClient

def get_unique_directory_name(base_path):
    """
    Generate a unique directory name by adding a version number if the directory already exists.
    
    Args:
        base_path: The base directory path to check
        
    Returns:
        A unique directory path
    """
    if not os.path.exists(base_path):
        return base_path
    
    counter = 1
    while True:
        new_path = f"{base_path} ({counter})"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def main():
    parser = argparse.ArgumentParser(description='Crypto Research Agent System')
    parser.add_argument('query', nargs='+', help='Your research query')
    
    # Mode selection arguments
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--test', action='store_true', help='Run in test mode (stops after finding 2 relevant items)')
    mode_group.add_argument('--search', action='store_true', help='Run in search mode (find and analyze content but do not generate outline)')
    
    # Other arguments
    parser.add_argument('--youtube', action='store_true', help='Search YouTube only')
    parser.add_argument('--substack', action='store_true', help='Search Substacks only')
    parser.add_argument('--thesis', type=str, help='Direction or focus for the research article thesis')
    parser.add_argument('--max-age', type=int, 
        help='Only include articles newer than specified number of days')
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Combine query words into a single string
    query = ' '.join(args.query)
    test_mode = args.test
    search_mode = args.search
    thesis_direction = args.thesis
    
    # Determine search mode
    search_youtube = args.youtube or not args.substack
    search_substack = args.substack or not args.youtube
    if args.youtube and args.substack:
        search_youtube = True
        search_substack = True
    
    print("\n===== CRYPTO RESEARCH AGENT SYSTEM =====")
    print(f"Researching: '{query}'")
    
    if thesis_direction:
        print(f"Thesis Direction: '{thesis_direction}'")
    
    if search_youtube and search_substack:
        print("Source: Searching both YouTube and Substacks")
    elif search_youtube:
        print("Source: Searching YouTube only")
    else:
        print("Source: Searching Substacks only")
    
    # Display run mode
    if test_mode:
        print("MODE: TESTING - Will stop after finding 2 relevant items per source")
    elif search_mode:
        print("MODE: SEARCH ONLY - Will find and analyze content but not generate outline")
    else:
        print("MODE: FULL - Complete research with outline generation")
    print("\n")
    
    # Step 1: Initialize coordinator and get research plan
    coordinator = CoordinatorAgent()
    print("\n[COORDINATOR] Planning research approach...")
    search_plan_json = coordinator.ask(query)
    print(f"Research Plan:\n{search_plan_json}\n")
    
    # Parse the JSON string to extract required terms
    try:
        search_plan = json.loads(search_plan_json)
        required_terms = search_plan.get('required_terms', [])
        print(f"Required terms that MUST appear in content: {required_terms}")
        
        # Debug: Verify the required_terms format and content
        print(f"[DEBUG] Required terms type: {type(required_terms)}")
        print(f"[DEBUG] Required terms value: {required_terms}")
        
        # Ensure required_terms is a list of strings
        if required_terms and not isinstance(required_terms, list):
            print(f"[DEBUG] Converting required_terms to list: {required_terms}")
            required_terms = [str(required_terms)]
        elif required_terms:
            # Ensure all items are strings and non-empty
            required_terms = [str(term) for term in required_terms if term]
            print(f"[DEBUG] Sanitized required_terms: {required_terms}")
    except:
        print("Warning: Unable to parse search plan as JSON. Proceeding without required terms.")
        required_terms = []
        search_plan = search_plan_json
    
    # Create search-specific output directory
    # Clean query for directory name
    query_dir_name = query.replace(' ', '_')[:30].replace('/', '_').replace('\\', '_')
    base_query_output_dir = os.path.join(OUTPUT_DIR, query_dir_name)
    
    # Get a unique directory name by adding a version number if needed
    query_output_dir = get_unique_directory_name(base_query_output_dir)
    os.makedirs(query_output_dir, exist_ok=True)
    
    # Variables to store results
    article_results = []
    video_results = []
    
    # Step 2: Substack search if enabled
    if search_substack:
        print("\n[SUBSTACK] Starting Substack search...")
        
        # Load Substack data
        substack_data = load_substack_data(CSV_PATH)
        if substack_data is None:
            print("Failed to load Substack database. Skipping Substack search.")
        else:
            # Initialize Substack agents
            db_search = DatabaseSearchAgent()
            retrieval = ArticleRetrievalAgent()
            analysis = AnalysisAgent()
            
            # Find and process Substacks
            urls = db_search.search(query, search_plan, substack_data)
            if urls:
                print(f"Found {len(urls)} relevant Substacks")
                
                # Retrieve articles
                all_articles = retrieval.process_urls(
                    urls, 
                    search_plan, 
                    test_mode=test_mode and not search_mode,  # Only limit articles in test mode, not search mode
                    max_age_days=args.max_age
                )
                if all_articles:
                    print(f"Retrieved {len(all_articles)} articles")
                    
                    # Pre-filter articles
                    print("\n[FILTER] Pre-filtering articles based on required terms...")
                    filtered_articles = []
                    filtered_out = 0
                    
                    for article in all_articles:
                        title = article.get('title', 'Unknown')
                        if contains_all_required_terms(article, required_terms):
                            filtered_articles.append(article)
                            print(f"ACCEPTED: '{title}' - contains all required terms")
                        else:
                            filtered_out += 1
                            print(f"FILTERED OUT: '{title}' - missing required terms")
                    
                    print(f"Pre-filtering complete: {len(filtered_articles)} articles accepted, {filtered_out} filtered out")
                    
                    if filtered_articles:
                        # Analyze articles
                        print("\n[ANALYSIS] Analyzing articles for relevance...")
                        analyzed_articles = analysis.analyze_articles(filtered_articles, search_plan, thesis_direction, test_mode)
                        
                        # Count by relevance
                        high_rel = sum(1 for a in analyzed_articles if a and a.get('relevance_score') == 'High')
                        med_rel = sum(1 for a in analyzed_articles if a and a.get('relevance_score') == 'Medium')
                        low_rel = sum(1 for a in analyzed_articles if a and a.get('relevance_score') == 'Low')
                        non_english = sum(1 for a in analyzed_articles if a is None)
                        
                        print(f"Article analysis complete: {high_rel} high relevance, {med_rel} medium relevance, {low_rel} low relevance")
                        if non_english > 0:
                            print(f"Non-English content filtered: {non_english} articles")
                        
                        # Store only medium and high relevance articles
                        article_results.extend([a for a in analyzed_articles if a and a.get('relevance_score') in ['High', 'Medium']])
                    else:
                        print("No articles passed the keyword filter.")
    
    # Step 3: YouTube search if enabled
    if search_youtube:
        print("\n[YOUTUBE] Starting YouTube search...")
        
        # Debug log required terms before YouTube search
        print(f"[YOUTUBE SEARCH] DEBUG: Required terms before YouTube search: {required_terms}")
        print(f"[YOUTUBE SEARCH] DEBUG: Required terms type: {type(required_terms)}")
        
        # Load YouTube data
        youtube_agent = YouTubeAgent()
        
        if not os.path.exists(YOUTUBE_CSV_PATH):
            print("Failed to load YouTube channel database. Skipping YouTube search.")
        else:
            # Search YouTube channels
            video_results = youtube_agent.search(
                query=query, 
                required_terms=required_terms, 
                max_results=5,  # Fixed max_results parameter 
                max_age_days=args.max_age,
                test_mode=test_mode and not search_mode,  # Only limit videos in test mode, not search mode
                output_dir=query_output_dir  # Pass the output directory for transcripts
            )
            
            # Debug log video results
            print(f"[YOUTUBE SEARCH] DEBUG: Received {len(video_results)} videos from YouTube search")
            for i, video in enumerate(video_results[:3]):  # Show first 3 videos
                print(f"[YOUTUBE SEARCH] DEBUG: Video {i+1}: {video.get('title', 'No title')}")
                # Print video properties to help diagnose relevance issues
                print(f"   - Relevance Score: {video.get('relevance_score', 'Not scored')}")
                print(f"   - Has Transcript: {'Yes' if video.get('transcript_text') else 'No'}")
                if required_terms:
                    # Check if title/description contains required terms
                    content = f"{video.get('title', '')} {video.get('description', '')}"
                    has_required_terms = all(term.lower() in content.lower() for term in required_terms)
                    print(f"   - Contains All Required Terms: {'Yes' if has_required_terms else 'No'}")
                    
                    # If transcript is available, check that too
                    if video.get('transcript_text'):
                        transcript_has_terms = all(term.lower() in video.get('transcript_text', '').lower() for term in required_terms)
                        print(f"   - Transcript Contains All Required Terms: {'Yes' if transcript_has_terms else 'No'}")
    
    # Step 4: Generate final report
    api_content_found = bool(article_results or video_results)
    
    if not api_content_found:
        print("\n[NOTICE] No relevant content found from Substack or YouTube sources.")
        print("You have two options:")
        print("  1. Terminate the process and try with different search terms")
        print("  2. Continue and add your own research materials to create content")
        
        choice = ""
        while choice not in ["1", "2"]:
            choice = input("Enter your choice (1 or 2): ").strip()
        
        if choice == "1":
            print("Process terminated by user. Try again with different search terms.")
            sys.exit(0)
        else:
            print("\n[PROCEEDING] Continuing with user-provided content only.")
    
    # Only run summarization if API content was found
    if api_content_found:
        # Initialize summarization agent
        summarization = SummarizationAgent()
        
        # Create final report
        print("\n[SUMMARY] Creating final markdown report...")
        final_report = summarization.summarize_combined_results(article_results, video_results, search_plan, query, thesis_direction)
        
        # Save results to markdown file
        filename = os.path.join(query_output_dir, f"research_results.md")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(final_report)
        
        print(f"\nResults saved to {filename}")
        
        # Print info about transcripts
        transcript_dir = os.path.join(query_output_dir, "transcripts")
        if os.path.exists(transcript_dir) and os.listdir(transcript_dir):
            print(f"Transcripts saved to {transcript_dir}")
    else:
        print("\n[SUMMARY] Skipping research results summary as no API content was found.")
    
    # Skip user content and outline generation in search mode
    if search_mode:
        print("\n[SEARCH MODE] Search and analysis complete. Skipping user content and outline generation.")
        if api_content_found:
            print(f"\nResults saved to {filename}")
        sys.exit(0)
    
    # Step 4.5: User Content Integration
    print("\n[USER CONTENT] Preparing for user content integration...")
    user_manager = UserContentManager()
    user_content_dir = user_manager.create_directory(query_output_dir)
    print(f"User content directory created at: {user_content_dir}")
    
    if user_manager.prompt_user():
        print("\n[USER CONTENT] Processing user-provided content...")
        user_content = user_manager.process_content(user_content_dir)
        print(f"Processed {len(user_content)} user-provided files")
    else:
        print("Skipping user content analysis.")
        user_content = []
    
    # Step 5: Generate research article outline
    print("\n[OUTLINE] Generating research article outline...")
    try:
        outline_agent = OutlineGeneratorAgent(test_mode=test_mode)
        outline = outline_agent.generate_outline(
            article_results,
            video_results,
            user_content,  # Add user content as parameter
            query,
            thesis_direction=thesis_direction,
            output_dir=query_output_dir,
            user_content_only=not api_content_found  # Pass flag to indicate only user content is available
        )
        
        # Save outline to file
        outline_path = outline_agent.save_outline(outline, query_output_dir, OUTLINE_FILE_NAME)
        if outline_path:
            print(f"Research outline saved to {outline_path}")
        else:
            print("Failed to save research outline.")
            
        # Skip article writing in search mode
        if search_mode:
            print("\n[SEARCH MODE] Search and analysis complete. Skipping user content and outline generation.")
            print(f"\nResults saved to {filename}")
            sys.exit(0)
        
        # Initialize article writer components
        try:
            # Set up necessary directories
            setup_article_writer_directories()
            
            # Initialize Anthropic client
            anthropic_client = AnthropicClient(test_mode=test_mode)
            
            # Initialize outline feedback processor
            outline_feedback = OutlineFeedbackProcessor()
            
            # Read the initial outline content for comparison
            with open(outline_path, 'r', encoding='utf-8') as f:
                original_outline_content = f.read()
            
            current_outline_content = original_outline_content
                
            # Present the outline to the user for feedback
            outline_feedback.present_outline(outline_path)
            
            # Feedback loop for the outline
            while True:
                # Get user feedback
                feedback = outline_feedback.prompt_for_feedback()
                
                # User accepts the outline
                if feedback['action'] == 'accept':
                    print(f"[OUTLINE FEEDBACK] Outline accepted. Proceeding to article generation.")
                    break
                
                # User has edited the file
                elif feedback['action'] == 'edited':
                    # Check for changes
                    has_changes, new_content = outline_feedback.check_for_file_edits(
                        outline_file=outline_path,
                        last_known_content=current_outline_content
                    )
                    
                    if has_changes:
                        print(f"[OUTLINE FEEDBACK] Manual edits detected and accepted.")
                        current_outline_content = new_content
                        break
                    else:
                        print(f"[OUTLINE FEEDBACK] No changes detected in the file. Please make your edits and save the file, or choose another option.")
                
                # User wants the AI to revise the outline
                elif feedback['action'] == 'revise':
                    print(f"[OUTLINE FEEDBACK] Processing revision request")
                    
                    # Generate revised outline
                    revised_outline = outline_agent.revise_outline(
                        current_outline=current_outline_content,
                        revision_instructions=feedback['details'],
                        article_results=article_results,
                        video_results=video_results,
                        user_content=user_content,
                        query=query,
                        thesis_direction=thesis_direction
                    )
                    
                    # Update the outline file with the revised content
                    with open(outline_path, 'w', encoding='utf-8') as f:
                        f.write(revised_outline)
                    
                    # Update current content
                    current_outline_content = revised_outline
                    
                    print(f"[OUTLINE FEEDBACK] Outline has been revised and updated.")
                    print(f"Please review the revised outline in the same file: {outline_path}")
            
            # Initialize outline finalizer
            outline_finalizer = OutlineFinalizerAgent()
            
            # Parse the finalized outline to extract sections
            sections = outline_finalizer.parse_sections(current_outline_content)
            
            if not sections:
                print("\n[ARTICLE WRITER] No valid sections found in outline. Exiting.")
                sys.exit(0)
            
            print(f"[ARTICLE WRITER] Outline finalized with {len(sections)} sections.")
            for i, section in enumerate(sections):
                print(f"  {i+1}. {section['title']}")
            
            # Initialize style learning agent
            style_learning = StyleLearningAgent()
            
            # Prompt user to add writing samples and instructions
            if not style_learning.prompt_for_samples():
                print("\n[ARTICLE WRITER] Style learning cancelled. Exiting.")
                sys.exit(0)
            
            # Get raw style materials
            style_materials = style_learning.get_raw_style_materials()
            
            # Verify style samples are correctly loaded
            if style_materials and 'samples' in style_materials:
                print(f"[MAIN] Verifying style samples: {len(style_materials['samples'])} samples loaded")
                for sample in style_materials['samples']:
                    print(f"[MAIN] Sample file: {sample.get('filename', 'Unknown')}, size: {len(sample.get('content', ''))} chars")
            else:
                print("[MAIN] Warning: No style samples were loaded")
            
            # Initialize article writer
            article_writer = ArticleWriterAgent(anthropic_client)
            
            # Initialize fact checker
            fact_checker = FactCheckerAgent(anthropic_client)
            
            # Initialize feedback processor
            feedback_processor = FeedbackProcessor()
            
            # Initialize article with title from query
            article_file = article_writer.initialize_article(query, query_output_dir)
            print(f"[ARTICLE WRITER] Created article file: {article_file}")
            
            # Track the full article content for context
            full_article_content = article_writer.read_current_article()
            
            # Process each section
            print(f"\n[ARTICLE WRITER] Ready to generate {len(sections)} sections")
            
            # Loop through each section
            for i, section in enumerate(sections):
                section_title = section['title']
                print(f"\n[ARTICLE WRITER] Processing section {i+1}/{len(sections)}: {section_title}")
                
                # Gather relevant sources for this section
                section_sources = article_writer.retrieve_relevant_sources(
                    section_title=section_title,
                    article_results=article_results,
                    video_results=video_results,
                    user_content=user_content,
                    user_content_only=not api_content_found  # Pass flag to indicate only user content is available
                )
                
                # Generate and fact-check the section
                section_content = article_writer.generate_and_check_section(
                    section_info=section,
                    research_data=section_sources,
                    style_materials=style_materials,
                    fact_checker=fact_checker,
                    previous_content=full_article_content
                )
                
                # Append to article file
                article_writer.append_section(section_content)
                
                # Update full article content
                full_article_content = article_writer.read_current_article()
                
                # Present the section to the user for feedback
                feedback_processor.present_section(section_title, article_file)
                
                # Feedback loop for this section
                while True:
                    # Get user feedback
                    feedback = feedback_processor.prompt_for_feedback()
                    
                    # User accepts the section
                    if feedback['action'] == 'accept':
                        print(f"[FEEDBACK] Section '{section_title}' accepted. Moving to next section.")
                        break
                    
                    # User has edited the file
                    elif feedback['action'] == 'edited':
                        # Check for changes
                        has_changes, new_content = feedback_processor.check_for_file_edits(
                            article_file=article_file,
                            last_known_content=full_article_content
                        )
                        
                        if has_changes:
                            print(f"[FEEDBACK] Manual edits detected and accepted.")
                            full_article_content = new_content
                            break
                        else:
                            print(f"[FEEDBACK] No changes detected in the file. Please make your edits or choose another option.")
                    
                    # User wants the AI to revise the section
                    elif feedback['action'] == 'revise':
                        # Add current content to section info for reference
                        section_with_content = section.copy()
                        section_with_content['current_content'] = section_content
                        
                        # Generate revised content
                        revised_content = feedback_processor.process_revision_request(
                            feedback=feedback,
                            article_writer=article_writer,
                            section_info=section_with_content,
                            research_data=section_sources,
                            style_materials=style_materials,
                            fact_checker=fact_checker,
                            previous_content=full_article_content
                        )
                        
                        # Replace section in the article file
                        # Read current article content
                        current_article_lines = full_article_content.split('\n')
                        
                        # Print debug info
                        print(f"\n[FEEDBACK] DEBUG: Searching for section '{section_title}'")
                        
                        # Use the new improved section boundary detection
                        section_start, section_end = feedback_processor.find_section_boundaries(
                            article_content=full_article_content, 
                            section_title=section_title
                        )
                        
                        # Debug: Show first few lines of content for troubleshooting
                        feedback_processor.log_debug("First few lines of article:")
                        for i, line in enumerate(current_article_lines[:min(10, len(current_article_lines))]):
                            feedback_processor.log_debug(f"Line {i+1}: {line}")
                        
                        # If we found the section
                        if section_start >= 0 and section_end >= 0:
                            # Ensure the revised content has the proper section heading
                            any_section_pattern = re.compile(r'^\s*##\s+')
                            if not any_section_pattern.match(revised_content):
                                # Add the section heading if it's missing
                                revised_content = f"## {feedback_processor.normalize_section_title(section_title, remove_numbers=True)}\n\n{revised_content}"
                                feedback_processor.log_debug("Added section heading to revised content")
                                
                            # Create new article content
                            new_content = '\n'.join(current_article_lines[:section_start])
                            new_content += '\n' + revised_content + '\n'
                            if section_end < len(current_article_lines) - 1:
                                new_content += '\n' + '\n'.join(current_article_lines[section_end+1:])
                            
                            # Write to file
                            with open(article_file, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            
                            # Update full article content
                            full_article_content = new_content
                            section_content = revised_content
                            
                            print(f"[FEEDBACK] Section revised and updated in the article.")
                            
                            # Present the revised section for feedback again
                            feedback_processor.present_section(section_title, article_file)
                        else:
                            print(f"[FEEDBACK] Error: Could not locate section boundaries in the article.")
                            feedback_processor.log_debug(f"Section boundaries - start: {section_start}, end: {section_end}")
                            
                            # Provide recovery options
                            print("\n[FEEDBACK] Recovery options:")
                            print("1. Type 'accept' to skip this section and move to the next one")
                            print("2. Edit the file directly to make your changes, then type 'edited'")
                            print("3. Type 'full' to replace the entire article with the revised content (use with caution)")
                            
                            recovery_choice = input("[FEEDBACK] Recovery option > ").strip().lower()
                            
                            if recovery_choice == 'full':
                                # Replace entire article content
                                feedback_processor.log_debug("Using full content replacement as recovery")
                                with open(article_file, 'w', encoding='utf-8') as f:
                                    f.write(revised_content)
                                
                                # Update tracking variables
                                full_article_content = revised_content
                                section_content = revised_content
                                
                                print(f"[FEEDBACK] Entire article replaced with revised content.")
                                feedback_processor.present_section(section_title, article_file)
            
            # Article completion
            print("\n[ARTICLE WRITER] 🎉 Article generation complete!")
            print(f"Your article is available at: {article_file}")
            
            # Convert article to DOCX using CloudConvert
            try:
                print("\n[DOCX CONVERSION] Converting article to Microsoft Word format...")
                cloud_convert = CloudConvertClient(CLOUDCONVERT_API_KEY)
                docx_file = cloud_convert.convert_markdown_to_docx(article_file)
                print(f"[DOCX CONVERSION] Word document created: {docx_file}")
            except Exception as e:
                print(f"[DOCX CONVERSION] Error converting to DOCX: {e}")
                print("[DOCX CONVERSION] The markdown article is still available.")
            
        except Exception as e:
            print(f"Error in article writing process: {e}")
            traceback.print_exc()
            
    except Exception as e:
        print(f"Error generating outline: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()