"""
Tidal music streaming service implementation.
"""
import time
import base64
import hashlib
import secrets
import requests
from urllib.parse import quote
from flask import session
from .base import MusicService
from config import TidalConfig
from utils import sanitize_search_query


class TidalService(MusicService):
    """Tidal service implementation."""
    
    def __init__(self):
        """Initialize Tidal service."""
        super().__init__(
            client_id=TidalConfig.CLIENT_ID,
            client_secret=TidalConfig.CLIENT_SECRET,
            redirect_uri=TidalConfig.REDIRECT_URI,
            scope=TidalConfig.SCOPE
        )
    
    @property
    def service_name(self):
        """Return the service name."""
        return 'tidal'
    
    @property
    def token_url(self):
        """Return the token exchange URL."""
        return TidalConfig.TOKEN_URL
    
    @property
    def auth_url(self):
        """Return the authorization URL."""
        return TidalConfig.AUTH_URL
    
    def get_owner_id(self):
        """Get the Tidal user/owner ID from session."""
        return session.get('tidal_owner_id')
    
    def save_tokens(self, access_token, refresh_token=None, expires_in=3600, owner_id=None):
        """
        Save tokens to session.
        
        Args:
            access_token: The access token
            refresh_token: The refresh token (optional)
            expires_in: Token lifetime in seconds
            owner_id: Tidal user ID (optional)
        """
        super().save_tokens(access_token, refresh_token, expires_in)
        if owner_id:
            session['tidal_owner_id'] = owner_id
    
    def clear_tokens(self):
        """Clear all tokens from session."""
        super().clear_tokens()
        session.pop('tidal_owner_id', None)
    
    def get_refresh_token_data(self, refresh_token):
        """Get the data payload for token refresh."""
        return {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id
        }
    
    def generate_pkce_pair(self):
        """
        Generate PKCE code verifier and challenge.
        
        Returns:
            tuple: (code_verifier, code_challenge, state)
        """
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        state = secrets.token_urlsafe(32)
        
        # Store in session
        session['pkce'] = {
            'state': state,
            'verifier': code_verifier,
            'expires': time.time() + 600  # 10 minutes
        }
        
        return code_verifier, code_challenge, state
    
    def get_pkce_verifier(self):
        """
        Get the PKCE code verifier from session.
        
        Returns:
            str: Code verifier or None if not found/expired
        """
        pkce_data = session.get('pkce')
        
        if not pkce_data:
            return None
        
        # Check if expired
        if time.time() > pkce_data['expires']:
            session.pop('pkce', None)
            return None
        
        return pkce_data['verifier']
    
    def clear_pkce(self):
        """Clear PKCE data from session."""
        session.pop('pkce', None)
    
    def get_api_headers(self):
        """Get headers for Tidal API requests."""
        token = self.get_valid_token()
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'
        }
    
    def get_playlists(self):
        """
        Get user's playlists from Tidal.
        
        Returns:
            list: List of playlist dictionaries with id, name, tracks, and type
        """
        owner_id = self.get_owner_id()
        
        print('\n=== Fetching Tidal playlists ===')
        print(f'Owner ID: {owner_id}')
        
        headers = self.get_api_headers()
        
        try:
            url = f'{TidalConfig.API_BASE_URL}/playlists'
            params = {
                'countryCode': TidalConfig.COUNTRY_CODE,
                'filter[owners.id]': owner_id,
            }
            
            print(f'Making request to: {url}')
            
            response = requests.get(url, headers=headers, params=params)
            
            print(f'Response status: {response.status_code}')
            
            if response.status_code != 200:
                print(f'ERROR: Non-200 status code')
                print(f'Full response body: {response.text}')
                raise Exception(f'Failed to fetch Tidal playlists: {response.status_code}')
            
            data = response.json().get('data', [])
            print(f'Items in response: {len(data)}')
            
            playlists = []
            
            for idx, item in enumerate(data):
                attr = item.get("attributes", {})
                name = attr.get('name', 'Untitled')
                num_items = attr.get('numberOfItems', 0)
                print(f'  Playlist {idx+1}: {name} (id={item.get("id")}, tracks={num_items})')
                playlists.append({
                    'id': item.get('id'),
                    'name': name,
                    'tracks': num_items,
                    'type': 'playlist'
                })
            
            print(f'✓ Successfully parsed {len(playlists)} Tidal playlists')
            return playlists
            
        except Exception as e:
            print(f'EXCEPTION: {str(e)}')
            import traceback
            traceback.print_exc()
            raise
    
    def create_playlist(self, name, description=''):
        """
        Create a new playlist on Tidal.
        
        Args:
            name: Playlist name
            description: Playlist description
            
        Returns:
            str: Playlist ID
        """
        headers = self.get_api_headers()
        
        response = requests.post(
            f'{TidalConfig.API_BASE_URL}/playlists',
            headers=headers,
            params={'countryCode': TidalConfig.COUNTRY_CODE},
            json={
                "data": {
                    "type": "playlists",
                    "attributes": {
                        "name": name,
                        "description": description
                    }
                }
            }
        )
        
        print(f'Create playlist response: {response.status_code}')
        
        if response.status_code not in [200, 201]:
            error_data = response.json()
            status = error_data.get('status')
            title = error_data.get('title')
            raise Exception(f'Failed to create Tidal playlist: {status} {title}')
        
        playlist_data = response.json()
        playlist_id = playlist_data.get('data', {}).get('id')
        
        if not playlist_id:
            raise Exception('Failed to get playlist ID from response')
        
        print(f'Created Tidal playlist: {playlist_id}')
        return playlist_id
    
    def add_track_to_playlist(self, playlist_id, track_id):
        """
        Add a track to a Tidal playlist.
        
        Args:
            playlist_id: ID of the playlist
            track_id: ID of the track to add
            
        Returns:
            bool: True if successful, False otherwise
        """
        headers = self.get_api_headers()
        
        response = requests.post(
            f'{TidalConfig.API_BASE_URL}/playlists/{playlist_id}/relationships/items',
            headers=headers,
            params={'countryCode': TidalConfig.COUNTRY_CODE},
            json={
                "data": [{
                    "type": "tracks",
                    "id": str(track_id)
                }],
            }
        )
        
        return response.status_code in [200, 201, 204]
    
    def search_track(self, track_name, artist_name):
        """
        Search for a track on Tidal.
        
        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            
        Returns:
            str: Track ID if found, None otherwise
        """
        # Sanitize for search
        track_name_clean = sanitize_search_query(track_name)
        artist_name_clean = sanitize_search_query(artist_name)
        
        search_query = f'{artist_name_clean} {track_name_clean}'.strip()
        search_query_encoded = quote(search_query)
        
        token = self.get_valid_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        # Try searching tracks first
        response = requests.get(
            f'{TidalConfig.API_BASE_URL}/searchResults/{search_query_encoded}/relationships/tracks',
            headers=headers,
            params={
                'explicitFilter': 'include',
                'countryCode': TidalConfig.COUNTRY_CODE,
            }
        )
        
        # If that fails, try top hits
        if response.status_code != 200:
            response = requests.get(
                f'{TidalConfig.API_BASE_URL}/searchResults/{artist_name}%20{track_name}/relationships/topHits',
                headers=headers,
                params={
                    'explicitFilter': 'include, exclude',
                    'countryCode': TidalConfig.COUNTRY_CODE,
                }
            )
        
        if response.status_code == 200:
            search_data = response.json().get('data', [])
            if search_data and len(search_data) > 0:
                return search_data[0].get('id')
        
        return None
