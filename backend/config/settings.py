"""
Application configuration and environment variables.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Base configuration."""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-this-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    # Session configuration
    SESSION_COOKIE_HTTPONLY = True
    
    @classmethod
    def configure_session(cls, app):
        """Configure session settings based on environment."""
        if cls.FLASK_ENV == 'production':
            app.config['SESSION_COOKIE_SAMESITE'] = 'None'
            app.config['SESSION_COOKIE_SECURE'] = True
        else:
            app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
            app.config['SESSION_COOKIE_SECURE'] = False
            app.config['SESSION_COOKIE_DOMAIN'] = None


class SpotifyConfig:
    """Spotify API configuration."""
    
    CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
    REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback/spotify')
    SCOPE = 'playlist-read-private playlist-read-collaborative user-library-read'
    
    # API endpoints
    AUTH_URL = 'https://accounts.spotify.com/authorize'
    TOKEN_URL = 'https://accounts.spotify.com/api/token'
    API_BASE_URL = 'https://api.spotify.com/v1'


class TidalConfig:
    """Tidal API configuration."""
    
    CLIENT_ID = os.getenv('TIDAL_CLIENT_ID')
    CLIENT_SECRET = os.getenv('TIDAL_CLIENT_SECRET')
    REDIRECT_URI = os.getenv('TIDAL_REDIRECT_URI', 'http://localhost:5000/callback/tidal')
    SCOPE = 'user.read playlists.read playlists.write collection.read collection.write'
    
    # API endpoints
    AUTH_URL = 'https://login.tidal.com/authorize'
    TOKEN_URL = 'https://auth.tidal.com/v1/oauth2/token'
    API_BASE_URL = 'https://openapi.tidal.com/v2'
    COUNTRY_CODE = 'US'


# Version info
VERSION_TAG = os.getenv('VERSION_TAG', 'dev')
GIT_COMMIT_HASH = os.getenv('GIT_COMMIT_HASH', 'unknown')
