# Spotify Playlist Transfer

A Flask application with React frontend that transfers playlists from Spotify to Tidal and Qobuz.

## Features

- 🎵 Transfer playlists from Spotify to Tidal and Qobuz
- 💚 Support for Liked Songs
- 🔐 Secure OAuth authentication for Spotify and Tidal
- 🔐 email/password Qobuz authentication
- ⚛️ React frontend with responsive design
- 🐳 Fully containerized with Docker (backend + frontend)
- 🚀 Production-ready with Gunicorn and Nginx

![alt text](image.png)

## Project Structure

```
.
├── backend/                   # Flask backend
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Production backend Dockerfile
├── docker-compose.yml         # Production orchestration
├── nginx.conf                 # Nginx configuration for frontend
├── .env.example               # Environment variables template
└── thatsawrap-react/          # React frontend (git submodule)
```

## Prerequisites

- Docker and Docker Compose installed
- Git (for cloning with submodules)
- Spotify Developer Account with registered app
- Tidal Developer Account with registered app

## Quick Start

### 1. Clone the Repository with Submodules

```bash
git clone --recurse-submodules https://github.com/bastreynard/thatsawrap

# If you already cloned without --recurse-submodules:
git submodule init
git submodule update
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your API credentials

#### Obtaining API Credentials

##### Spotify
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add `http://127.0.0.1:5000/callback/spotify` to Redirect URIs
4. Copy Client ID and Client Secret

##### Tidal
1. Go to [Tidal Developer Portal](https://developer.tidal.com/)
2. Create a new application
3. Add `http://127.0.0.1:5000/callback/tidal` to Redirect URIs
4. Copy Client ID and Client Secret

### 3. Build and Run with Docker Compose

```bash
# Build and start both backend and frontend
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the containers
docker-compose down
```

The application will be available at:
- **Frontend:** http://localhost:8080
- **Backend API:** http://localhost:8080/api (proxied through Nginx)

## Using the Makefile

Convenient commands for common operations:

```bash
make help          # Show all available commands
make build         # Build the Docker images
make up            # Start containers in production mode
make down          # Stop and remove containers
make restart       # Restart containers
make logs          # Follow container logs
make status        # Show container status
make dev           # Run in development mode
make env-check     # Verify environment variables are set
make clean         # Remove containers, images, and volumes
make push          # Push to docker registry
```

## API Endpoints

### Authentication
- `GET /auth/spotify` - Initiate Spotify OAuth
- `GET /auth/tidal` - Initiate Tidal OAuth
- `GET /callback/spotify` - Spotify OAuth callback
- `GET /callback/tidal` - Tidal OAuth callback
- `GET /auth/status` - Check authentication status
- `POST /disconnect/spotify` - Disconnect Spotify
- `POST /disconnect/tidal` - Disconnect Tidal

### Playlist Operations
- `GET /spotify/playlists` - Get Spotify playlists
- `GET /tidal/playlists` - Get Tidal playlists
- `POST /transfer` - Transfer playlist from Spotify to Tidal

## Development

### Running Backend Locally Without Docker

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python backend.py
```
### Running Frontend Locally Without Docker

Requires node.js and npm to be installed

```bash
npm install
npm start
```

## Security Notes

- Always use HTTPS in production
- Generate a strong `SECRET_KEY` using `openssl rand -hex 32`
- Never commit `.env` file to version control
- The container runs as a non-root user for security
- Update `SESSION_COOKIE_SECURE` to `True` when using HTTPS

## License

Copyright 2025

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
