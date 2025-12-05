"""
Qobuz music streaming service implementation.
"""
import requests
from .base import MusicService
from config import QobuzConfig
from utils import sanitize_search_query


class QobuzService(MusicService):
    """Qobuz service implementation."""
    
    def __init__(self):
        """Initialize Qobuz service."""
        super().__init__(
            client_id=QobuzConfig.APP_ID,
            client_secret=QobuzConfig.APP_SECRET,
            redirect_uri=None,  # Qobuz doesn't use OAuth
            scope=None
        )
    
    @property
    def service_name(self):
        """Return the service name."""
        return 'qobuz'
    
    @property
    def token_url(self):
        """Return the token exchange URL."""
        return QobuzConfig.TOKEN_URL
    
    @property
    def auth_url(self):
        """Return the authorization URL."""
        return QobuzConfig.AUTH_URL
    
    def get_refresh_token_data(self, refresh_token):
        """
        Qobuz doesn't use refresh tokens.
        The user_auth_token is long-lived.
        """
        return None
    
    def get_api_headers(self):
        """Get headers for Qobuz API requests."""
        token = self.get_valid_token()
        return {
            'X-User-Auth-Token': token,
            'X-App-Id': self.client_id,
        }
    
    def get_owner_id(self):
        """
        Get the user ID for the authenticated user.
        Returns a simple identifier for progress tracking.
        """
        # Qobuz doesn't expose user ID in the same way as Tidal
        # We'll use the token hash as a unique identifier
        token = self.get_valid_token()
        return f"qobuz_{hash(token)}"
    
    def get_playlists(self):
        """
        Get user's playlists from Qobuz.
        
        Returns:
            list: List of playlist dictionaries with id, name, tracks, and type
        """
        headers = self.get_api_headers()
        
        print('\n=== Fetching Qobuz playlists ===')
        
        try:
            url = f'{QobuzConfig.API_BASE_URL}/playlist/getUserPlaylists'
            params = {
                'limit': 500,
                'offset': 0
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            print(f'Response status: {response.status_code}')
            
            if response.status_code != 200:
                print(f'ERROR: {response.text}')
                raise Exception(f'Failed to fetch playlists: {response.status_code}')
            
            data = response.json()
            playlists = []
            
            # The response has a 'playlists' key with items inside
            playlist_items = data.get('playlists', {}).get('items', [])
            
            for item in playlist_items:
                playlists.append({
                    'id': str(item.get('id')),
                    'name': item.get('name', 'Untitled'),
                    'tracks': item.get('tracks_count', 0),
                    'type': 'playlist'
                })
            
            print(f'✓ Found {len(playlists)} playlists')
            return playlists
            
        except Exception as e:
            print(f'EXCEPTION: {str(e)}')
            raise
    
    def create_playlist(self, name, description=''):
        """
        Create a new playlist on Qobuz.
        
        Args:
            name: Playlist name
            description: Playlist description
            
        Returns:
            str: Playlist ID
        """
        headers = self.get_api_headers()
        
        # Qobuz API uses form data, not JSON
        data = {
            'name': name,
            'is_public': 'false',  # Private by default
            'is_collaborative': 'false'
        }
        if description:
            data['description'] = description
        
        response = requests.post(
            f'{QobuzConfig.API_BASE_URL}/playlist/create',
            headers=headers,
            data=data  # Use data (form) instead of json
        )
        
        print(f'Create playlist response: {response.status_code}')
        
        if response.status_code not in [200, 201]:
            print(f'ERROR: {response.text}')
            raise Exception(f'Failed to create playlist: {response.status_code}')
        
        playlist_data = response.json()
        playlist_id = str(playlist_data.get('id'))
        
        if not playlist_id:
            raise Exception('Failed to get playlist ID from response')
        
        print(f'Created Qobuz playlist: {playlist_id}')
        return playlist_id
    
    def add_track_to_playlist(self, playlist_id, track_id):
        """
        Add a track to a Qobuz playlist.
        
        Args:
            playlist_id: ID of the playlist
            track_id: ID of the track to add
            
        Returns:
            bool: True if successful, False otherwise
        """
        headers = self.get_api_headers()
        
        # Qobuz uses form data with comma-separated track IDs
        data = {
            'playlist_id': str(playlist_id),
            'track_ids': str(track_id),  # Can be comma-separated for multiple
            'no_duplicate': 'true'  # Don't add duplicates
        }
        
        response = requests.post(
            f'{QobuzConfig.API_BASE_URL}/playlist/addTracks',
            headers=headers,
            data=data  # Use data (form) instead of json
        )
        
        if response.status_code in [200, 201, 204]:
            return True
        else:
            print(f'Failed to add track {track_id}: {response.status_code} - {response.text}')
            return False
    
    def search_track(self, track_name, artist_name):
        """
        Search for a track on Qobuz.
        
        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            
        Returns:
            str: Track ID if found, None otherwise
        """
        track_name_clean = sanitize_search_query(track_name)
        artist_name_clean = sanitize_search_query(artist_name)
        
        search_query = f'{artist_name_clean} {track_name_clean}'.strip()
        
        headers = self.get_api_headers()
        
        # Qobuz search endpoint from the API
        params = {
            'query': search_query,
            'limit': 1,  # Only need the first result
            'offset': 0
        }
        
        response = requests.get(
            f'{QobuzConfig.API_BASE_URL}/catalog/search',
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            # Search returns tracks in tracks.items
            tracks = data.get('tracks', {}).get('items', [])
            if tracks:
                return str(tracks[0].get('id'))
        
        return None
