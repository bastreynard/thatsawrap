"""
OAuth authentication routes.
"""
import time
import requests
from flask import Blueprint, request, redirect, session, jsonify
from urllib.parse import urlencode
from config import Config, SpotifyConfig, TidalConfig
from services import SpotifyService, TidalService


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# Initialize services
spotify_service = SpotifyService()
tidal_service = TidalService()


@auth_bp.route('/spotify')
def spotify_auth():
    """Initiate Spotify OAuth flow."""
    params = {
        'client_id': SpotifyConfig.CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SpotifyConfig.REDIRECT_URI,
        'scope': SpotifyConfig.SCOPE
    }
    auth_url = f'{SpotifyConfig.AUTH_URL}?{urlencode(params)}'
    return redirect(auth_url)


@auth_bp.route('/tidal')
def tidal_auth():
    """Initiate Tidal OAuth flow with PKCE."""
    print(f'\n=== Starting Tidal OAuth authorization flow ===')
    
    # Generate PKCE pair
    code_verifier, code_challenge, state = tidal_service.generate_pkce_pair()
    
    print(f'Generated PKCE code_verifier: {code_verifier[:20]}...')
    print(f'Generated PKCE code_challenge: {code_challenge[:20]}...')
    print(f'State parameter: {state}...')
    
    # Build authorization URL
    params = {
        'client_id': TidalConfig.CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': TidalConfig.REDIRECT_URI,
        'scope': TidalConfig.SCOPE,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state
    }
    
    auth_url = f'{TidalConfig.AUTH_URL}?{urlencode(params)}'
    
    print(f'Redirecting to Tidal authorization URL')
    print(f'  Redirect URI: {TidalConfig.REDIRECT_URI}')
    
    return redirect(auth_url)


@auth_bp.route('/status')
def auth_status():
    """Check authentication status for all services."""
    print('\n=== Auth Status Check ===')
    print(f'Session keys: {list(session.keys())}')
    
    spotify_status = spotify_service.is_authenticated()
    tidal_status = tidal_service.is_authenticated()
    
    print(f'Spotify authenticated: {spotify_status}')
    print(f'Tidal authenticated: {tidal_status}')
    
    return jsonify({
        'spotify': spotify_status,
        'tidal': tidal_status
    })


# Callback routes (in separate blueprint for cleaner organization)
callback_bp = Blueprint('callback', __name__, url_prefix='/callback')


@callback_bp.route('/spotify')
def spotify_callback():
    """Handle Spotify OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')
    
    print(f'\n=== Spotify OAuth Callback ===')
    print(f'Authorization code: {code[:20] if code else None}...')
    print(f'Error: {error}')
    
    if error:
        print(f'Spotify authorization failed: {error}')
        return f'<h2>Spotify Authorization Error</h2><p>{error}</p>', 400
    
    if not code:
        print('No authorization code received')
        return '<h2>No authorization code</h2>', 400
    
    # Exchange code for token
    headers = {
        'Authorization': spotify_service.get_basic_auth_header(),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SpotifyConfig.REDIRECT_URI
    }
    
    print(f'Exchanging code for token...')
    
    try:
        response = requests.post(SpotifyConfig.TOKEN_URL, headers=headers, data=data)
        
        print(f'Token response status: {response.status_code}')
        
        if response.status_code != 200:
            return f'<h2>Failed to get token</h2><p>{response.text}</p>', 400
        
        tokens = response.json()
        
        spotify_service.save_tokens(
            access_token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            expires_in=3600
        )
        
        print(f'✓ Spotify token saved')
        print(f'✓ Refresh token saved: {bool(tokens.get("refresh_token"))}')
        
        return redirect(Config.FRONTEND_URL)
        
    except Exception as e:
        print(f'Exception during token exchange: {str(e)}')
        return f'<h2>Error</h2><p>{str(e)}</p>', 500


@callback_bp.route('/tidal')
def tidal_callback():
    """Handle Tidal OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    print(f'\n=== Tidal OAuth Callback ===')
    print(f'Authorization code: {code[:20] if code else None}...')
    print(f'State: {state if state else None}...')
    print(f'Error: {error}')
    
    if error:
        error_msg = f'{error}: {error_description}' if error_description else error
        print(f'Authorization failed: {error_msg}')
        return f'<h2>Authorization Failed</h2><p>{error_msg}</p><p><a href="{Config.FRONTEND_URL}">Back</a></p>', 400
    
    if not code or not state:
        print('Missing code or state parameter')
        return '<h2>Missing parameters</h2><p><a href="/auth/tidal">Try again</a></p>', 400
    
    # Retrieve code_verifier
    code_verifier = tidal_service.get_pkce_verifier()
    
    if not code_verifier:
        print(f'ERROR: No PKCE data found or expired')
        return '<h2>Session expired</h2><p>PKCE state not found. <a href="/auth/tidal">Try again</a></p>', 400
    
    print(f'Retrieved code_verifier: {code_verifier[:20]}...')
    
    # Exchange authorization code for access token
    headers = {
        'Authorization': tidal_service.get_basic_auth_header(),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': TidalConfig.REDIRECT_URI,
        'code_verifier': code_verifier,
        'client_id': TidalConfig.CLIENT_ID
    }
    
    print(f'Exchanging code for token...')
    
    try:
        response = requests.post(TidalConfig.TOKEN_URL, headers=headers, data=data)
        
        print(f'Token response status: {response.status_code}')
        
        if response.status_code != 200:
            print(f'Token response body: {response.text}')
            return f'<h2>Token exchange failed</h2><p>Status: {response.status_code}</p><pre>{response.text}</pre><p><a href="/auth/tidal">Try again</a></p>', 400
        
        tokens = response.json()
        
        tidal_service.save_tokens(
            access_token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            expires_in=3600,
            owner_id=tokens.get('user_id')
        )
        
        # Clear PKCE data
        tidal_service.clear_pkce()
        
        print(f'✓ Tidal token saved')
        print(f'✓ Owner ID: {tokens.get("user_id")}')
        print(f'✓ Refresh token saved: {bool(tokens.get("refresh_token"))}')
        
        return redirect(Config.FRONTEND_URL)
        
    except Exception as e:
        print(f'Exception: {str(e)}')
        return f'<h2>Error</h2><p>{str(e)}</p><p><a href="/auth/tidal">Try again</a></p>', 500


# Disconnect routes
disconnect_bp = Blueprint('disconnect', __name__, url_prefix='/disconnect')


@disconnect_bp.route('/spotify', methods=['POST'])
def disconnect_spotify():
    """Disconnect Spotify account."""
    spotify_service.clear_tokens()
    print('Spotify disconnected')
    return jsonify({'success': True})


@disconnect_bp.route('/tidal', methods=['POST'])
def disconnect_tidal():
    """Disconnect Tidal account."""
    tidal_service.clear_tokens()
    print('Tidal disconnected')
    return jsonify({'success': True})
