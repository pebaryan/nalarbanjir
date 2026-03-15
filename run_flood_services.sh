#!/bin/bash
# Run Flood Prediction World Model Services

echo "================================================================================"
echo "🌊 FLOOD PREDICTION WORLD MODEL - SERVICE LAUNCHER"
echo "================================================================================"
echo ""

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo "📍 Server IP: ${SERVER_IP}"
echo ""

echo "📋 Starting services on ports..."
echo "   • Flood Dashboard: Port 3000"
echo "   • Flood API: Port 8000"
echo "   • WebSocket: Port 9000"
echo "   • llama.cpp WebUI: Port 8080"
echo ""

echo "🚀 Starting Flood Prediction Application..."
echo ""

# Run the main application
cd "$(dirname "$0")"
exec python3 run_server.py
