import os
import time
import logging
from playwright.sync_api import sync_playwright

class TweetExtractor:
    """
    Utility for extracting tweet content from tweet URLs using Playwright.
    """
    
    def __init__(self):
        """Initialize the TweetExtractor."""
        self.logger = logging.getLogger('TweetExtractor')
    
    def extract_tweets_from_file(self, tweets_file_path, output_dir):
        """
        Extract tweets from a file containing tweet URLs.
        
        Args:
            tweets_file_path (str): Path to the file containing tweet URLs (one per line)
            output_dir (str): Directory to save extracted tweets
            
        Returns:
            list: List of dictionaries containing tweet data
        """
        if not os.path.exists(tweets_file_path):
            self.logger.warning(f"Tweets file not found: {tweets_file_path}")
            return []
        
        # Create tweets directory if it doesn't exist
        tweets_dir = os.path.join(output_dir, "tweets")
        os.makedirs(tweets_dir, exist_ok=True)
        
        # Read tweet URLs from file
        with open(tweets_file_path, 'r', encoding='utf-8') as f:
            tweet_urls = [line.strip() for line in f.readlines() if line.strip()]
        
        self.logger.info(f"Found {len(tweet_urls)} tweet URLs in {tweets_file_path}")
        
        # Extract content from each tweet
        tweet_data = []
        successful = 0
        
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            for i, url in enumerate(tweet_urls):
                try:
                    self.logger.info(f"Processing tweet {i+1}/{len(tweet_urls)}: {url}")
                    tweet_content = self._extract_tweet_content(page, url)
                    
                    if tweet_content:
                        # Save to file
                        tweet_file = os.path.join(tweets_dir, f"tweet_{i+1}.txt")
                        with open(tweet_file, 'w', encoding='utf-8') as f:
                            f.write(tweet_content)
                        
                        # Add to results
                        tweet_data.append({
                            'title': f"Tweet {i+1}",
                            'text': tweet_content,
                            'url': url,
                            'relevance_score': 'High'  # Treat all tweets as high relevance
                        })
                        
                        successful += 1
                    else:
                        self.logger.warning(f"Failed to extract content from tweet: {url}")
                    
                    # Add delay to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error processing tweet {url}: {e}")
            
            browser.close()
        
        self.logger.info(f"Successfully extracted {successful}/{len(tweet_urls)} tweets")
        return tweet_data
    
    def _extract_tweet_content(self, page, url):
        """
        Extract the content of a tweet using Playwright.
        
        Args:
            page: Playwright page object
            url (str): URL of the tweet
            
        Returns:
            str: Text content of the tweet or None if extraction failed
        """
        try:
            # Navigate to the tweet
            page.goto(url, wait_until="domcontentloaded")
            
            # Wait for the tweet content to load
            page.wait_for_selector('[data-testid="tweetText"]', timeout=10000)
            
            # Extract the tweet text
            tweet_text = page.evaluate('''() => {
                const tweetElement = document.querySelector('[data-testid="tweetText"]');
                return tweetElement ? tweetElement.textContent : null;
            }''')
            
            return tweet_text
            
        except Exception as e:
            self.logger.error(f"Error extracting tweet content: {e}")
            return None 