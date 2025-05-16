import requests
from bs4 import BeautifulSoup
import time
import random

class ArticleScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        # Rate limiting to avoid being blocked
        self.min_delay = 1.0
        self.max_delay = 3.0
    
    def _random_delay(self):
        """Add a random delay between requests to avoid being blocked"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def get_substack_articles(self, url, max_articles=5):
        """
        Extract article links from a Substack homepage
        
        Args:
            url: Substack URL
            max_articles: Maximum number of articles to extract
            
        Returns:
            List of article URLs
        """
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            print(f"Fetching articles from: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all article links
            article_links = []
            post_items = soup.select('.post-preview')
            
            if not post_items:  # Try alternative selectors for different Substack themes
                post_items = soup.select('.post-item')
            
            if not post_items:
                post_items = soup.select('article')
            
            # Extract links from post items
            for item in post_items[:max_articles]:
                link_tag = item.find('a', href=True)
                if link_tag and link_tag['href']:
                    href = link_tag['href']
                    # Handle relative URLs
                    if not href.startswith(('http://', 'https://')):
                        if href.startswith('/'):
                            href = url.rstrip('/') + href
                        else:
                            href = url.rstrip('/') + '/' + href
                    article_links.append(href)
            
            print(f"Found {len(article_links)} articles")
            return article_links[:max_articles]
        
        except Exception as e:
            print(f"Error fetching articles from {url}: {e}")
            return []
    
    def extract_article_content(self, url):
        """
        Extract article content from a Substack article URL
        
        Args:
            url: Article URL
            
        Returns:
            Dict with article title, date, author, and text
        """
        self._random_delay()
        
        try:
            print(f"Extracting content from: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title_tag = soup.find('h1')
            title = title_tag.get_text().strip() if title_tag else "Unknown Title"
            
            # Extract date
            date_tag = soup.select_one('.post-date') or soup.select_one('.datetime')
            date = date_tag.get_text().strip() if date_tag else "Unknown Date"
            
            # Extract author
            author_tag = soup.select_one('.author-name') or soup.select_one('.profile-name')
            author = author_tag.get_text().strip() if author_tag else "Unknown Author"
            
            # Extract content
            content_div = soup.select_one('.body') or soup.select_one('.post-content') or soup.select_one('article')
            
            if content_div:
                # Remove any script and style elements
                for element in content_div.select('script, style, .subscription-widget-wrap'):
                    element.extract()
                
                # Get all text from paragraphs
                paragraphs = content_div.find_all('p')
                text = '\n\n'.join([p.get_text().strip() for p in paragraphs])
            else:
                text = "Unable to extract article content"
            
            return {
                'title': title,
                'date': date,
                'author': author,
                'text': text,
                'url': url
            }
            
        except Exception as e:
            print(f"Error extracting content from {url}: {e}")
            return {
                'title': "Error",
                'date': "Unknown",
                'author': "Unknown",
                'text': f"Failed to extract content: {str(e)}",
                'url': url
            } 