#!/bin/bash
set -e

cd /opt/ai-devsecops

echo "=== AI DevSecOps Deploy ==="
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short HEAD)"
echo ""

# Pull latest code
echo "[1/4] Pulling latest code..."
git pull origin main

# Build and start services (use prod-only compose file)
echo "[2/4] Building and starting containers..."
docker compose -f docker-compose.prod.yml up -d --build

# Prune old images
echo "[3/4] Pruning old images..."
docker image prune -f

# Status check
echo "[4/4] Container status:"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== Deploy complete ==="
echo "App: https://app.iqbalhidayatrasyad.blog"
