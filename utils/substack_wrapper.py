import requests
import time
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse, urljoin

class Newsletter:
    """Class to interact with a Substack newsletter"""
    
    def __init__(self, url: str):
        """Initialize a Newsletter with a Substack URL"""
        self.url = url.rstrip('/')
        
        # Extract domain from URL
        parsed_url = urlparse(self.url)
        self.domain = parsed_url.netloc
        
        # If no protocol specified, assume https and fix the domain/url
        if not parsed_url.scheme:
            self.domain = self.url
            self.url = f"https://{self.url}"
        
        # API endpoints
        self.base_api_url = f"{self.url}/api/v1"
        
        # Default headers for requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36'
        }
    
    def __str__(self) -> str:
        return f"Newsletter: {self.url}"
    
    def __repr__(self) -> str:
        return f"Newsletter(url={self.url})"
    
    def get_posts(self, limit: Optional[int] = None, offset: Optional[int] = None, sorting: str = "new") -> List['Post']:
        """
        Get posts from the newsletter
        
        Args:
            limit: Maximum number of posts to retrieve
            offset: Number of posts to skip (for pagination)
            sorting: How to sort the posts ('new' or 'top')
            
        Returns:
            List of Post objects
        """
        # Endpoint for getting posts
        posts_endpoint = f"{self.base_api_url}/posts"
        
        # Parameters
        params = {
            'sort': sorting,
            'limit': limit or 25  # Keep default at 25 to avoid rate limiting
        }
        
        # Add offset parameter if provided
        if offset is not None:
            params['offset'] = offset
        
        try:
            response = requests.get(posts_endpoint, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            # The API might return data in different structures
            # Try different ways to extract post data
            post_data_list = []
            
            if isinstance(data, dict) and 'posts' in data:
                # Standard structure: {'posts': [...]}
                post_data_list = data['posts']
            elif isinstance(data, list):
                # Alternative structure: direct list of posts
                post_data_list = data
            
            # Create Post objects from the response
            for post_data in post_data_list:
                # Check if post_data has canonical_url or we need to construct it
                post_url = None
                
                if isinstance(post_data, dict):
                    post_url = post_data.get('canonical_url')
                    
                    # If no canonical_url, try to construct from slug
                    if not post_url and 'slug' in post_data:
                        post_url = f"{self.url}/p/{post_data['slug']}"
                
                if post_url:
                    post = Post(post_url)
                    post._post_data = post_data  # Pre-fill with data to avoid additional requests
                    posts.append(post)
            
            return posts[:limit] if limit else posts
            
        except Exception as e:
            print(f"Error retrieving posts: {e}")
            return []
    
    def search_posts(self, query: str, limit: Optional[int] = None) -> List['Post']:
        """
        Search for posts in the newsletter
        
        Args:
            query: Search query
            limit: Maximum number of posts to retrieve
            
        Returns:
            List of matching Post objects
        """
        # Endpoint for searching posts
        search_endpoint = f"{self.base_api_url}/search"
        
        # Parameters
        params = {
            'query': query,
            'limit': limit or 10
        }
        
        try:
            response = requests.get(search_endpoint, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            # The API might return data in different structures
            # Try different ways to extract search results
            result_list = []
            
            if isinstance(data, dict) and 'results' in data:
                # Standard structure: {'results': [...]}
                result_list = data['results']
            elif isinstance(data, list):
                # Alternative structure: direct list of results
                result_list = data
            
            # Create Post objects from the response
            for post_data in result_list:
                post_url = None
                
                if isinstance(post_data, dict):
                    # Try different ways to get the post URL
                    if 'canonical_url' in post_data:
                        post_url = post_data['canonical_url']
                    elif 'slug' in post_data:
                        post_url = urljoin(self.url, f"/p/{post_data['slug']}")
                
                if post_url:
                    post = Post(post_url)
                    post._post_data = post_data  # Pre-fill with data
                    posts.append(post)
            
            return posts[:limit] if limit else posts
            
        except Exception as e:
            print(f"Error searching posts: {e}")
            return []
    
    def get_podcasts(self, limit: Optional[int] = None) -> List['Post']:
        """
        Get podcast episodes from the newsletter
        
        Args:
            limit: Maximum number of episodes to retrieve
            
        Returns:
            List of Post objects that are podcasts
        """
        # For simplicity, we'll get all posts and filter for podcasts
        all_posts = self.get_posts(limit=50)  # Get more than needed to account for filtering
        
        # Filter for posts that are podcasts
        podcasts = [post for post in all_posts if post.get_metadata().get('podcast_metadata')]
        
        return podcasts[:limit] if limit else podcasts
    
    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get recommended newsletters for this Substack
        
        Returns:
            List of recommended newsletter data
        """
        # Endpoint for recommendations
        recommendations_endpoint = f"{self.base_api_url}/recommendations"
        
        try:
            response = requests.get(recommendations_endpoint, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('recommendations', [])
            
        except Exception as e:
            print(f"Error retrieving recommendations: {e}")
            return []
    
    def get_authors(self) -> List[Dict[str, Any]]:
        """
        Get author information for the newsletter
        
        Returns:
            List of author data
        """
        # Endpoint for newsletter info (which includes authors)
        info_endpoint = f"{self.base_api_url}/publication"
        
        try:
            response = requests.get(info_endpoint, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('contributors', [])
            
        except Exception as e:
            print(f"Error retrieving authors: {e}")
            return []

class Post:
    """Class to interact with a Substack post"""
    
    def __init__(self, url: str):
        """Initialize a Post with its URL"""
        self.url = url
        
        # Parse URL to extract components
        parsed_url = urlparse(url)
        
        # Handle URLs without scheme
        if not parsed_url.scheme:
            self.url = f"https://{url}"
            parsed_url = urlparse(self.url)
        
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Extract slug from path
        path_parts = parsed_url.path.strip('/').split('/')
        self.slug = path_parts[-1] if len(path_parts) >= 2 and path_parts[-2] == 'p' else ""
        
        # Remove any query parameters or fragments from slug
        self.slug = self.slug.split('?')[0].split('#')[0]
        
        # API endpoint for this post
        self.endpoint = f"{self.base_url}/api/v1/posts/{self.slug}"
        
        # Default headers for requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36'
        }
        
        # Cache for post data
        self._post_data = None
    
    def __str__(self) -> str:
        return f"Post: {self.url}"
    
    def __repr__(self) -> str:
        return f"Post(url={self.url})"
    
    def _fetch_post_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch post data from the API
        
        Args:
            force_refresh: Whether to force a refresh of cached data
            
        Returns:
            Post data as dictionary
        """
        # Use cached data if available and not forcing refresh
        if self._post_data is not None and not force_refresh:
            return self._post_data
        
        try:
            response = requests.get(self.endpoint, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            self._post_data = response.json()
            return self._post_data
            
        except Exception as e:
            print(f"Error fetching post data for {self.url}: {e}")
            # Return empty dict instead of raising to be more resilient
            return {}
    
    def get_metadata(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get metadata for the post
        
        Args:
            force_refresh: Whether to force a refresh of cached data
            
        Returns:
            Dictionary with post metadata
        """
        # Use existing cached data if available
        try:
            return self._fetch_post_data(force_refresh=force_refresh)
        except Exception as e:
            print(f"Error getting metadata: {e}")
            return {}
    
    def get_content(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get HTML content of the post
        
        Args:
            force_refresh: Whether to force a refresh of cached data
            
        Returns:
            HTML content as string, or None if not available
        """
        try:
            data = self._fetch_post_data(force_refresh=force_refresh)
            # Try different common field names for the content
            for field in ['body_html', 'content', 'html', 'body']:
                if field in data and data[field]:
                    return data[field]
            return None
        except Exception as e:
            print(f"Error getting content: {e}")
            return None 