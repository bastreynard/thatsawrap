"""Routes package."""
from .auth_routes import auth_bp, callback_bp, disconnect_bp
from .api_routes import api_bp

__all__ = ['auth_bp', 'callback_bp', 'disconnect_bp', 'api_bp']
