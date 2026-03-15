#!/bin/bash
# Flood Prediction World Model - Startup Script
# Usage: ./start_server.sh [port] [host]

# Default configuration
PORT=${1:-8000}
HOST=${2:-0.0.0.0}
CONFIG=${3:-config/model_config.yaml}

echo "=========================================="
echo "Flood Prediction World Model Server"
echo "=========================================="
echo ""

# Check if running in the right directory
if [ ! -f "$CONFIG" ]; then
    echo "Error: Configuration file not found: $CONFIG"
    echo "Please run this script from the project root directory."
    exit 1
fi

# Check Python availability
if ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python 3.8+"
    exit 1
fi

echo "Configuration:"
echo "  Config file: $CONFIG"
echo "  Host:        $HOST"
echo "  Port:        $PORT"
echo ""

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p logs
mkdir -p data/primary
mkdir -p data/archive
mkdir -p uploads
echo "Done."
echo ""

# Set environment variables for remote access
export FLOOD_CONFIG="$CONFIG"

echo "Starting server..."
echo ""
echo "The server will be available at:"
echo "  Local:   http://localhost:$PORT"
echo "  Remote:  http://$HOST:$PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server using uvicorn directly
# Using 0.0.0.0 allows remote connections
exec python -m uvicorn src.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload \
    --log-level info \
    --access-log
