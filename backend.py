from flask import Flask, request, jsonify, redirect, session, Response
from flask_cors import CORS
from dotenv import load_dotenv
from urllib.parse import urlencode, quote
import requests
import base64
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from threading import Lock
from functools import wraps


# Load environment variables
load_dotenv()

app = Flask(__name__)

# Use a fixed secret key from .env, or generate one and save it
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    print("WARNING: No SECRET_KEY in .env file. Sessions will not persist across restarts!")
    SECRET_KEY = 'dev-secret-key-change-this-in-production'

app.secret_key = SECRET_KEY

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
if FLASK_ENV == 'production':
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True
else:
    # Configure session to work with CORS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_DOMAIN'] = None

CORS(app, supports_credentials=True, origins=[FRONTEND_URL])

# Configuration from environment variables
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback/spotify')

TIDAL_CLIENT_ID = os.getenv('TIDAL_CLIENT_ID')
TIDAL_CLIENT_SECRET = os.getenv('TIDAL_CLIENT_SECRET')
TIDAL_REDIRECT_URI = os.getenv('TIDAL_REDIRECT_URI', 'http://localhost:5000/callback/tidal')

# In-memory store for PKCE code verifiers (maps state to verifier)
pkce_store = {}

# Progress endpoints vars
transfer_progress = {}
progress_lock = Lock()

def set_progress(user_id, progress, added=0, total=0, current_track=''):
    with progress_lock:
        transfer_progress[user_id] = {'progress': progress, 'added': added, 'total': total, 'current_track': current_track}

def get_progress(user_id):
    with progress_lock:
        return transfer_progress.get(user_id, {'progress': 0, 'added': 0, 'total': 0, 'current_track': ''})

