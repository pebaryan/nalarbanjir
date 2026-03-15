#!/bin/bash
#
# Local Deployment Script for Flood Prediction World Model
# Runs the application locally without Docker
#

set -e

PROJECT_DIR="/home/peb/.openclaw/workspace/flood-prediction-world"
LOG_DIR="${PROJECT_DIR}/logs"
PID_FILE="${LOG_DIR}/server.pid"

echo "================================================================================"
echo "🌊 FLOOD PREDICTION WORLD MODEL - LOCAL DEPLOYMENT"
echo "================================================================================"
echo ""

# Create log directory
mkdir -p "${LOG_DIR}"

# Check if server is already running
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    if ps -p "${OLD_PID}" > /dev/null 2>&1; then
        echo "⚠️  Server is already running (PID: ${OLD_PID})"
        echo "   Stopping existing server..."
        kill "${OLD_PID}" 2>/dev/null || true
        sleep 2
    fi
    rm -f "${PID_FILE}"
fi

# Check Python and dependencies
echo "🔍 Checking Python environment..."
cd "${PROJECT_DIR}"

# Check if required packages are installed
python3 -c "import fastapi, uvicorn, numpy, torch" 2>/dev/null || {
    echo "❌ Required packages not installed. Installing..."
    pip install -r requirements.txt --quiet
}

echo "✅ Environment check passed"
echo ""

# Start the server
echo "🚀 Starting Flood Prediction World Model server..."
echo "   API will be available at: http://localhost:8000"
echo "   WebSocket will be available at: ws://localhost:8000/ws"
echo ""

# Start server in background
python3 -m uvicorn src.server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info \
    > "${LOG_DIR}/server.log" 2>&1 &

SERVER_PID=$!
echo "${SERVER_PID}" > "${PID_FILE}"

echo "✅ Server started with PID: ${SERVER_PID}"
echo ""

# Wait for server to be ready
echo "⏳ Waiting for server to be ready..."
sleep 3

# Check if server is running
if ps -p "${SERVER_PID}" > /dev/null 2>&1; then
    echo "✅ Server is running!"
    echo ""
    echo "================================================================================"
    echo "📋 ACCESS INFORMATION"
    echo "================================================================================"
    echo ""
    echo "Local Access:"
    echo "  • API:       http://localhost:8000"
    echo "  • Health:    http://localhost:8000/health"
    echo "  • Docs:      http://localhost:8000/docs"
    echo "  • WebSocket: ws://localhost:8000/ws"
    echo ""
    echo "Network Access (from other computers on LAN):"
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo "  • API:       http://${SERVER_IP}:8000"
    echo "  • Health:    http://${SERVER_IP}:8000/health"
    echo "  • Docs:      http://${SERVER_IP}:8000/docs"
    echo ""
    echo "Logs: ${LOG_DIR}/server.log"
    echo ""
    echo "To stop the server:"
    echo "  kill $(cat ${PID_FILE})"
    echo ""
    echo "================================================================================"
else
    echo "❌ Failed to start server"
    echo "Check logs: ${LOG_DIR}/server.log"
    exit 1
fi