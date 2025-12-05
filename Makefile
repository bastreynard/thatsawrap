.PHONY: help build up down restart logs shell clean push

# Get version info from git
VERSION_TAG := $(shell git describe --tags --abbrev=0 2>/dev/null || echo "dev")
GIT_COMMIT_HASH := $(shell git rev-parse HEAD 2>/dev/null || echo "unknown")

# Export for docker-compose
export VERSION_TAG
export GIT_COMMIT_HASH

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker image
	@echo "Building with VERSION_TAG=$(VERSION_TAG) and GIT_COMMIT_HASH=$(GIT_COMMIT_HASH)"
	@sed -i '/^VERSION_TAG=/d' .env 2>/dev/null || true
	@sed -i '/^GIT_COMMIT_HASH=/d' .env 2>/dev/null || true
	@echo "VERSION_TAG=$(VERSION_TAG)" >> .env
	@echo "GIT_COMMIT_HASH=$(GIT_COMMIT_HASH)" >> .env
	docker-compose build

up: ## Start the container in detached mode
	docker-compose up -d

down: ## Stop and remove the container
	docker-compose down

restart: down up ## Restart the container

logs: ## Follow container logs
	docker-compose logs -f

shell: ## Open a shell in the running container
	docker-compose exec app /bin/bash

clean: ## Remove container, image, and volumes
	docker-compose down -v
	docker rmi thatsawrap-app 2>/dev/null || true

status: ## Show container status
	docker-compose ps

health: ## Check application health
	curl -s http://localhost:5000/auth/status | python -m json.tool

env-check: ## Verify environment variables are set
	@echo "Checking environment variables..."
	@test -f .env || (echo "❌ .env file not found! Copy .env.example to .env" && exit 1)
	@grep -q "SPOTIFY_CLIENT_ID=" .env && echo "✓ SPOTIFY_CLIENT_ID set" || echo "❌ SPOTIFY_CLIENT_ID missing"
	@grep -q "SPOTIFY_CLIENT_SECRET=" .env && echo "✓ SPOTIFY_CLIENT_SECRET set" || echo "❌ SPOTIFY_CLIENT_SECRET missing"
	@grep -q "TIDAL_CLIENT_ID=" .env && echo "✓ TIDAL_CLIENT_ID set" || echo "❌ TIDAL_CLIENT_ID missing"
	@grep -q "TIDAL_CLIENT_SECRET=" .env && echo "✓ TIDAL_CLIENT_SECRET set" || echo "❌ TIDAL_CLIENT_SECRET missing"
	@grep -q "SECRET_KEY=" .env && echo "✓ SECRET_KEY set" || echo "❌ SECRET_KEY missing"

dev: ## Run in development mode (with auto-reload)
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

push: build
	docker tag thatsawrap-app vulpiculus/thatsawrap-app:latest
	docker push vulpiculus/thatsawrap-app:latest