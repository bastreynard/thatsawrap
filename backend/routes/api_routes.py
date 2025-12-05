"""
API routes for music service operations.
"""
from flask import Blueprint, jsonify, request
from functools import wraps
from services import SpotifyService, TidalService, TransferService
from utils import get_progress


# Initialize services
spotify_service = SpotifyService()
tidal_service = TidalService()


# Create blueprint
api_bp = Blueprint('api', __name__)


# Decorators for authentication
def require_spotify_auth(f):
    """Decorator to require valid Spotify authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not spotify_service.is_authenticated():
            return jsonify({'error': 'Not authenticated with Spotify'}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_tidal_auth(f):
    """Decorator to require valid Tidal authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not tidal_service.is_authenticated():
            return jsonify({'error': 'Not authenticated with Tidal'}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_both_auth(f):
    """Decorator to require both Spotify and Tidal authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not spotify_service.is_authenticated():
            return jsonify({'error': 'Not authenticated with Spotify'}), 401
        if not tidal_service.is_authenticated():
            return jsonify({'error': 'Not authenticated with Tidal'}), 401
        return f(*args, **kwargs)
    return decorated_function


# Spotify endpoints
@api_bp.route('/spotify/playlists')
@require_spotify_auth
def get_spotify_playlists():
    """Get user's Spotify playlists."""
    try:
        playlists = spotify_service.get_playlists()
        return jsonify({'playlists': playlists})
    except Exception as e:
        print(f'Error fetching Spotify playlists: {str(e)}')
        return jsonify({'error': 'Failed to fetch playlists'}), 400


# Tidal endpoints
@api_bp.route('/tidal/playlists')
@require_tidal_auth
def get_tidal_playlists():
    """Get user's Tidal playlists."""
    try:
        playlists = tidal_service.get_playlists()
        return jsonify({'playlists': playlists})
    except Exception as e:
        print(f'Error fetching Tidal playlists: {str(e)}')
        return jsonify({'error': f'Failed to fetch Tidal playlists: {str(e)}'}), 500


# Transfer endpoints
@api_bp.route('/transfer', methods=['POST'])
@require_both_auth
def transfer_playlist():
    """Transfer a playlist from Spotify to Tidal."""
    playlist_id = request.json.get('playlist_id')
    playlist_type = request.json.get('playlist_type', 'playlist')
    
    if not playlist_id:
        return jsonify({'error': 'Missing playlist_id'}), 400
    
    try:
        # Get user ID for progress tracking
        user_id = tidal_service.get_owner_id()
        
        # Create transfer service
        transfer_service = TransferService(spotify_service, tidal_service)
        
        # Perform transfer
        result = transfer_service.transfer_playlist(playlist_id, playlist_type, user_id)
        
        return jsonify(result)
        
    except Exception as e:
        print(f'Error during transfer: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Transfer failed: {str(e)}'}), 500


@api_bp.route('/transfer-progress')
def transfer_progress_endpoint():
    """Get current transfer progress."""
    user_id = tidal_service.get_owner_id()
    progress = get_progress(user_id)
    return jsonify(progress)
