from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
from dotenv import load_dotenv
from urllib.parse import urlencode
import requests
import base64
import os
import hashlib
import secrets
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Use a fixed secret key from .env, or generate one and save it
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    print("WARNING: No SECRET_KEY in .env file. Sessions will not persist across restarts!")
    SECRET_KEY = 'dev-secret-key-change-this-in-production'

app.secret_key = SECRET_KEY

# Configure session to work with CORS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_DOMAIN'] = None

CORS(app, supports_credentials=True, origins=['http://127.0.0.1:3000'])

# Configuration from environment variables
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback/spotify')

TIDAL_CLIENT_ID = os.getenv('TIDAL_CLIENT_ID')
TIDAL_CLIENT_SECRET = os.getenv('TIDAL_CLIENT_SECRET')
TIDAL_REDIRECT_URI = os.getenv('TIDAL_REDIRECT_URI', 'http://localhost:5000/callback/tidal')

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# In-memory store for PKCE code verifiers (maps state to verifier)
pkce_store = {}

# Spotify OAuth
@app.route('/auth/spotify')
def spotify_auth():
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
        session.modified = True  # Force session save
        
        print(f'✓ Spotify token saved: {session["spotify_token"][:20]}...')
        print(f'✓ Session ID after save: {id(session)}')
        
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
    
    # Generate a unique state parameter to link challenge and verifier
    state = secrets.token_urlsafe(32)
    
    # Store code_verifier with state as key (in-memory, expires in 10 minutes)
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
    
    # Retrieve code_verifier from in-memory store using state
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
        session['tidal_refresh_token'] = tokens.get('refresh_token')
        session['tidal_user_id'] = tokens.get('user', {}).get('userId') or tokens.get('userId')
        session.modified = True  # Force session save
        
        print(f'✓ Tidal token saved: {session["tidal_token"][:20]}...')
        print(f'✓ User ID: {session.get("tidal_user_id")}')
        print(f'✓ Session saved')
        
        # Use server-side redirect instead of JavaScript
        return redirect(FRONTEND_URL)
        
    except Exception as e:
        print(f'Exception: {str(e)}')
        return f'<h2>Error</h2><p>{str(e)}</p><p><a href="/auth/tidal">Try again</a></p>', 500

# Check auth status
@app.route('/auth/status')
def auth_status():
    spotify_status = 'spotify_token' in session
    tidal_status = 'tidal_token' in session
    
    print(f'Auth status check - Spotify: {spotify_status}, Tidal: {tidal_status}')
    if spotify_status:
        print(f'  Spotify token: {session.get("spotify_token")[:20]}...')
    if tidal_status:
        print(f'  Tidal token: {session.get("tidal_token")[:20]}...')
    
    return jsonify({
        'spotify': spotify_status,
        'tidal': tidal_status
    })

# Disconnect endpoints
@app.route('/disconnect/spotify', methods=['POST'])
def disconnect_spotify():
    session.pop('spotify_token', None)
    print('Spotify disconnected')
    return jsonify({'success': True})

@app.route('/disconnect/tidal', methods=['POST'])
def disconnect_tidal():
    session.pop('tidal_token', None)
    session.pop('tidal_user_id', None)
    print('Tidal disconnected')
    return jsonify({'success': True})

# Get Spotify playlists
@app.route('/playlists')
def get_playlists():
    token = session.get('spotify_token')
    if not token:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
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
        
        # Add liked songs as a special "playlist"
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
def get_tidal_playlists():
    token = session.get('tidal_token')
    user_id = session.get('tidal_user_id')
    
    if not token:
        return jsonify({'error': 'Not authenticated with Tidal'}), 401
    
    print('\n=== Fetching Tidal playlists ===')
    print(f'User ID: {user_id}')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    # Try multiple possible endpoints
    endpoints_to_try = [
        f'https://listen.tidal.com/v2/my-collection/playlists/folders',
        f'https://api.tidal.com/v1/users/{user_id}/playlists',
        f'https://openapi.tidal.com/v2/my-collection/playlists/folders'
    ]
    
    for endpoint in endpoints_to_try:
        try:
            print(f'Trying endpoint: {endpoint}')
            response = requests.get(endpoint, headers=headers)
            
            print(f'Response status: {response.status_code}')
            
            if response.status_code == 200:
                data = response.json()
                print(f'Response data keys: {list(data.keys()) if isinstance(data, dict) else "not a dict"}')
                playlists = []
                
                # Try different response structures
                items = (
                    data.get('items') or 
                    data.get('data') or 
                    data.get('playlists') or
                    []
                )
                
                for item in items:
                    # Handle different playlist structures
                    if isinstance(item, dict):
                        playlist_id = item.get('uuid') or item.get('id')
                        playlist_name = item.get('title') or item.get('name') or 'Untitled'
                        track_count = item.get('numberOfTracks') or item.get('numberOfItems') or 0
                        
                        if playlist_id:
                            playlists.append({
                                'id': playlist_id,
                                'name': playlist_name,
                                'tracks': track_count,
                                'type': 'playlist'
                            })
                
                print(f'Found {len(playlists)} Tidal playlists')
                if playlists:
                    return jsonify({'playlists': playlists})
        
        except Exception as e:
            print(f'Error with endpoint {endpoint}: {str(e)}')
            continue
    
    # If all endpoints failed, return empty list
    print('All endpoints failed, returning empty list')
    return jsonify({'playlists': []})

