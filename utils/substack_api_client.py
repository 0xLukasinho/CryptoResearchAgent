from utils.substack_wrapper import Newsletter, Post
import time
import random
import datetime
from typing import List, Dict, Any, Optional
import requests
import re

class SubstackAPIClient:
    """Client for interacting with the unofficial Substack API"""
    
    def __init__(self):
        # Rate limiting to avoid being blocked (significantly reduced)
        self.min_delay = 0.03  # Was 0.02 - increased to 0.03
        self.max_delay = 0.09  # Was 0.07 - increased to 0.09
        self.last_had_age_filtering = False
        
    def _random_delay(self):
        """Add a random delay between requests to avoid being blocked"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def _safe_api_call(self, func, *args, **kwargs):
        """
        Safely execute an API call with proper error handling
        
        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function call or None on error
        """
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            # Handle specific HTTP status codes
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 429:
                    print("Rate limit exceeded. Waiting before retry...")
                    # Use class variable to track consecutive rate limits
                    if not hasattr(self, '_rate_limit_count'):
                        self._rate_limit_count = 0
                    self._rate_limit_count += 1
                    
                    # Progressive backoff - 5s base with 1s per consecutive error up to 15s max
                    wait_time = min(5 + self._rate_limit_count, 15)
                    time.sleep(wait_time)
                    
                    # Reset counter after 3 consecutive rate limits to avoid persistent slowdown
                    if self._rate_limit_count >= 3:
                        self._rate_limit_count = 0
                elif e.response.status_code == 404:
                    print("Resource not found. Check the URL/ID.")
                else:
                    print(f"HTTP Status: {e.response.status_code}")
            return None
        except ValueError as e:
            print(f"Value Error: {e}")
            return None
        except KeyError as e:
            print(f"Key Error: {e} - Missing expected data in API response")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def _extract_substack_domain(self, url):
        """Extract the domain from a Substack URL"""
        # Remove protocol if present
        url = url.replace('https://', '').replace('http://', '')
        # Get domain part without any path
        domain = url.split('/')[0]
        # Remove any "substack.com" appended to the domain
        if 'substack.com' in domain and domain != 'substack.com':
            domain = domain.split('.substack.com')[0]
        return domain
    
    def get_newsletter_posts(self, url: str, max_articles: Optional[int] = None, 
                             max_age_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get articles from a Substack newsletter using the unofficial API with pagination
        
        Args:
            url: Substack URL
            max_articles: Maximum number of articles to extract (None for unlimited)
            max_age_days: Maximum age of articles in days
            
        Returns:
            List of article content dictionaries in the same format as the RSS parser output
        """
        # Maximum retries for the entire API call
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Reset tracking flag for age filtering
                self.last_had_age_filtering = False
                
                # Initialize the Newsletter object with the URL
                newsletter = Newsletter(url)
                
                # Add random delay to avoid rate limiting
                self._random_delay()
                
                # Use pagination to get posts
                all_posts = []
                current_page = 0
                page_size = 25  # Keep same as default in substack_wrapper to avoid issues
                has_more_posts = True
                posts_count = 0
                
                # Print info about pagination
                print(f"Retrieving articles from {url} with pagination (batch size: {page_size})")
                
                # Get current date for age filtering
                current_date = datetime.datetime.now(datetime.timezone.utc)
                
                # Track filtering stats
                filtered_for_date_count = 0
                total_retrieved = 0
                
                while has_more_posts:
                    # Calculate offset for current page
                    offset = current_page * page_size
                    
                    # Use the get_posts method to retrieve current page of posts
                    posts = self._safe_api_call(
                        newsletter.get_posts, 
                        limit=page_size,
                        offset=offset,
                        sorting="new"
                    )
                    
                    # Add delay between pagination requests to avoid rate limiting
                    self._random_delay()
                    
                    # Additional small delay between pages to help with higher article limits
                    if current_page > 0 and current_page % 5 == 0:
                        # Add a slightly longer pause every 5 pages
                        time.sleep(0.1)  # Was 0.2
                    
                    # Break if no posts returned or error occurred
                    if not posts:
                        if current_page == 0:
                            print(f"No posts found or error occurred for {url}")
                        else:
                            print(f"Retrieved {len(all_posts)} articles from {url} (reached end of posts)")
                        break
                    
                    # Add current batch count to total
                    total_retrieved += len(posts)
                    
                    # Apply date filtering
                    if max_age_days is not None:
                        posts_before_filter = len(posts)
                        filtered_posts = []
                        
                        for post in posts:
                            try:
                                # Get post metadata - we only need the date for filtering
                                metadata = self._safe_api_call(post.get_metadata)
                                if not metadata:
                                    # Keep posts with missing metadata for now - we'll filter later if needed
                                    filtered_posts.append(post)
                                    continue
                                    
                                # Check post date
                                post_date_str = metadata.get('post_date', '')
                                if not post_date_str:
                                    # Keep posts with missing dates
                                    filtered_posts.append(post)
                                    continue
                                    
                                # Parse date with robust error handling
                                try:
                                    post_date = datetime.datetime.fromisoformat(post_date_str.replace('Z', '+00:00'))
                                except ValueError:
                                    # Try other date formats if ISO format fails
                                    try:
                                        post_date = datetime.datetime.strptime(post_date_str, "%Y-%m-%d")
                                    except ValueError:
                                        # Keep posts with unparseable dates
                                        filtered_posts.append(post)
                                        continue
                                
                                # Calculate age
                                delta = current_date - post_date
                                
                                # Skip posts older than max_age_days
                                if delta.days > max_age_days:
                                    filtered_for_date_count += 1
                                    continue
                                
                                # Keep posts within date range
                                filtered_posts.append(post)
                                
                            except Exception as e:
                                # Keep posts where we couldn't determine age
                                print(f"Warning: Error checking post date: {e}")
                                filtered_posts.append(post)
                        
                        # Filter stats for this page
                        filtered_this_page = posts_before_filter - len(filtered_posts)
                        if filtered_this_page > 0:
                            print(f"  Filtered {filtered_this_page} posts older than {max_age_days} days")
                        
                        # Replace the posts list with filtered posts
                        posts = filtered_posts
                    
                    # Add posts to our collection
                    all_posts.extend(posts)
                    posts_count = len(all_posts)
                    
                    # Report progress
                    print(f"Retrieved page {current_page + 1} ({len(posts)} articles, total so far: {posts_count})")
                    
                    # Check if we've reached max_articles
                    if max_articles is not None and posts_count >= max_articles:
                        all_posts = all_posts[:max_articles]  # Trim to exact limit
                        print(f"Reached maximum article limit ({max_articles})")
                        break
                    
                    # Check if this page had fewer articles than requested (indicating last page)
                    if len(posts) < page_size:
                        has_more_posts = False
                        print(f"Retrieved all available posts from {url} (total: {posts_count})")
                    else:
                        # Move to next page
                        current_page += 1
                
                # Process each post
                all_articles = []
                
                for post in all_posts:
                    # Add random delay between post processing to avoid rate limiting
                    self._random_delay()
                    
                    # Convert to our article format
                    article = self._convert_post_to_article_format(post)
                    
                    if not article:
                        continue
                    
                    all_articles.append(article)
                
                # Print summary of date filtering
                if max_age_days is not None:
                    print(f"Age filtering summary: {filtered_for_date_count} of {total_retrieved} posts were filtered out (older than {max_age_days} days)")
                    # Set flag that we performed age filtering (regardless of whether any were filtered)
                    self.last_had_age_filtering = True
                
                print(f"Processed {len(all_articles)} articles from {url}")
                return all_articles
                
            except Exception as e:
                print(f"Error fetching posts from {url}: {e}")
                retry_count += 1
                if retry_count <= max_retries:
                    # Wait before retrying
                    wait_time = 2 * retry_count  # Progressive wait: 2s, then 4s
                    print(f"Retrying in {wait_time}s (attempt {retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed after {max_retries} retries")
                    return []
        
        return []  # Fallback return
    
    def _convert_post_to_article_format(self, post) -> Dict[str, Any]:
        """
        Convert a Substack API Post object to our article format
        
        Args:
            post: Substack API Post object
            
        Returns:
            Article dictionary in the format expected by our system
        """
        try:
            # Get post metadata
            metadata = self._safe_api_call(post.get_metadata)
            
            if not metadata:
                return None
            
            # Get full content
            content = self._safe_api_call(post.get_content)
            
            # Ensure we have valid strings for concatenation
            description = metadata.get('description', '') or ''
            content_text = content or ''
            
            # Map fields to our article format
            return {
                'title': metadata.get('title', 'Unknown Title'),
                'date': metadata.get('post_date', 'Unknown Date'),
                'author': metadata.get('byline', 'Unknown Author'),
                'text': description + "\n\n" + content_text,
                'url': metadata.get('canonical_url', '')
            }
        except Exception as e:
            print(f"Error converting post to article format: {e}")
            return None
    
    def search_newsletter_posts(self, url: str, query: str, max_articles: Optional[int] = None, 
                               max_age_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for posts in a Substack newsletter
        
        Args:
            url: Substack URL
            query: Search query
            max_articles: Maximum number of articles to extract
            max_age_days: Maximum age of articles in days
            
        Returns:
            List of matching article content dictionaries
        """
        try:
            # Initialize the Newsletter object with the URL
            newsletter = Newsletter(url)
            
            # Add random delay to avoid rate limiting
            self._random_delay()
            
            # Use the search_posts method to search for posts
            search_results = self._safe_api_call(
                newsletter.search_posts,
                query=query,
                limit=max_articles
            )
            
            if not search_results:
                print(f"No search results found or error occurred for query '{query}' in {url}")
                return []
            
            # Process each result
            articles = []
            current_date = datetime.datetime.now(datetime.timezone.utc)
            
            for post in search_results:
                # Add random delay between post processing
                self._random_delay()
                
                # Convert to our article format
                article = self._convert_post_to_article_format(post)
                
                if not article:
                    continue
                
                # Apply date filtering if specified
                if max_age_days is not None:
                    try:
                        post_date_str = article.get('date', '')
                        post_date = datetime.datetime.fromisoformat(post_date_str.replace('Z', '+00:00'))
                        delta = current_date - post_date
                        
                        # Skip posts older than max_age_days
                        if delta.days > max_age_days:
                            continue
                    except (ValueError, AttributeError, TypeError):
                        # If date parsing fails, include the post
                        print(f"Warning: Could not parse date for post: {article.get('title', 'Unknown')}")
                
                articles.append(article)
            
            print(f"Found {len(articles)} matching articles for query '{query}' in {url}")
            return articles
            
        except Exception as e:
            print(f"Error searching posts in {url}: {e}")
            return []