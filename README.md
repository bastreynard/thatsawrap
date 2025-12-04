# Spotify to Tidal Playlist Transfer - Docker Deployment

A Flask application with React frontend that transfers playlists from Spotify to Tidal, fully containerized with Docker for easy deployment.

## Features

- 🎵 Transfer playlists from Spotify to Tidal
- 💚 Support for Liked Songs
- 🔐 Secure OAuth authentication for both services
- ⚛️ React frontend with responsive design
- 🐳 Fully containerized with Docker (backend + frontend)
- 🚀 Production-ready with Gunicorn and Nginx

## Project Structure

```
.
├── backend.py                 # Flask backend
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Production backend Dockerfile
├── Dockerfile.dev             # Development backend Dockerfile
├── docker-compose.yml         # Production orchestration
├── docker-compose.dev.yml     # Development orchestration
├── nginx.conf                 # Nginx configuration for frontend
├── .env.example              # Environment variables template
└── thatsawrap-react/         # React frontend (git submodule)
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
cd thatsawrap

# If you already cloned without --recurse-submodules:
git submodule init
git submodule update
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your API credentials:

```env
# Spotify API Configuration see https://developer.spotify.com/
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost/api/callback/spotify

# Tidal API Configuration see https://developer.tidal.com/
TIDAL_CLIENT_ID=your_tidal_client_id
TIDAL_CLIENT_SECRET=your_tidal_client_secret
TIDAL_REDIRECT_URI=http://localhost/api/callback/tidal

# Application Configuration
FRONTEND_URL=http://127.0.0.1:8080
SECRET_KEY=your_secret_key_here

# Generate a secure SECRET_KEY with:
# openssl rand -hex 32
```

### 3. Build and Run with Docker Compose

**Production Mode:**
```bash
# Build and start both backend and frontend
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the containers
docker-compose down
```

**Development Mode (with hot-reload):**
```bash
# Start in development mode with hot-reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or use the Makefile
make dev
```

The application will be available at:
- **Frontend:** http://localhost (port 80)
- **Backend API:** http://localhost/api (proxied through Nginx)

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

### Running Locally Without Docker

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python backend.py
```

### Building for Production

The Docker image uses Gunicorn as the production WSGI server with:
- 2 worker processes
- 4 threads per worker
- 60-second timeout
- Health checks enabled

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SPOTIFY_CLIENT_ID` | Spotify API client ID | Required |
| `SPOTIFY_CLIENT_SECRET` | Spotify API client secret | Required |
| `SPOTIFY_REDIRECT_URI` | Spotify OAuth callback URL | `http://127.0.0.1:5000/callback/spotify` |
| `TIDAL_CLIENT_ID` | Tidal API client ID | Required |
| `TIDAL_CLIENT_SECRET` | Tidal API client secret | Required |
| `TIDAL_REDIRECT_URI` | Tidal OAuth callback URL | `http://127.0.0.1:5000/callback/tidal` |
| `FRONTEND_URL` | Frontend application URL | `http://127.0.0.1:8080` |
| `SECRET_KEY` | Flask session secret key | Required |

## Obtaining API Credentials

### Spotify
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add `http://127.0.0.1:5000/callback/spotify` to Redirect URIs
4. Copy Client ID and Client Secret

### Tidal
1. Go to [Tidal Developer Portal](https://developer.tidal.com/)
2. Create a new application
3. Add `http://127.0.0.1:5000/callback/tidal` to Redirect URIs
4. Copy Client ID and Client Secret

## Security Notes

- Always use HTTPS in production
- Generate a strong `SECRET_KEY` using `openssl rand -hex 32`
- Never commit `.env` file to version control
- The container runs as a non-root user for security
- Update `SESSION_COOKIE_SECURE` to `True` when using HTTPS

## Deployment to Production

### Deploy to Cloud (General Steps)

1. **Set up your server** (AWS EC2, DigitalOcean, etc.)
2. **Install Docker and Docker Compose**
3. **Update environment variables**:
   - Use your production domain in redirect URIs
   - Set `SESSION_COOKIE_SECURE=True`
   - Use HTTPS
4. **Update CORS origins** in `backend.py` to match your frontend
5. **Run the container**:
   ```bash
   docker-compose up -d
   ```

### Using a Reverse Proxy (Nginx)

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs

# Verify environment variables
docker-compose config
```

### Authentication issues
- Verify redirect URIs match in your .env and developer portals
- Check that credentials are correct
- Ensure frontend URL is accessible

### Port already in use
```bash
# Change port in docker-compose.yml
ports:
  - "5001:5000"  # Use 5001 instead of 5000
```

## Health Check

The container includes a health check that runs every 30 seconds:

```bash
# Check container health
docker ps

# Manual health check
curl http://localhost:5000/auth/status
```

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
