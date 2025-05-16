import requests
import re
import datetime
import sys
import json
import time  # Make sure this is imported
sys.path.append('..')
from config import YOUTUBE_API_KEY, YOUTUBE_API_BASE_URL, YOUTUBE_API_MAX_RESULTS_PER_PAGE, SUPADATA_API_KEY, SUPADATA_BASE_URL, SUPADATA_TRANSCRIPT_ENDPOINT, SUPADATA_REQUEST_DELAY

# Add delay constant for YouTube API requests
YOUTUBE_API_REQUEST_DELAY = 0.5  # 500ms delay between API requests

class YouTubeAPIClient:
    """
    Client for interacting with the YouTube Data API.
    Replaces the RSS feed approach with direct API access to get all videos from a channel.
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the YouTube API client.
        
        Args:
            api_key (str, optional): YouTube API key. If not provided, uses the key from config.
        """
        self.api_key = api_key or YOUTUBE_API_KEY
        self.base_url = YOUTUBE_API_BASE_URL
        
        if not self.api_key:
            raise ValueError("YouTube API key is required. Set YOUTUBE_API_KEY in .env file.")
    
    def extract_channel_id(self, channel_url):
        """
        Extract YouTube channel ID from a URL or return the ID if it's already an ID.
        
        Args:
            channel_url (str): Channel URL or ID
            
        Returns:
            str: Channel ID or None if extraction fails
        """
        # If it's already a channel ID (starts with UC)
        if channel_url and channel_url.startswith('UC'):
            return channel_url
            
        # If it's not a URL, can't extract
        if not channel_url or not ('youtube.com' in channel_url or 'youtu.be' in channel_url):
            return None
            
        # Make sure URL starts with http:// or https://
        if not channel_url.startswith(('http://', 'https://')):
            channel_url = 'https://' + channel_url
        
        # Try to extract from different URL formats
        try:
            # Extract from /channel/ URL
            if '/channel/' in channel_url:
                channel_id = channel_url.split('/channel/')[1].split('/')[0]
                return channel_id
                
            # Extract from @username format (modern YouTube URLs)
            elif '@' in channel_url:
                username = channel_url.split('@')[1].split('/')[0].split('?')[0]
                # Try to get channel ID from username via API
                
                # Add delay before API request
                time.sleep(YOUTUBE_API_REQUEST_DELAY)
                
                endpoint = f"{self.base_url}/search"
                params = {
                    'key': self.api_key,
                    'q': username,
                    'type': 'channel',
                    'part': 'snippet',
                    'maxResults': 1
                }
                
                response = requests.get(endpoint, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'items' in data and data['items']:
                        return data['items'][0]['snippet']['channelId']
                
            # For other URL formats, we need to make an API request
            # Try to extract username or custom URL
            username = None
            
            if '/c/' in channel_url:
                username = channel_url.split('/c/')[1].split('/')[0]
            elif '/user/' in channel_url:
                username = channel_url.split('/user/')[1].split('/')[0]
                
            if username:
                # Use the channels.list endpoint to find the channel ID
                
                # Add delay before API request
                time.sleep(YOUTUBE_API_REQUEST_DELAY)
                
                endpoint = f"{self.base_url}/channels"
                params = {
                    'key': self.api_key,
                    'part': 'id',
                    'forUsername': username
                }
                
                response = requests.get(endpoint, params=params)
                data = response.json()
                
                if response.status_code == 200 and 'items' in data and data['items']:
                    return data['items'][0]['id']
                    
            # If all else fails, try to fetch the page and extract the channel ID
            response = requests.get(channel_url)
            response.raise_for_status()
            
            # Try to find channel ID in the HTML
            channel_id_match = re.search(r'"channelId":"([^"]+)"', response.text)
            if channel_id_match:
                return channel_id_match.group(1)
            
            # Alternate pattern
            alt_match = re.search(r'"externalId":"([^"]+)"', response.text)
            if alt_match:
                return alt_match.group(1)
                
            return None
                
        except Exception as e:
            print(f"Error extracting channel ID from {channel_url}: {e}")
            return None
    
    def get_channel_videos(self, channel_url, channel_id=None, max_age_days=None):
        """
        Get all videos from a YouTube channel using the uploads playlist.
        This uses much less API quota than search.list calls.
        
        Args:
            channel_url (str): URL of the YouTube channel
            channel_id (str, optional): Channel ID (if already known)
            max_age_days (int, optional): Only return videos newer than this many days
            
        Returns:
            list: List of video objects
        """
        # Extract channel ID if not provided or invalid
        if not channel_id or not channel_id.startswith('UC'):
            extracted_id = self.extract_channel_id(channel_url)
            if extracted_id:
                channel_id = extracted_id
                print(f"Extracted channel ID from URL")
        
        if not channel_id:
            print(f"Could not determine channel ID for {channel_url}")
            return []
            
        # Step 1: Get the uploads playlist ID for this channel (single API call)
        try:
            uploads_playlist_id = self._get_uploads_playlist_id(channel_id)
            if not uploads_playlist_id:
                print(f"Could not find uploads playlist for channel")
                return []
                
            # Step 2: Get videos from the uploads playlist (one API call per page of 50 videos)
            videos = self._get_playlist_videos(uploads_playlist_id, max_age_days)
            print(f"Found {len(videos)} videos")
            return videos
                
        except Exception as e:
            print(f"Error fetching videos: {e}")
            return []
    
    def _get_uploads_playlist_id(self, channel_id):
        """
        Get the uploads playlist ID for a channel.
        
        Args:
            channel_id (str): The YouTube channel ID
            
        Returns:
            str: The uploads playlist ID or None if not found
        """
        # Add delay before API request
        time.sleep(YOUTUBE_API_REQUEST_DELAY)
        
        endpoint = f"{self.base_url}/channels"
        params = {
            'key': self.api_key,
            'part': 'contentDetails',
            'id': channel_id
        }
        
        response = requests.get(endpoint, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if 'items' in data and data['items']:
                # The uploads playlist ID is stored in contentDetails.relatedPlaylists.uploads
                return data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        return None
    
    def _get_playlist_videos(self, playlist_id, max_age_days=None):
        """
        Get all videos from a playlist.
        
        Args:
            playlist_id (str): The YouTube playlist ID
            max_age_days (int, optional): Only return videos newer than this many days
            
        Returns:
            list: List of video objects
        """
        videos = []
        next_page_token = None
        page_count = 0
        max_pages = 4  # Limit to 4 pages (200 videos)
        
        while True:
            page_count += 1
            if page_count > max_pages:
                print(f"Reached maximum page limit ({max_pages})")
                break
                
            print(f"Fetching playlist page {page_count}")
            
            # Add delay between API requests
            if page_count > 1:
                time.sleep(YOUTUBE_API_REQUEST_DELAY)
            
            # Prepare API request for playlistItems
            endpoint = f"{self.base_url}/playlistItems"
            params = {
                'key': self.api_key,
                'part': 'snippet,contentDetails',
                'playlistId': playlist_id,
                'maxResults': 50
            }
            
            if next_page_token:
                params['pageToken'] = next_page_token
                
            response = requests.get(endpoint, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching playlist: {response.status_code}")
                if response.status_code == 403 and "quota" in response.text:
                    print("YouTube API quota exceeded!")
                print(f"Response: {response.text}")
                break
                
            data = response.json()
            
            # Process video items from this page
            for item in data.get('items', []):
                snippet = item.get('snippet', {})
                
                # Check if the video is too old
                if max_age_days is not None:
                    published_at = snippet.get('publishedAt')
                    if published_at:
                        published_date = datetime.datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        now = datetime.datetime.now(datetime.timezone.utc)
                        if (now - published_date).days > max_age_days:
                            continue
                
                # Extract video data
                video_id = snippet.get('resourceId', {}).get('videoId', '')
                
                video = {
                    'title': snippet.get('title', ''),
                    'date': snippet.get('publishedAt', ''),
                    'channel': snippet.get('channelTitle', ''),
                    'description': snippet.get('description', ''),
                    'video_id': video_id,
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                }
                
                videos.append(video)
            
            # Get next page token if any
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                print("No more pages in playlist")
                break
            
            # If we have enough videos already, stop
            if len(videos) >= 200:  # Increased from 150 to 200 videos per channel
                print(f"Reached video count limit (200)")
                break
                
        return videos
    
    def get_transcript(self, video_url=None, video_id=None):
        """
        Fetch the transcript of a YouTube video using SupaData API.
        This method maintains compatibility with the previous implementation.
        
        Args:
            video_url: URL of the YouTube video
            video_id: ID of the YouTube video (alternative to URL)
            
        Returns:
            Dictionary with transcript text and status, or None if unsuccessful
        """
        if not video_url and not video_id:
            print("Error: Neither video URL nor video ID provided")
            return {
                "success": False,
                "error": "No video URL or ID provided"
            }
        
        # Extract video_id from URL if needed
        if video_url and not video_id:
            match = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([^&?\/]+)', video_url)
            if match:
                video_id = match.group(1)
        
        # Prepare API request headers
        headers = {
            'x-api-key': SUPADATA_API_KEY
        }
        
        # Build request URL with parameters
        request_url = f"{SUPADATA_BASE_URL}{SUPADATA_TRANSCRIPT_ENDPOINT}"
        
        # According to the SupaData docs, we must use videoId parameter
        params = {
            'text': 'true',
            'videoId': video_id
        }
        
        try:
            # Add delay to respect rate limits
            time.sleep(SUPADATA_REQUEST_DELAY)
            
            # Make the API request
            response = requests.get(request_url, headers=headers, params=params)
            
            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully retrieved transcript")
                return {
                    "success": True,
                    "content": data.get("content", ""),
                    "lang": data.get("lang", "unknown")
                }
            elif response.status_code == 206:
                print(f"No transcript available for this video")
                return {
                    "success": False,
                    "error": "No transcript available for this video"
                }
            else:
                error_msg = ""
                try:
                    error_msg = response.json().get("message", "")
                except:
                    pass
                
                print(f"Error fetching transcript: {response.status_code} - {error_msg}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {error_msg}"
                }
                
        except Exception as e:
            print(f"Exception while fetching transcript: {e}")
            return {
                "success": False,
                "error": f"Exception: {str(e)}"
            }
    
    def save_transcript(self, transcript, title, output_dir):
        """
        Save a transcript to a file with a sanitized filename.
        This method maintains compatibility with the previous implementation.
        
        Args:
            transcript: Transcript content
            title: Video title (will be sanitized for filename)
            output_dir: Directory to save the transcript
            
        Returns:
            Path to the saved file or None if unsuccessful
        """
        import os
        
        if not transcript or not title:
            return None
        
        # Sanitize the title for a filename
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title)  # Remove invalid filename chars
        sanitized_title = re.sub(r'\s+', "_", sanitized_title)  # Replace spaces with underscores
        sanitized_title = sanitized_title[:100]  # Limit length
        
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Create the file path
        file_path = os.path.join(output_dir, f"{sanitized_title}_transcript.txt")
        
        try:
            # Write the transcript to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            print(f"Transcript saved to {file_path}")
            return file_path
        except Exception as e:
            print(f"Error saving transcript: {e}")
            return None 