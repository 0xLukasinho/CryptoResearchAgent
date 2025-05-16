import re

def extract_clean_text(article):
    """
    Extract and clean text from an article for keyword matching
    
    Args:
        article: Article dictionary with title and text fields
        
    Returns:
        Combined text of title and content in lowercase
    """
    title = article.get('title', '').lower()
    text = article.get('text', '').lower()
    
    # Combine title and text, remove special characters
    combined_text = title + " " + text
    # Replace special characters with spaces
    clean_text = re.sub(r'[^\w\s]', ' ', combined_text)
    # Remove extra spaces
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

def contains_all_required_terms(article, required_terms):
    """
    Check if an article contains all required terms
    
    Args:
        article: Article dictionary with title and text fields, or a plain string
        required_terms: List of required terms (case insensitive)
        
    Returns:
        Boolean indicating if all terms are present
    """
    # Add debug output to verify parameters
    if isinstance(required_terms, list):
        print(f"[FILTER] DEBUG: Required terms list length: {len(required_terms)}")
    else:
        print(f"[FILTER] DEBUG: Required terms is not a list! Type: {type(required_terms)}")
        
    # First verify we actually have required terms
    if not required_terms or not isinstance(required_terms, list) or len(required_terms) == 0:
        print(f"[FILTER] DEBUG: No required terms to check against, passing all content")
        return True  # If no required terms, pass all articles
    
    # Check if the input is a string or a dictionary
    if isinstance(article, str):
        clean_text = article.lower()
    else:
        clean_text = extract_clean_text(article)
    
    # Clean the required terms to match the text cleaning
    clean_terms = []
    for term in required_terms:
        if not term or not isinstance(term, str):
            print(f"[FILTER] DEBUG: Invalid term in required_terms: {term}, type: {type(term)}")
            continue
        clean_term = term.lower().strip()  # Convert to lowercase and strip whitespace
        if clean_term:  # Only add non-empty terms
            clean_terms.append(clean_term)
    
    # If all terms were invalid or empty, pass all content
    if not clean_terms:
        print(f"[FILTER] DEBUG: No valid required terms after cleaning, passing all content")
        return True
    
    # Print debugging info for important searches
    print(f"[FILTER] DEBUG: Checking for terms {clean_terms} in content")
    print(f"[FILTER] DEBUG: Content preview: {clean_text[:100]}...")
    
    # Check if all terms are in the text (case insensitive)
    all_terms_found = True
    for term in clean_terms:
        if term not in clean_text:
            print(f"[FILTER] DEBUG: Term '{term}' NOT FOUND in content")
            all_terms_found = False
            break
        else:
            print(f"[FILTER] DEBUG: Term '{term}' FOUND in content")
    
    # Print result for all searches
    if all_terms_found:
        print(f"[FILTER] DEBUG: All required terms found: {clean_terms}")
    else:
        print(f"[FILTER] DEBUG: Not all required terms found in content")
    
    return all_terms_found

def is_likely_english(text, threshold=0.005):
    """
    Check if text is likely English using common word frequency
    
    Args:
        text: The text to check
        threshold: Minimum ratio of common words (default 0.5%)
        
    Returns:
        Boolean indicating if text is likely English
    """
    # 300 most common English words
    common_english_words = {
        "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", 
        "was", "for", "on", "are", "as", "with", "his", "they", "I", "at", "be", 
        "this", "have", "from", "or", "one", "had", "by", "word", "but", "not", 
        "what", "all", "were", "we", "when", "your", "can", "said", "there", 
        "use", "an", "each", "which", "she", "do", "how", "their", "if", "will", 
        "up", "other", "about", "out", "many", "then", "them", "these", "so", 
        "some", "her", "would", "make", "like", "him", "into", "time", "has", 
        "look", "two", "more", "write", "go", "see", "number", "no", "way", 
        "could", "people", "my", "than", "first", "water", "been", "call", 
        "who", "oil", "its", "now", "find", "long", "down", "day", "did", "get", 
        "come", "made", "may", "part"
    }
    
    # Simple word tokenization
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    if not words:
        return False  # No recognizable words
    
    # Count English common words
    english_word_count = sum(1 for word in words if word in common_english_words)
    
    # Calculate ratio
    ratio = english_word_count / len(words)
    
    return ratio >= threshold 