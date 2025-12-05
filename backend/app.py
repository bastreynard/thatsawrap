"""
Main application file for Spotify to Tidal playlist transfer service.
"""
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config, VERSION_TAG, GIT_COMMIT_HASH
from routes import auth_bp, callback_bp, disconnect_bp, api_bp


def create_app():
    """
    Application factory for creating Flask app.
    
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    app.secret_key = Config.SECRET_KEY
    if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev-secret-key-change-this-in-production':
        print("WARNING: No SECRET_KEY in .env file. Sessions will not persist across restarts!")
    
    # Configure session
    Config.configure_session(app)
    
    # Configure CORS
    CORS(app, supports_credentials=True, origins=[Config.FRONTEND_URL])
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(callback_bp)
    app.register_blueprint(disconnect_bp)
    app.register_blueprint(api_bp)
    
    # Version endpoint
    @app.route('/version')
    def get_version():
        """Get version information."""
        return jsonify({
            'tag': VERSION_TAG,
            'hash': GIT_COMMIT_HASH
        })
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return jsonify({'status': 'healthy'})
    
    return app
    
