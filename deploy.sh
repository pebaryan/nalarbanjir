#!/bin/bash
# Run this script from the nalarbanjir repo directory on the server.

set -e

echo "==> Pulling latest changes..."
git pull

echo "==> Stopping containers..."
docker compose down

echo "==> Building and starting containers..."
docker compose up -d --build

echo "==> Done. Running containers:"
docker compose ps