# Transfer playlist
@app.route('/transfer', methods=['POST'])
def transfer_playlist():
    spotify_token = session.get('spotify_token')
    tidal_token = session.get('tidal_token')
    tidal_user_id = session.get('tidal_user_id')
    
    if not spotify_token or not tidal_token:
        return jsonify({'error': 'Not authenticated with both services'}), 401
    
    playlist_id = request.json.get('playlist_id')
    playlist_type = request.json.get('playlist_type', 'playlist')
    
    print(f'\n=== Starting playlist transfer ===')
    print(f'Playlist ID: {playlist_id}')
    print(f'Type: {playlist_type}')
    
    spotify_headers = {'Authorization': f'Bearer {spotify_token}'}
    
    # Handle liked songs differently
    if playlist_id == 'liked' or playlist_type == 'liked':
        print('Transferring Liked Songs')
        playlist_name = 'Liked Songs (from Spotify)'
        
        # Get liked songs
        tracks_response = requests.get(
            'https://api.spotify.com/v1/me/tracks?limit=50',
            headers=spotify_headers
        )
        
        if tracks_response.status_code != 200:
            return jsonify({'error': 'Failed to fetch liked songs'}), 400
        
        tracks_data = tracks_response.json()
        spotify_tracks = [item['track'] for item in tracks_data.get('items', []) if item.get('track')]
        
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
        
        # Get all tracks
        tracks_response = requests.get(
            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
            headers=spotify_headers
        )
        
        if tracks_response.status_code != 200:
            return jsonify({'error': 'Failed to fetch tracks'}), 400
        
        tracks_data = tracks_response.json()
        spotify_tracks = [item['track'] for item in tracks_data.get('items', []) if item.get('track')]
    
    print(f'Found {len(spotify_tracks)} tracks to transfer')
    
    # Create Tidal playlist using the unofficial endpoint
    tidal_headers = {
        'Authorization': f'Bearer {tidal_token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    # Try the unofficial v2 endpoint for creating playlists
    create_response = requests.post(
        'https://listen.tidal.com/v2/my-collection/playlists/folders/create-playlist',
        headers=tidal_headers,
        json={
            'name': playlist_name,
            'description': 'Transferred from Spotify via That\'s a wrap'
        }
    )
    
    print(f'Create playlist response: {create_response.status_code}')
    print(f'Response: {create_response.text[:200]}')
    
    if create_response.status_code not in [200, 201]:
        print(f'Failed to create playlist: {create_response.text}')
        return jsonify({'error': f'Failed to create Tidal playlist. The Tidal API for playlist creation may not be available yet.'}), 400
    
    tidal_playlist_data = create_response.json()
    # The response structure may vary, try different possible locations for the ID
    tidal_playlist_id = (
        tidal_playlist_data.get('data', {}).get('id') or 
        tidal_playlist_data.get('id') or 
        tidal_playlist_data.get('uuid')
    )
    
    if not tidal_playlist_id:
        print(f'Playlist created but no ID found. Response: {tidal_playlist_data}')
        return jsonify({'error': 'Playlist created but could not get playlist ID'}), 400
    
    print(f'Created Tidal playlist: {tidal_playlist_id}')
    
    # Search and add tracks to Tidal
    added_count = 0
    not_found = []
    
    for track in spotify_tracks[:50]:  # Limit to first 50 for now
        if not track:
            continue
        
        track_name = track.get('name', '')
        artist_name = track['artists'][0]['name'] if track.get('artists') else ''
        
        # Search on Tidal using v2 API
        search_response = requests.get(
            'https://openapi.tidal.com/v2/searchresults/catalog',
            headers=tidal_headers,
            params={
                'query': f'{track_name} {artist_name}',
                'type': 'TRACKS',
                'limit': 1
            }
        )
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            tracks = search_data.get('data', [])
            
            if tracks and len(tracks) > 0:
                tidal_track = tracks[0]
                tidal_track_id = tidal_track.get('id')
                
                if tidal_track_id:
                    # Add track to playlist
                    add_response = requests.put(
                        f'https://openapi.tidal.com/v2/playlists/{tidal_playlist_id}/items',
                        headers=tidal_headers,
                        json={
                            'trackIds': [tidal_track_id]
                        }
                    )
                    
                    if add_response.status_code in [200, 201, 204]:
                        added_count += 1
                        print(f'✓ Added: {track_name} - {artist_name}')
                    else:
                        print(f'✗ Failed to add: {track_name} - {artist_name}')
                else:
                    not_found.append(f'{track_name} - {artist_name}')
            else:
                not_found.append(f'{track_name} - {artist_name}')
                print(f'✗ Not found on Tidal: {track_name} - {artist_name}')
    
    print(f'\n=== Transfer complete ===')
    print(f'Added: {added_count}/{len(spotify_tracks)}')
    print(f'Not found: {len(not_found)}')
    
    return jsonify({
        'success': True,
        'playlist_name': playlist_name,
        'total_tracks': len(spotify_tracks),
        'tracks_added': added_count,
        'tracks_not_found': len(not_found),
        'not_found_list': not_found[:10]  # Return first 10 not found
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)