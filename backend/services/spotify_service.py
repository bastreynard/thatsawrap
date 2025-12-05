"""
Spotify music streaming service implementation.
"""
import requests
from .base import MusicService
from config import SpotifyConfig


class SpotifyService(MusicService):
    """Spotify service implementation."""
    
    def __init__(self):
        """Initialize Spotify service."""
        super().__init__(
            client_id=SpotifyConfig.CLIENT_ID,
            client_secret=SpotifyConfig.CLIENT_SECRET,
            redirect_uri=SpotifyConfig.REDIRECT_URI,
            scope=SpotifyConfig.SCOPE
        )
    
    @property
    def service_name(self):
        """Return the service name."""
        return 'spotify'
    
    @property
    def token_url(self):
        """Return the token exchange URL."""
        return SpotifyConfig.TOKEN_URL
    
    @property
    def auth_url(self):
        """Return the authorization URL."""
        return SpotifyConfig.AUTH_URL
    
    def get_refresh_token_data(self, refresh_token):
        """Get the data payload for token refresh."""
        return {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    
    def get_api_headers(self):
        """Get headers for Spotify API requests."""
        token = self.get_valid_token()
        return {'Authorization': f'Bearer {token}'}
    
    def get_playlists(self):
        """
        Get user's playlists from Spotify.
        
        Returns:
            list: List of playlist dictionaries with id, name, tracks, and type
        """
        headers = self.get_api_headers()
        
        print('\n=== Fetching Spotify playlists ===')
        
        # Get user's playlists
        playlists_response = requests.get(
            f'{SpotifyConfig.API_BASE_URL}/me/playlists',
            headers=headers
        )
        
        print(f'Playlists response status: {playlists_response.status_code}')
        
        if playlists_response.status_code != 200:
            print(f'Error: {playlists_response.text}')
            raise Exception('Failed to fetch playlists')
        
        playlists_data = playlists_response.json()
        playlists = [
            {
                'id': p['id'],
                'name': p['name'],
                'tracks': p['tracks']['total'],
                'type': 'playlist'
            }
            for p in playlists_data.get('items', [])
        ]
        
        print(f'Found {len(playlists)} playlists')
        
        # Get liked songs count
        print('Fetching liked songs...')
        liked_response = requests.get(
            f'{SpotifyConfig.API_BASE_URL}/me/tracks?limit=1',
            headers=headers
        )
        
        print(f'Liked songs response status: {liked_response.status_code}')
        
        if liked_response.status_code == 200:
            liked_data = liked_response.json()
            liked_count = liked_data.get('total', 0)
            
            print(f'Found {liked_count} liked songs')
            
            if liked_count > 0:
                playlists.insert(0, {
                    'id': 'liked',
                    'name': 'Liked Songs',
                    'tracks': liked_count,
                    'type': 'liked'
                })
                print('Added Liked Songs to list')
        else:
            print(f'Failed to fetch liked songs: {liked_response.text}')
        
        print(f'Returning {len(playlists)} total items')
        
        return playlists
    
    def get_playlist_tracks(self, playlist_id, playlist_type='playlist'):
        """
        Get all tracks from a playlist or liked songs.
        
        Args:
            playlist_id: ID of the playlist or 'liked' for liked songs
            playlist_type: Type of playlist ('playlist' or 'liked')
            
        Returns:
            tuple: (playlist_name, list of tracks)
        """
        headers = self.get_api_headers()
        tracks = []
        
        # Handle liked songs differently
        if playlist_id == 'liked' or playlist_type == 'liked':
            print('Fetching Liked Songs')
            playlist_name = 'Liked Songs (from Spotify)'
            
            offset = 0
            limit = 50
            
            while True:
                response = requests.get(
                    f'{SpotifyConfig.API_BASE_URL}/me/tracks?limit={limit}&offset={offset}',
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise Exception('Failed to fetch liked songs')
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break
                
                tracks.extend([item['track'] for item in items if item.get('track')])
                
                print(f'Fetched {len(items)} liked songs (offset {offset})')
                
                if data.get('next') is None:
                    break
                
                offset += limit
        else:
            # Get regular playlist
            playlist_response = requests.get(
                f'{SpotifyConfig.API_BASE_URL}/playlists/{playlist_id}',
                headers=headers
            )
            
            if playlist_response.status_code != 200:
                raise Exception('Failed to fetch playlist')
            
            playlist_data = playlist_response.json()
            playlist_name = playlist_data['name']
            
            # Fetch all playlist tracks with pagination
            offset = 0
            limit = 100
            
            while True:
                response = requests.get(
                    f'{SpotifyConfig.API_BASE_URL}/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}',
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise Exception('Failed to fetch tracks')
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break
                
                tracks.extend([item['track'] for item in items if item.get('track')])
                
                print(f'Fetched {len(items)} tracks (offset {offset})')
                
                if data.get('next') is None:
                    break
                
                offset += limit
        
        print(f'Total tracks fetched: {len(tracks)}')
        return playlist_name, tracks
    
    def search_track(self, track_name, artist_name):
        """
        Search for a track on Spotify.
        
        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            
        Returns:
            str: Track ID if found, None otherwise
        """
        # This method is not typically used for Spotify as source
        # but included for completeness
        pass