def sanitize_search_query(text):
    """
    Sanitize text for search queries by removing special characters
    that might break the search or cause poor results.
    """
    if not text:
        return ''
    
    import re
    
    # Remove content in parentheses (often remix info, features, etc.)
    # Example: "Song (Remix)" -> "Song", "Song (feat. Artist)" -> "Song"
    text = re.sub(r'\([^)]*\)', '', text)
    
    # Remove content in brackets
    text = re.sub(r'\[[^\]]*\]', '', text)
    
    # Remove common special characters that break searches
    # Keep: letters, numbers, spaces, apostrophes
    text = re.sub(r'[^\w\s\'-]', ' ', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text

# ============================================================================
# TOKEN REFRESH FUNCTIONS
# ============================================================================

def refresh_spotify_token():
    """Refresh Spotify access token using refresh token"""
    refresh_token = session.get('spotify_refresh_token')
    
    if not refresh_token:
        print('No Spotify refresh token available')
        return False
    
    print('Refreshing Spotify token...')
    
    auth_str = f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    token_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': f'Basic {b64_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            session['spotify_token'] = tokens.get('access_token')
            # Spotify may return a new refresh token
            if tokens.get('refresh_token'):
                session['spotify_refresh_token'] = tokens.get('refresh_token')
            session['spotify_token_expires'] = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
            session.modified = True
            
            print('✓ Spotify token refreshed successfully')
            return True
        else:
            print(f'Failed to refresh Spotify token: {response.status_code}')
            print(f'Response: {response.text}')
            return False
            
    except Exception as e:
        print(f'Exception refreshing Spotify token: {str(e)}')
        return False

def refresh_tidal_token():
    """Refresh Tidal access token using refresh token"""
    refresh_token = session.get('tidal_refresh_token')
    
    if not refresh_token:
        print('No Tidal refresh token available')
        return False
    
    print('Refreshing Tidal token...')
    
    auth_str = f'{TIDAL_CLIENT_ID}:{TIDAL_CLIENT_SECRET}'
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    token_url = 'https://auth.tidal.com/v1/oauth2/token'
    headers = {
        'Authorization': f'Basic {b64_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': TIDAL_CLIENT_ID
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            session['tidal_token'] = tokens.get('access_token')
            # Tidal may return a new refresh token
            if tokens.get('refresh_token'):
                session['tidal_refresh_token'] = tokens.get('refresh_token')
            session['tidal_token_expires'] = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
            session.modified = True
            
            print('✓ Tidal token refreshed successfully')
            return True
        else:
            print(f'Failed to refresh Tidal token: {response.status_code}')
            print(f'Response: {response.text}')
            return False
            
    except Exception as e:
        print(f'Exception refreshing Tidal token: {str(e)}')
        return False

def get_valid_spotify_token():
    """Get a valid Spotify token, refreshing if necessary"""
    token = session.get('spotify_token')
    expires = session.get('spotify_token_expires')
    
    if not token:
        return None
    
    # If we don't have expiry info, assume token is still valid
    if not expires:
        return token
    
    # Convert expires to naive datetime if it's offset-aware
    if isinstance(expires, datetime):
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
    
    # If token expires in less than 5 minutes, refresh it
    if datetime.now() + timedelta(minutes=5) >= expires:
        if refresh_spotify_token():
            return session.get('spotify_token')
        return None
    
    return token

def get_valid_tidal_token():
    """Get a valid Tidal token, refreshing if necessary"""
    token = session.get('tidal_token')
    expires = session.get('tidal_token_expires')
    
    if not token:
        return None
    
    # If we don't have expiry info, assume token is still valid
    if not expires:
        return token
    
    # Convert expires to naive datetime if it's offset-aware
    if isinstance(expires, datetime):
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
    
    # If token expires in less than 5 minutes, refresh it
    if datetime.now() + timedelta(minutes=5) >= expires:
        if refresh_tidal_token():
            return session.get('tidal_token')
        return None
    
    return token

# Decorator to require valid Spotify authentication
def require_spotify_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_valid_spotify_token()
        if not token:
            return jsonify({'error': 'Not authenticated with Spotify'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Decorator to require valid Tidal authentication
def require_tidal_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_valid_tidal_token()
        if not token:
            return jsonify({'error': 'Not authenticated with Tidal'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# OAUTH ENDPOINTS
# ============================================================================

# Spotify OAuth
@app.route('/auth/spotify')
def spotify_auth():
    # Request offline_access to get refresh token
    scope = 'playlist-read-private playlist-read-collaborative user-library-read'
    auth_url = (
        f'https://accounts.spotify.com/authorize?'
        f'client_id={SPOTIFY_CLIENT_ID}&'
        f'response_type=code&'
        f'redirect_uri={SPOTIFY_REDIRECT_URI}&'
        f'scope={scope}'
    )
    return redirect(auth_url)

@app.route('/callback/spotify')
def spotify_callback():
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
    auth_str = f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    token_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': f'Basic {b64_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI
    }
    
    print(f'Exchanging code for token...')
    print(f'Token URL: {token_url}')
    print(f'Redirect URI: {SPOTIFY_REDIRECT_URI}')
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        
        print(f'Token response status: {response.status_code}')
        print(f'Token response: {response.text[:200]}...')
        
        if response.status_code != 200:
            return f'<h2>Failed to get token</h2><p>{response.text}</p>', 400
        
        tokens = response.json()
        
        session['spotify_token'] = tokens.get('access_token')
        session['spotify_refresh_token'] = tokens.get('refresh_token')
        session['spotify_token_expires'] = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        session.modified = True
        
        print(f'✓ Spotify token saved: {session["spotify_token"][:20]}...')
        print(f'✓ Refresh token saved: {bool(session.get("spotify_refresh_token"))}')
        print(f'✓ Token expires: {session.get("spotify_token_expires")}')
        
        return redirect(FRONTEND_URL)
        
    except Exception as e:
        print(f'Exception during token exchange: {str(e)}')
        return f'<h2>Error</h2><p>{str(e)}</p>', 500

# Tidal OAuth with PKCE
@app.route('/auth/tidal')
def tidal_auth():
    print(f'\n=== Starting Tidal OAuth authorization flow ===')
    
    # Generate PKCE code verifier and challenge
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    # Generate a unique state parameter
    state = secrets.token_urlsafe(32)
    
    # Store code_verifier with state as key
    pkce_store[state] = {
        'verifier': code_verifier,
        'expires': datetime.now() + timedelta(minutes=10)
    }
    
    print(f'Generated PKCE code_verifier: {code_verifier[:20]}...')
    print(f'Generated PKCE code_challenge: {code_challenge[:20]}...')
    print(f'State parameter: {state[:20]}...')
    
    # Build authorization URL
    params = {
        'client_id': TIDAL_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': TIDAL_REDIRECT_URI,
        'scope': 'user.read playlists.read playlists.write collection.read collection.write',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state
    }
    
    auth_url = f'https://login.tidal.com/authorize?{urlencode(params)}'
    
    print(f'Redirecting to Tidal authorization URL')
    print(f'  Redirect URI: {TIDAL_REDIRECT_URI}')
    
    return redirect(auth_url)

@app.route('/callback/tidal')
def tidal_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    print(f'\n=== Tidal OAuth Callback ===')
    print(f'Authorization code: {code[:20] if code else None}...')
    print(f'State: {state[:20] if state else None}...')
    print(f'Error: {error}')
    
    if error:
        error_msg = f'{error}: {error_description}' if error_description else error
        print(f'Authorization failed: {error_msg}')
        return f'<h2>Authorization Failed</h2><p>{error_msg}</p><p><a href="{FRONTEND_URL}">Back</a></p>', 400
    
    if not code or not state:
        print('Missing code or state parameter')
        return '<h2>Missing parameters</h2><p><a href="/auth/tidal">Try again</a></p>', 400
    
    # Retrieve code_verifier
    pkce_data = pkce_store.get(state)
    
    if not pkce_data:
        print(f'ERROR: No PKCE data found for state: {state[:20]}...')
        return '<h2>Session expired</h2><p>PKCE state not found. <a href="/auth/tidal">Try again</a></p>', 400
    
    # Check if expired
    if datetime.now() > pkce_data['expires']:
        print('PKCE data expired')
        pkce_store.pop(state, None)
        return '<h2>Session expired</h2><p>Please <a href="/auth/tidal">try again</a></p>', 400
    
    code_verifier = pkce_data['verifier']
    print(f'Retrieved code_verifier: {code_verifier[:20]}...')
    
    # Clean up the PKCE store
    pkce_store.pop(state, None)
    
    # Exchange authorization code for access token
    token_url = 'https://auth.tidal.com/v1/oauth2/token'
    
    auth_str = f'{TIDAL_CLIENT_ID}:{TIDAL_CLIENT_SECRET}'
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {b64_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': TIDAL_REDIRECT_URI,
        'code_verifier': code_verifier,
        'client_id': TIDAL_CLIENT_ID
    }
    
    print(f'Exchanging code for token...')
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        
        print(f'Token response status: {response.status_code}')
        
        if response.status_code != 200:
            print(f'Token response body: {response.text}')
            return f'<h2>Token exchange failed</h2><p>Status: {response.status_code}</p><pre>{response.text}</pre><p><a href="/auth/tidal">Try again</a></p>', 400
        
        tokens = response.json()

        session['tidal_token'] = tokens.get('access_token')
        session['tidal_owner_id'] = tokens.get('user_id')
        session['tidal_refresh_token'] = tokens.get('refresh_token')
        session['tidal_token_expires'] = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        session.modified = True
        
        print(f'✓ Tidal token saved: {session["tidal_token"][:20]}...')
        print(f'✓ Owner ID: {session.get("tidal_owner_id")}')
        print(f'✓ Refresh token saved: {bool(session.get("tidal_refresh_token"))}')
        print(f'✓ Token expires: {session.get("tidal_token_expires")}')

        return redirect(FRONTEND_URL)
        
    except Exception as e:
        print(f'Exception: {str(e)}')
        return f'<h2>Error</h2><p>{str(e)}</p><p><a href="/auth/tidal">Try again</a></p>', 500

# Check auth status
@app.route('/auth/status')
def auth_status():
    print('\n=== Auth Status Check ===')
    print(f'Session keys: {list(session.keys())}')
    
    # Use the helper functions to get valid tokens
    spotify_token = get_valid_spotify_token()
    tidal_token = get_valid_tidal_token()
    tidal_owner_id = session.get('tidal_owner_id')
    
    spotify_status = bool(spotify_token)
    tidal_status = bool(tidal_token)
    
    print(f'Spotify authenticated: {spotify_status}')
    if spotify_status:
        print(f'  Spotify token: {spotify_token[:30]}...')
        print(f'  Token expires: {session.get("spotify_token_expires")}')
    
    print(f'Tidal authenticated: {tidal_status}')
    if tidal_status:
        print(f'  Tidal token: {tidal_token[:30]}...')
        print(f'  Tidal owner ID: {tidal_owner_id}')
        print(f'  Token expires: {session.get("tidal_token_expires")}')
    
    return jsonify({
        'spotify': spotify_status,
        'tidal': tidal_status
    })

# Disconnect endpoints
@app.route('/disconnect/spotify', methods=['POST'])
def disconnect_spotify():
    session.pop('spotify_token', None)
    session.pop('spotify_refresh_token', None)
    session.pop('spotify_token_expires', None)
    print('Spotify disconnected')
    return jsonify({'success': True})

@app.route('/disconnect/tidal', methods=['POST'])
def disconnect_tidal():
    session.pop('tidal_token', None)
    session.pop('tidal_owner_id', None)
    session.pop('tidal_refresh_token', None)
    session.pop('tidal_token_expires', None)
    print('Tidal disconnected')
    return jsonify({'success': True})

# ============================================================================
# API ENDPOINTS (with automatic token refresh)
# ============================================================================

# Get Spotify playlists
@app.route('/spotify/playlists')
@require_spotify_auth
def get_playlists():
    token = get_valid_spotify_token()
    
    headers = {'Authorization': f'Bearer {token}'}
    
    print('\n=== Fetching Spotify playlists ===')
    
    # Get user's playlists
    playlists_response = requests.get(
        'https://api.spotify.com/v1/me/playlists',
        headers=headers
    )
    
    print(f'Playlists response status: {playlists_response.status_code}')
    
    if playlists_response.status_code != 200:
        print(f'Error: {playlists_response.text}')
        return jsonify({'error': 'Failed to fetch playlists'}), 400
    
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
        'https://api.spotify.com/v1/me/tracks?limit=1',
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
    
    return jsonify({'playlists': playlists})

# Get Tidal playlists
@app.route('/tidal/playlists')
@require_tidal_auth
def get_tidal_playlists():
    token = get_valid_tidal_token()
    owner_id = session.get('tidal_owner_id')

    print('\n=== Fetching Tidal playlists ===')
    print(f'Token present: {bool(token)}')
    print(f'Token preview: {token[:30] if token else None}...')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.api+json'
    }

    try:
        url = f'https://openapi.tidal.com/v2/playlists'
        params = {
            'countryCode': 'US', 
            'filter[owners.id]': owner_id,
        }
        
        print(f'Making request to: {url}')
        
        response = requests.get(url, headers=headers, params=params)
        
        print(f'Response status: {response.status_code}')
        print(f'Response headers: {dict(response.headers)}')
        print(f'Response body preview: {response.text[:500]}...')
        
        if response.status_code != 200:
            print(f'ERROR: Non-200 status code')
            print(f'Full response body: {response.text}')
            return jsonify({'error': f'Failed to fetch Tidal playlists: {response.status_code}'}), 400
        
        data = response.json().get('data')
        print(f'Items in response: {len(data)}')
        
        playlists = []
        
        for idx, item in enumerate(data):
            attr = item.get("attributes")
            name = attr.get('name', 'Untitled')
            numItems = attr.get('numberOfItems', 0)
            print(f'  Playlist {idx+1}: {name} (id={item.get("id")}, tracks={numItems})')
            playlists.append({
                'id': item.get('id'),
                'name': name,
                'tracks': numItems,
                'type': 'playlist'
            })
        
        print(f'✓ Successfully parsed {len(playlists)} Tidal playlists')
        return jsonify({'playlists': playlists})
        
    except Exception as e:
        print(f'EXCEPTION: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to fetch Tidal playlists: {str(e)}'}), 500

# Transfer playlist
@app.route('/transfer', methods=['POST'])
def transfer_playlist():
    # Get valid tokens (with auto-refresh)
    spotify_token = get_valid_spotify_token()
    tidal_token = get_valid_tidal_token()
    
    if not spotify_token or not tidal_token:
        return jsonify({'error': 'Not authenticated with both services'}), 401
    
    playlist_id = request.json.get('playlist_id')
    playlist_type = request.json.get('playlist_type', 'playlist')
    
    print(f'\n=== Starting playlist transfer ===')
    print(f'Playlist ID: {playlist_id}')
    print(f'Type: {playlist_type}')
    
    spotify_headers = {'Authorization': f'Bearer {spotify_token}'}
    tidal_headers = {
        'Authorization': f'Bearer {tidal_token}',
        'Accept': 'application/vnd.api+json',
        'Content-Type': 'application/vnd.api+json'
    }
    
    # Handle liked songs differently
    if playlist_id == 'liked' or playlist_type == 'liked':
        print('Transferring Liked Songs')
        playlist_name = 'Liked Songs (from Spotify)'
        
        # Fetch all liked songs with pagination
        spotify_tracks = []
        offset = 0
        limit = 50
        
        while True:
            tracks_response = requests.get(
                f'https://api.spotify.com/v1/me/tracks?limit={limit}&offset={offset}',
                headers=spotify_headers
            )
            
            if tracks_response.status_code != 200:
                return jsonify({'error': 'Failed to fetch liked songs'}), 400
            
            tracks_data = tracks_response.json()
            items = tracks_data.get('items', [])
            
            if not items:
                break
            
            spotify_tracks.extend([item['track'] for item in items if item.get('track')])
            
            print(f'Fetched {len(items)} liked songs (offset {offset})')
            
            # Check if there are more tracks
            if tracks_data.get('next') is None:
                break
            
            offset += limit
        
        print(f'Total liked songs fetched: {len(spotify_tracks)}')
        
    else:
        # Get regular playlist
        playlist_response = requests.get(
            f'https://api.spotify.com/v1/playlists/{playlist_id}',
            headers=spotify_headers
        )
        
        if playlist_response.status_code != 200:
            return jsonify({'error': 'Failed to fetch playlist'}), 400
        
        playlist_data = playlist_response.json()
        playlist_name = playlist_data['name']
        
        # Fetch all playlist tracks with pagination
        spotify_tracks = []
        offset = 0
        limit = 100
        
        while True:
            tracks_response = requests.get(
                f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}',
                headers=spotify_headers
            )
            
            if tracks_response.status_code != 200:
                return jsonify({'error': 'Failed to fetch tracks'}), 400
            
            tracks_data = tracks_response.json()
            items = tracks_data.get('items', [])
            
            if not items:
                break
            
            spotify_tracks.extend([item['track'] for item in items if item.get('track')])
            
            print(f'Fetched {len(items)} tracks (offset {offset})')
            
            # Check if there are more tracks
            if tracks_data.get('next') is None:
                break
            
            offset += limit
        
        print(f'Total playlist tracks fetched: {len(spotify_tracks)}')
    
    print(f'Found {len(spotify_tracks)} tracks to transfer')
    
    # Create Tidal playlist
    create_response = requests.post(
        f'https://openapi.tidal.com/v2/playlists',
        headers=tidal_headers,
        params={'countryCode': 'US'},
        json={
            "data": {
                "type": "playlists",
                "attributes": {
                    "name": playlist_name,
                    "description": "Transferred from Spotify"
                }
            }
        }
    )
    
    print(f'Create playlist response: {create_response.status_code}')
    
    if create_response.status_code not in [200, 201]:
        status, title = create_response.json().get('status'), create_response.json().get('title')
        return jsonify({'error': f'Failed to create Tidal playlist : {status} {title}'}), 400
    
    tidal_playlist_data = create_response.json()
    tidal_playlist_id = tidal_playlist_data.get('data').get('id')
    
    if not tidal_playlist_id:
        print(f'No playlist ID in response: {tidal_playlist_data}')
        return jsonify({'error': 'Failed to get playlist ID'}), 400
    
    print(f'Created Tidal playlist: {tidal_playlist_id}')
    
    # Search and add tracks to Tidal
    added_count = 0
    not_found = []
    
    for idx, track in enumerate(spotify_tracks):
        if not track:
            continue
        progress = int(((idx + 1) / len(spotify_tracks)) * 100)
        set_progress(session.get("tidal_owner_id"), progress)
        
        # Get track and artist names
        track_name = track.get('name', '')
        artist_name = track['artists'][0]['name'] if track.get('artists') else ''
        
        # Sanitize for search (remove special characters)
        track_name_clean = sanitize_search_query(track_name)
        artist_name_clean = sanitize_search_query(artist_name)
        
        # Refresh Tidal token if needed during long transfer
        if idx % 20 == 0:  # Check every 20 tracks
            tidal_token = get_valid_tidal_token()
            tidal_headers['Authorization'] = f'Bearer {tidal_token}'
        
        # Search on Tidal using cleaned query
        search_query = f'{artist_name_clean} {track_name_clean}'.strip()
        
        # URL-encode the search query (spaces become %20, etc.)
        search_query_encoded = quote(search_query)
        
        search_response = requests.get(
            f'https://openapi.tidal.com/v2/searchResults/{search_query_encoded}/relationships/tracks',
            headers={'Authorization': f'Bearer {tidal_token}'},
            params={
                'explicitFilter': 'include',
                'countryCode': 'US',
            }
        )
        if search_response.status_code != 200:
            search_response = requests.get(
                f'https://openapi.tidal.com/v2/searchResults/{artist_name}%20{track_name}/relationships/topHits',
                headers={'Authorization': f'Bearer {tidal_token}'},
                params={
                    'explicitFilter': 'include, exclude',
                    'countryCode': 'US',
                }
            )
        if search_response.status_code == 200:
            search_data = search_response.json().get('data')
            if search_data and len(search_data) > 0:
                tidal_track_id = search_data[0].get('id')
                if tidal_track_id:
                    # Add track to playlist
                    add_response = requests.post(
                        f'https://openapi.tidal.com/v2/playlists/{tidal_playlist_id}/relationships/items',
                        headers=tidal_headers,
                        params={'countryCode': 'US'},
                        json={
                            "data": [{
                                "type": "tracks",
                                "id": str(tidal_track_id)
                            }],
                        }
                    )
                    
                    if add_response.status_code in [200, 201, 204]:
                        added_count += 1
                        print(f'✓ Added: {track_name} - {artist_name}')
                    else:
                        print(f'✗ Failed to add: {track_name} - {artist_name}')
                        not_found.append(f'{track_name} - {artist_name}')
                else:
                    not_found.append(f'{track_name} - {artist_name}')
                    print(f'✗ Not found on Tidal: {track_name} - {artist_name}')
            else:
                not_found.append(f'{track_name} - {artist_name}')
                print(f'✗ No results for: {track_name} - {artist_name}')
        else:
            not_found.append(f'{track_name} - {artist_name}')
            print(f'✗ Search failed for: {track_name} - {artist_name}')
    
    print(f'\n=== Transfer complete ===')
    print(f'Added: {added_count}/{len(spotify_tracks)}')

    return jsonify({
        'success': added_count != 0,
        'playlist_name': playlist_name,
        'total_tracks': len(spotify_tracks),
        'tracks_added': added_count,
        'tracks_not_found': len(not_found),
        'not_found_list': not_found[:10]
    })

@app.route('/transfer-progress')
def transfer_progress_endpoint():
    user_id = session.get("tidal_owner_id")
    return jsonify(get_progress(user_id))

if __name__ == '__main__':
    app.run(debug=True, port=5000)