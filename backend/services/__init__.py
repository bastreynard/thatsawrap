"""Music services package."""
from .base import MusicService
from .spotify_service import SpotifyService
from .tidal_service import TidalService
from .qobuz_service import QobuzService  # Add this line
from .transfer_service import TransferService

__all__ = ['MusicService', 'SpotifyService', 'TidalService', 'QobuzService', 'TransferService']
