"""
Base class for music streaming services.
"""
import time
import base64
import requests
from abc import ABC, abstractmethod
from flask import session


class MusicService(ABC):
    """Abstract base class for music streaming services."""
    
    def __init__(self, client_id, client_secret, redirect_uri, scope):
        """
        Initialize the music service.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: OAuth redirect URI
            scope: OAuth scope
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        
    @property
    @abstractmethod
    def service_name(self):
        """Return the service name (e.g., 'spotify', 'tidal')."""
        pass
    
    @property
    @abstractmethod
    def token_url(self):
        """Return the token exchange URL."""
        pass
    
    @property
    @abstractmethod
    def auth_url(self):
        """Return the authorization URL."""
        pass
    
    def get_token_key(self):
        """Get the session key for the access token."""
        return f'{self.service_name}_token'
    
    def get_refresh_token_key(self):
        """Get the session key for the refresh token."""
        return f'{self.service_name}_refresh_token'
    
    def get_token_expires_key(self):
        """Get the session key for token expiration."""
        return f'{self.service_name}_token_expires'
    
    def get_token(self):
        """Get the current access token from session."""
        return session.get(self.get_token_key())
    
    def get_refresh_token(self):
        """Get the refresh token from session."""
        return session.get(self.get_refresh_token_key())
    
    def get_token_expires(self):
        """Get token expiration timestamp from session."""
        return session.get(self.get_token_expires_key())
    
    def save_tokens(self, access_token, refresh_token=None, expires_in=3600):
        """
        Save tokens to session.
        
        Args:
            access_token: The access token
            refresh_token: The refresh token (optional)
            expires_in: Token lifetime in seconds
        """
        session[self.get_token_key()] = access_token
        if refresh_token:
            session[self.get_refresh_token_key()] = refresh_token
        session[self.get_token_expires_key()] = time.time() + expires_in
        session.modified = True
    
    def clear_tokens(self):
        """Clear all tokens from session."""
        session.pop(self.get_token_key(), None)
        session.pop(self.get_refresh_token_key(), None)
        session.pop(self.get_token_expires_key(), None)
    
    def get_basic_auth_header(self):
        """Get the Basic Authorization header value."""
        auth_str = f'{self.client_id}:{self.client_secret}'
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        return f'Basic {b64_auth}'
    
    def refresh_access_token(self):
        """
        Refresh the access token using the refresh token.
        
        Returns:
            bool: True if successful, False otherwise
        """
        refresh_token = self.get_refresh_token()
        
        if not refresh_token:
            print(f'No {self.service_name} refresh token available')
            return False
        
        print(f'Refreshing {self.service_name} token...')
        
        headers = {
            'Authorization': self.get_basic_auth_header(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = self.get_refresh_token_data(refresh_token)
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            
            if response.status_code == 200:
                tokens = response.json()
                new_access_token = tokens.get('access_token')
                new_refresh_token = tokens.get('refresh_token', refresh_token)
                
                self.save_tokens(new_access_token, new_refresh_token)
                
                print(f'✓ {self.service_name} token refreshed successfully')
                return True
            else:
                print(f'Failed to refresh {self.service_name} token: {response.status_code}')
                print(f'Response: {response.text}')
                return False
                
        except Exception as e:
            print(f'Exception refreshing {self.service_name} token: {str(e)}')
            return False
    
    @abstractmethod
    def get_refresh_token_data(self, refresh_token):
        """
        Get the data payload for token refresh.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            dict: Data to send in token refresh request
        """
        pass
    
    def get_valid_token(self):
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            str: Valid access token or None
        """
        token = self.get_token()
        expires = self.get_token_expires()
        
        if not token:
            return None
        
        # If we don't have expiry info, assume token is still valid
        if not expires:
            return token
        
        # If token expires in less than 5 minutes, refresh it
        if time.time() + 300 >= expires:
            if self.refresh_access_token():
                return self.get_token()
            return None
        
        return token
    
    def is_authenticated(self):
        """Check if the service is authenticated."""
        return bool(self.get_valid_token())
    
    @abstractmethod
    def get_playlists(self):
        """
        Get user's playlists from the service.
        
        Returns:
            list: List of playlist dictionaries
        """
        pass
    
    @abstractmethod
    def search_track(self, track_name, artist_name):
        """
        Search for a track on the service.
        
        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            
        Returns:
            str: Track ID if found, None otherwise
        """
        pass
