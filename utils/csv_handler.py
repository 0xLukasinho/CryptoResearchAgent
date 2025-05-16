import pandas as pd

def load_substack_data(file_path):
    """
    Load the Substack CSV file into a pandas DataFrame
    """
    try:
        df = pd.read_csv(file_path)
        print(f"Successfully loaded {len(df)} Substack entries")
        return df
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return None

def search_substacks(df, query, keywords=None):
    """
    Search Substack entries based on query and keywords
    
    Args:
        df: Pandas DataFrame containing Substack data
        query: Search query from user
        keywords: Optional list of keywords to filter results
    
    Returns:
        DataFrame with matching Substacks
    """
    if keywords is None:
        keywords = []
    
    # Convert query and keywords to lowercase for case-insensitive matching
    query = query.lower()
    keywords = [k.lower() for k in keywords]
    
    # Check if any fields contain the query
    mask = df['Name'].str.lower().str.contains(query, na=False)
    if 'by' in df.columns:
        mask |= df['by'].str.lower().str.contains(query, na=False)
    
    # Apply filters for keywords
    for keyword in keywords:
        mask |= df['Name'].str.lower().str.contains(keyword, na=False)
        if 'by' in df.columns:
            mask |= df['by'].str.lower().str.contains(keyword, na=False)
    
    results = df[mask].copy()
    
    # Only return results with valid URLs
    results = results[results['Substack URL'].notna() & (results['Substack URL'] != '')]
    
    return results 