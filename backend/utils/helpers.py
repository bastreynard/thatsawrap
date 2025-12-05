"""
Utility functions for the application.
"""
import re
from threading import Lock


# Progress tracking
transfer_progress = {}
progress_lock = Lock()


def set_progress(user_id, progress, added=0, total=0, current_track=''):
    """Set transfer progress for a user."""
    with progress_lock:
        transfer_progress[user_id] = {
            'progress': progress,
            'added': added,
            'total': total,
            'current_track': current_track
        }


def get_progress(user_id):
    """Get transfer progress for a user."""
    with progress_lock:
        return transfer_progress.get(user_id, {
            'progress': 0,
            'added': 0,
            'total': 0,
            'current_track': ''
        })


def sanitize_search_query(text):
    """
    Sanitize text for search queries by removing special characters
    that might break the search or cause poor results.
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text suitable for search queries
    """
    if not text:
        return ''
    
    # Remove content in parentheses (often remix info, features, etc.)
    # Example: "Song (Remix)" -> "Song", "Song (feat. Artist)" -> "Song"
    text = re.sub(r'\([^)]*\)', '', text)
    
    # Remove content in brackets
    text = re.sub(r'\[[^\]]*\]', '', text)
    
    # Remove common special characters that break searches
    # Keep: letters, numbers, spaces, apostrophes
    text = re.sub(r'[^\w\s\'-]', ' ', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text
