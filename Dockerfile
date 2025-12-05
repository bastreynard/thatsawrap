# Single-container Dockerfile - Backend + Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy entire frontend directory
COPY thatsawrap-react/ ./

# Install dependencies - will use existing package-lock or create new one
RUN npm install --production

# Build the frontend
RUN npm run build

# Production stage with Python and Nginx
FROM python:3.11-slim

# Version variables
ARG VERSION_TAG=dev
ARG GIT_COMMIT_HASH=unknown
ENV VERSION_TAG=${VERSION_TAG}
ENV GIT_COMMIT_HASH=${GIT_COMMIT_HASH}

WORKDIR /app

# Install nginx and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend.py .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/build /var/www/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/sites-available/default

# Create supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /var/www/html && \
    chown -R appuser:appuser /var/log/nginx && \
    chown -R appuser:appuser /var/lib/nginx && \
    chown -R appuser:appuser /var/log/supervisor && \
    touch /run/nginx.pid && \
    chown appuser:appuser /run/nginx.pid

USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/api/auth/status')"

# Start supervisor (manages both nginx and gunicorn)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]