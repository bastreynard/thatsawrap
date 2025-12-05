"""
API routes for music service operations.
"""
from flask import Blueprint, jsonify, request, session
from functools import wraps
from services import SpotifyService, TidalService, QobuzService, TransferService
from utils import get_progress


# Initialize services
spotify_service = SpotifyService()
tidal_service = TidalService()
qobuz_service = QobuzService()

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

@api_bp.route('/qobuz/playlists')
def get_qobuz_playlists():
    """Get user's Qobuz playlists."""
    if not qobuz_service.is_authenticated():
        return jsonify({'error': 'Not authenticated with Qobuz'}), 401
    
    try:
        playlists = qobuz_service.get_playlists()
        return jsonify({'playlists': playlists})
    except Exception as e:
        print(f'Error fetching Qobuz playlists: {str(e)}')
        return jsonify({'error': f'Failed to fetch Qobuz playlists: {str(e)}'}), 500
    
# Transfer endpoints
@api_bp.route('/transfer', methods=['POST'])
@require_spotify_auth
def transfer_playlist():
    """Transfer a playlist from Spotify to a target service."""
    playlist_id = request.json.get('playlist_id')
    playlist_type = request.json.get('playlist_type', 'playlist')
    target_service_id = request.json.get('target_service', 'tidal')
    
    if not playlist_id:
        return jsonify({'error': 'Missing playlist_id'}), 400
    
    # Map service IDs to service instances
    service_map = {
        'tidal': tidal_service,
        'qobuz': qobuz_service,
        # 'youtube_music': youtube_music_service,
    }
    
    target_service = service_map.get(target_service_id)
    
    if not target_service:
        return jsonify({'error': f'Unknown target service: {target_service_id}'}), 400
    
    # Check target service authentication
    if not target_service.is_authenticated():
        return jsonify({'error': f'Not authenticated with {target_service_id}'}), 401
    
    # Store the current transfer service in session for progress tracking
    session['current_transfer_service'] = target_service_id
    
    # Get user ID for progress tracking
    try:
        if hasattr(target_service, 'get_owner_id'):
            user_id = target_service.get_owner_id()
        else:
            # Fallback: use service name as user ID
            user_id = f"{target_service_id}_user"
    except Exception as e:
        print(f"Warning: Could not get owner ID: {e}")
        user_id = f"{target_service_id}_user"
    
    # Store user ID in session
    session['user_id'] = user_id
    
    # Create transfer service
    transfer_service = TransferService(spotify_service, target_service)
    
    try:
        # Perform the transfer
        result = transfer_service.transfer_playlist(
            playlist_id=playlist_id,
            playlist_type=playlist_type,
            user_id=user_id
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f'Transfer error: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transfer-progress')
def transfer_progress_endpoint():
    """Get current transfer progress for any service."""
    # Get the target service from session (stored during transfer)
    target_service_id = session.get('current_transfer_service', 'tidal')
    
    # Map service IDs to service instances
    service_map = {
        'tidal': tidal_service,
        'qobuz': qobuz_service,
        # 'youtube_music': youtube_music_service,
    }
    
    target_service = service_map.get(target_service_id)
    
    if not target_service:
        return jsonify({'progress': 0, 'status': 'No active transfer'}), 200
    
    # Get user ID from the active service
    try:
        if hasattr(target_service, 'get_owner_id'):
            user_id = target_service.get_owner_id()
        else:
            # Fallback: use session-based user ID
            user_id = session.get('user_id', 'default')
    except Exception:
        user_id = session.get('user_id', 'default')
    
    progress = get_progress(user_id)
    return jsonify(progress)
