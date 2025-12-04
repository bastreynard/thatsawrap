from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import base64
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
CORS(app, supports_credentials=True)

# Configuration from environment variables
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:5000/callback/spotify')

TIDAL_CLIENT_ID = os.getenv('TIDAL_CLIENT_ID')
TIDAL_CLIENT_SECRET = os.getenv('TIDAL_CLIENT_SECRET')
TIDAL_REDIRECT_URI = os.getenv('TIDAL_REDIRECT_URI', 'http://127.0.0.1:5000/callback/tidal')

# Spotify OAuth
@app.route('/auth/spotify')
def spotify_auth():
    scope = 'playlist-read-private playlist-read-collaborative'
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
    
    response = requests.post(token_url, headers=headers, data=data)
    tokens = response.json()
    
    session['spotify_token'] = tokens.get('access_token')
    return redirect('http://localhost:3000')

# Tidal OAuth
@app.route('/auth/tidal')
def tidal_auth():
    scope = 'r_usr w_usr'
    auth_url = (
        f'https://auth.tidal.com/v1/oauth2/authorize?'
        f'client_id={TIDAL_CLIENT_ID}&'
        f'response_type=code&'
        f'redirect_uri={TIDAL_REDIRECT_URI}&'
        f'scope={scope}'
    )
    return redirect(auth_url)

@app.route('/callback/tidal')
def tidal_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f'Tidal OAuth Error: {error}', 400
    
    if not code:
        return 'No authorization code received', 400
    
    token_url = 'https://auth.tidal.com/v1/oauth2/token'
    
    # Tidal expects form-encoded data with Basic auth
    auth_str = f'{TIDAL_CLIENT_ID}:{TIDAL_CLIENT_SECRET}'
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {b64_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': TIDAL_REDIRECT_URI
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    
    print(f'Tidal token response status: {response.status_code}')
    print(f'Tidal token response: {response.text}')
    
    if response.status_code != 200:
        return f'Failed to get Tidal token: {response.text}', 400
    
    tokens = response.json()
    
    session['tidal_token'] = tokens.get('access_token')
    session['tidal_user_id'] = tokens.get('user', {}).get('userId')
    
    print(f'Tidal token saved: {session.get("tidal_token")[:20]}...' if session.get('tidal_token') else 'No token!')
    
    return redirect('http://localhost:3000')

# Check auth status
@app.route('/auth/status')
def auth_status():
    return jsonify({
        'spotify': 'spotify_token' in session,
        'tidal': 'tidal_token' in session
    })

# Get Spotify playlists
@app.route('/playlists')
def get_playlists():
    token = session.get('spotify_token')
    if not token:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401
    
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(
        'https://api.spotify.com/v1/me/playlists',
        headers=headers
    )
    
    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch playlists'}), 400
    
    data = response.json()
    playlists = [
        {
            'id': p['id'],
            'name': p['name'],
            'tracks': p['tracks']['total']
        }
        for p in data.get('items', [])
    ]
    
    return jsonify({'playlists': playlists})

# Transfer playlist
@app.route('/transfer', methods=['POST'])
def transfer_playlist():
    spotify_token = session.get('spotify_token')
    tidal_token = session.get('tidal_token')
    tidal_user_id = session.get('tidal_user_id')
    
    if not spotify_token or not tidal_token:
        return jsonify({'error': 'Not authenticated'}), 401
    
    playlist_id = request.json.get('playlist_id')
    
    # Get Spotify playlist details
    headers = {'Authorization': f'Bearer {spotify_token}'}
    playlist_response = requests.get(
        f'https://api.spotify.com/v1/playlists/{playlist_id}',
        headers=headers
    )
    
    if playlist_response.status_code != 200:
        return jsonify({'error': 'Failed to fetch playlist'}), 400
    
    playlist_data = playlist_response.json()
    playlist_name = playlist_data['name']
    
    # Get all tracks
    tracks_response = requests.get(
        f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
        headers=headers
    )
    
    if tracks_response.status_code != 200:
        return jsonify({'error': 'Failed to fetch tracks'}), 400
    
    tracks_data = tracks_response.json()
    
    # Create Tidal playlist
    tidal_headers = {
        'Authorization': f'Bearer {tidal_token}',
        'Content-Type': 'application/json'
    }
    
    create_playlist_response = requests.post(
        f'https://api.tidal.com/v1/users/{tidal_user_id}/playlists',
        headers=tidal_headers,
        json={'title': playlist_name, 'description': 'Transferred from Spotify'}
    )
    
    if create_playlist_response.status_code not in [200, 201]:
        return jsonify({'error': 'Failed to create Tidal playlist'}), 400
    
    tidal_playlist = create_playlist_response.json()
    tidal_playlist_id = tidal_playlist.get('uuid')
    
    # Search and add tracks to Tidal
    added_count = 0
    for item in tracks_data.get('items', []):
        track = item.get('track')
        if not track:
            continue
        
        track_name = track['name']
        artist_name = track['artists'][0]['name'] if track['artists'] else ''
        
        # Search on Tidal
        search_response = requests.get(
            f'https://api.tidal.com/v1/search/tracks',
            headers=tidal_headers,
            params={'query': f'{track_name} {artist_name}', 'limit': 1}
        )
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            if search_data.get('items'):
                tidal_track_id = search_data['items'][0]['id']
                
                # Add track to playlist
                add_response = requests.post(
                    f'https://api.tidal.com/v1/playlists/{tidal_playlist_id}/items',
                    headers=tidal_headers,
                    json={'trackIds': [tidal_track_id]}
                )
                
                if add_response.status_code in [200, 201]:
                    added_count += 1
    
    return jsonify({
        'success': True,
        'playlist_name': playlist_name,
        'tracks_added': added_count
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)