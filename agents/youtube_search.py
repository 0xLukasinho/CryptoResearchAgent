import sys
sys.path.append('..')
from config import SUPADATA_MAX_TRANSCRIPTS
from agents.claude_agent_base import ClaudeAgentBase
from utils.youtube_api import YouTubeAPIClient
import pandas as pd
import json
import os
import re
import time
import requests
import datetime

class YouTubeAgent(ClaudeAgentBase):
    """
    Agent for searching YouTube channels, filtering videos by required terms,
    and retrieving transcripts for relevant videos.
    """

    def __init__(self, youtube_channels_csv="input/YouTubes.csv"):
        """
        Initialize the YouTube agent.

        Args:
            youtube_channels_csv (str): Path to CSV file containing YouTube channel data
        """
        super().__init__()
        self.api_client = YouTubeAPIClient()
        self.transcript_count = 0
        self.youtube_channels_csv = youtube_channels_csv

    def load_youtube_data(self, file_path):
        """
        Load YouTube channel data from CSV file.

        Args:
            file_path (str): Path to CSV file

        Returns:
            pandas.DataFrame: Channel data or None if loading fails
        """
        try:
            df = pd.read_csv(file_path)
            self.logger.info(f"Successfully loaded {len(df)} YouTube channels")
            return df
        except Exception as e:
            self.logger.error(f"Error loading YouTube CSV file: {e}")
        return None

    def search(self, query, required_terms=None, max_results=5, max_age_days=None, test_mode=False, output_dir=None):
        """
        Search YouTube channels for videos containing required terms.

        Args:
            query (str): The primary search query
            required_terms (list): Terms that MUST appear in title or description
            max_results (int): Maximum videos to return
            max_age_days (int): Only include videos newer than this many days
            test_mode (bool): If True, limit to finding 2 relevant videos
            output_dir (str): Where to save transcripts

        Returns:
            list: List of relevant videos with metadata formatted for research results
        """
        # Input validation and normalization
        try:
            max_results = int(max_results) if max_results is not None else 5
        except (ValueError, TypeError):
            self.logger.info(f"Warning: Invalid max_results value '{max_results}', using default of 5")
            max_results = 5

        # Ensure required_terms is a list of strings
        if required_terms is None:
            required_terms = []
        elif not isinstance(required_terms, list):
            required_terms = [str(required_terms)]
        else:
            required_terms = [str(term) for term in required_terms if term]

        self.logger.info(f"[YOUTUBE] Search query: '{query}'")
        self.logger.info(f"[YOUTUBE] Required terms: {required_terms}")

        # Load channel data
        channels_df = self.load_youtube_data(self.youtube_channels_csv)
        if channels_df is None or len(channels_df) == 0:
            self.logger.info("No YouTube channels found. Returning empty results.")
            return []

        # Limit channels in test mode
        if test_mode and len(channels_df) > 2:
            channels_df = channels_df.head(2)
            self.logger.info(f"[YOUTUBE] Test mode: Limited to {len(channels_df)} channels")

        # Process each channel
        all_matching_videos = []
        videos_found_in_test_mode = 0

        for _, channel in channels_df.iterrows():
            # Get channel info from CSV
            channel_id = channel.get('Channel ID')
            channel_name = channel.get('Name')
            channel_url = channel.get('YouTube URL', '')

            self.logger.info(f"[YOUTUBE] Processing channel: {channel_name}")

            # Get videos from this channel
            try:
                videos = self.retrieve_channel_videos(channel_id, channel_url, max_age_days)

                # Apply required terms filter
                filtered_videos = self.filter_videos_by_required_terms(videos, required_terms)

                # In test mode, check if we've found enough matches
                if test_mode:
                    all_matching_videos.extend(filtered_videos)
                    videos_found_in_test_mode += len(filtered_videos)

                    if videos_found_in_test_mode >= 2:
                        self.logger.info(f"[YOUTUBE] Test mode: Found {videos_found_in_test_mode} matching videos, stopping early")
                        break
                else:
                    all_matching_videos.extend(filtered_videos)

            except Exception as e:
                self.logger.error(f"[YOUTUBE] Error processing channel {channel_name}: {e}")
                continue

        # Calculate relevance scores
        scored_videos = self.calculate_relevance_scores(all_matching_videos, query)

        # Limit results
        max_to_process = min(max_results, len(scored_videos))
        result_videos = scored_videos[:max_to_process]

        # Process transcripts only for result videos
        final_videos = self.fetch_transcripts(
            result_videos,
            output_dir,
            max_transcripts=max_to_process
        )

        # Format for research results integration
        formatted_results = self.format_for_research_results(final_videos, query)

        self.logger.info(f"[YOUTUBE] Search complete. Returning {len(formatted_results)} relevant videos.")
        return formatted_results

    def retrieve_channel_videos(self, channel_id, channel_url, max_age_days):
        """
        Retrieve videos from a single channel.

        Args:
            channel_id (str): YouTube channel ID
            channel_url (str): YouTube channel URL
            max_age_days (int): Only include videos newer than this many days

        Returns:
            list: Videos from the channel
        """
        videos = self.api_client.get_channel_videos(
            channel_id=channel_id,
            channel_url=channel_url,
            max_age_days=max_age_days
        )

        self.logger.info(f"[YOUTUBE] Retrieved {len(videos)} videos from channel")
        return videos

    def filter_videos_by_required_terms(self, videos, required_terms):
        """
        Apply strict filtering with the following rules:
        1. ALL required terms must be present in title OR description
        2. At least ONE search term MUST appear in the title

        Args:
            videos (list): List of video dictionaries
            required_terms (list): Terms that must all be present

        Returns:
            list: Filtered videos meeting all criteria
        """
        if not required_terms:
            self.logger.info("[YOUTUBE] No required terms provided - no filtering applied")
            return videos

        filtered_videos = []
        filtered_count = 0

        for video in videos:
            title = video.get('title', '').lower()
            description = video.get('description', '').lower()
            full_content = f"{title} {description}".lower()

            # Rule 1: Check if ALL required terms are present in content (title + description)
            all_terms_found = True
            for term in required_terms:
                term = term.lower()
                if term not in full_content:
                    all_terms_found = False
                    break

            # Rule 2: Ensure at least ONE search term appears in the title
            any_term_in_title = False
            for term in required_terms:
                term = term.lower()
                if term in title:
                    any_term_in_title = True
                    break

            # Only include videos that pass both filters
            if all_terms_found and any_term_in_title:
                self.logger.info(f"[YOUTUBE] Video passed filter: {video.get('title')}")
                filtered_videos.append(video)
            else:
                # Increment counter but don't log each filtered video
                filtered_count += 1

        self.logger.info(f"[YOUTUBE] Filtered {len(videos)} videos to {len(filtered_videos)} matching required terms ({filtered_count} filtered out)")
        return filtered_videos

    def calculate_relevance_scores(self, videos, query):
        """
        Score videos based on relevance to query with the following rules:
        1. Title match gives higher score than description match
        2. Exact title matches get highest priority
        3. Interview/Founder videos get a significant boost

        Args:
            videos (list): List of video dictionaries
            query (str): Search query

        Returns:
            list: Videos with relevance scores added, sorted by score
        """
        if not videos:
            return []

        query_words = set(query.lower().split())
        interview_keywords = ["founder", "interview", "ceo", "creator", "with", "exclusive"]

        for video in videos:
            title = video.get('title', '').lower()
            description = video.get('description', '').lower()

            # Calculate title word overlap (2x weight)
            title_words = set(title.split())
            title_match_score = 0
            if query_words:
                matching_title_words = query_words.intersection(title_words)
                title_match_score = (len(matching_title_words) / len(query_words)) * 2.0

            # Calculate description word overlap (1x weight)
            desc_words = set(description.split())
            desc_match_score = 0
            if query_words:
                matching_desc_words = query_words.intersection(desc_words)
                desc_match_score = len(matching_desc_words) / len(query_words)

            # Combined base score (weighted toward title matches)
            base_score = title_match_score + desc_match_score

            # Bonus for exact phrase match in title
            exact_query = query.lower()
            if exact_query in title:
                base_score += 3.0  # Major bonus for exact phrase match

            # Check for interview/founder terms and boost further
            has_interview_term = any(keyword in title for keyword in interview_keywords)

            # Special case: If title has both the query AND interview terms, it's likely very relevant
            if has_interview_term and (title_match_score > 0):
                video['relevance_score'] = "High"  # Changed from Very High to High
                video['relevance_value'] = base_score * 3.5  # Highest possible score
                video['interview_score'] = 15  # Higher interview score
            # Normal interview boost
            elif has_interview_term:
                video['relevance_score'] = "High"
                video['relevance_value'] = base_score * 3.0  # Triple score for interviews
                video['interview_score'] = 10
            # Strong title match but not an interview
            elif title_match_score > 1.0:
                video['relevance_score'] = "Medium"  # Changed from Above Average to Medium
                video['relevance_value'] = base_score * 1.5  # Boost for strong title match
                video['interview_score'] = 5
            # Default
            else:
                video['relevance_score'] = "Medium"
                video['relevance_value'] = base_score
                video['interview_score'] = 0

            # Add detailed information about score calculation for debugging
            video['score_details'] = {
                'title_match_score': title_match_score,
                'desc_match_score': desc_match_score,
                'base_score': base_score,
                'has_interview_term': has_interview_term,
                'final_multiplier': video['relevance_value'] / base_score if base_score > 0 else 0
            }

            # Extract key points (simple for now)
            video['key_points'] = self.extract_key_points(title, description)

        # Sort by relevance value
        sorted_videos = sorted(videos, key=lambda x: x.get('relevance_value', 0), reverse=True)

        # Print only top results (reduced logging)
        self.logger.info("\n[YOUTUBE] Top videos by relevance:")
        for i, video in enumerate(sorted_videos[:min(3, len(sorted_videos))]):
            self.logger.info(f"  {i+1}. {video.get('title')} - ({video.get('relevance_score')})")

        return sorted_videos

    def extract_key_points(self, title, description, max_points=3):
        """
        Extract key points from video title and description.

        Args:
            title (str): Video title
            description (str): Video description
            max_points (int): Maximum number of key points to extract

        Returns:
            list: Key points about the video
        """
        # Simple extraction approach
        key_points = []

        # First key point is always a title summary
        key_points.append(f"Video titled: {title}")

        # Try to extract 1-2 sentences from description
        if description:
            sentences = re.split(r'[.!?]', description)
            clean_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            for sentence in clean_sentences[:max_points-1]:
                key_points.append(sentence)

        return key_points

    def fetch_transcripts(self, videos, output_dir, max_transcripts):
        """
        Fetch and save transcripts for videos.

        Args:
            videos (list): List of video dictionaries
            output_dir (str): Directory to save transcripts
            max_transcripts (int): Maximum number of transcripts to process

        Returns:
            list: Videos that successfully had transcripts fetched
        """
        if not videos:
            return []

        videos_with_transcripts = []
        transcript_count = 0

        for video in videos:
            if transcript_count >= max_transcripts:
                break

            try:
                video_id = video.get('video_id')

                if not video_id:
                    self.logger.error(f"[YOUTUBE] Error: No video_id for {video.get('title')}")
                    continue

                self.logger.info(f"[YOUTUBE] Fetching transcript for: {video.get('title')}")
                transcript = self.api_client.get_transcript(video_id=video_id)  # Pass video_id explicitly

                if not transcript or not transcript.get('success') or not transcript.get('content'):
                    self.logger.info(f"[YOUTUBE] Failed to retrieve transcript for: {video.get('title')}")
                    continue

                # Add transcript to video metadata
                video['transcript_text'] = transcript.get('content')
                transcript_count += 1

                # Save transcript to file
                if output_dir:
                    transcript_dir = os.path.join(output_dir, "transcripts")
                    os.makedirs(transcript_dir, exist_ok=True)

                    filename = self.create_safe_filename(video.get('title'))
                    transcript_path = os.path.join(transcript_dir, f"{filename}_transcript.txt")

                    with open(transcript_path, 'w', encoding='utf-8') as f:
                        f.write(transcript.get('content'))

                    video['transcript_path'] = transcript_path
                    self.logger.info(f"[YOUTUBE] Saved transcript to: {transcript_path}")

                videos_with_transcripts.append(video)

            except Exception as e:
                self.logger.error(f"[YOUTUBE] Error processing transcript for '{video.get('title')}': {e}")
                # Skip this video entirely as we can't access its information

        return videos_with_transcripts

    def create_safe_filename(self, title):
        """
        Convert a video title to a safe filename.

        Args:
            title (str): Video title

        Returns:
            str: Safe filename
        """
        if not title:
            return "unknown_video"

        # Replace unsafe chars with underscores
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", title)
        # Replace multiple spaces/underscores with single underscore
        safe_name = re.sub(r'[\s_]+', "_", safe_name)
        # Limit length
        if len(safe_name) > 100:
            safe_name = safe_name[:100]
        return safe_name

    def format_for_research_results(self, videos, query):
        """
        Format videos to match article structure in research results.

        Args:
            videos (list): List of video dictionaries with transcripts
            query (str): Original search query

        Returns:
            list: Formatted video results ready for research integration
        """
        formatted_videos = []

        for video in videos:
            # Skip videos without transcripts
            if 'transcript_text' not in video:
                continue

            # Build list of key insights combining score details and key_points
            key_insights = []

            # First, add relevance information
            if video.get('relevance_score'):
                key_insights.append(f"Relevance: {video.get('relevance_score')}")

            # Add search term match info
            title_contains_query = False
            for term in query.lower().split():
                if term in video.get('title', '').lower():
                    title_contains_query = True
                    break

            if title_contains_query:
                key_insights.append(f"Title contains search term '{query}'")

            # If we have score details, add them
            if 'score_details' in video:
                score_details = video.get('score_details', {})
                if score_details.get('title_match_score', 0) > 0:
                    key_insights.append(f"Title match score: {score_details.get('title_match_score', 0):.1f}")
                if score_details.get('has_interview_term'):
                    key_insights.append("Contains interview or founder keywords")

            # Add original key points
            for point in video.get('key_points', []):
                if point not in key_insights:  # Avoid duplicates
                    key_insights.append(point)

            formatted_video = {
                'title': video.get('title', 'Untitled Video'),
                'author': video.get('channel', 'Unknown Channel'),
                'date': video.get('date', 'Unknown Date'),
                'url': video.get('url', ''),
                'video_id': video.get('video_id', ''),
                'relevance_score': video.get('relevance_score', 'Medium'),
                'key_insights': key_insights,  # Use our enhanced insights
                'key_points': key_insights,    # Keep both for compatibility
                'text': video.get('transcript_text', ''),
                'source_type': 'video',  # Mark as video for display formatting
                'interview_score': video.get('interview_score', 0),
                'transcript_path': video.get('transcript_path', '')
            }

            formatted_videos.append(formatted_video)

        return formatted_videos
