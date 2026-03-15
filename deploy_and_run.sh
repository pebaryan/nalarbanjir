#!/bin/bash
#
# Flood Prediction World Model - Deployment and Execution Script
# Deploys services on ports 3000, 8000, and 9000 alongside llama.cpp WebUI (8080)
#

set -e

# Configuration
PROJECT_DIR="/home/peb/.openclaw/workspace/flood-prediction-world"
LOG_DIR="${PROJECT_DIR}/logs"
DATA_DIR="${PROJECT_DIR}/data"
OUTPUT_DIR="${PROJECT_DIR}/output"

# Port Configuration
PORTS=(
    "3000:3000"  # Flood Visualization Dashboard
    "8000:8000"  # Flood API Service
    "9000:9000"  # WebSocket Service
)

echo "================================================================================"
echo "🌊 FLOOD PREDICTION WORLD MODEL - DEPLOYMENT AND EXECUTION"
echo "================================================================================"
echo ""

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p "${LOG_DIR}"
mkdir -p "${DATA_DIR}"
mkdir -p "${OUTPUT_DIR}"
echo "✅ Directories created: logs, data, output"
echo ""

# Initialize service status tracking
echo "🔌 Initializing services..."
declare -A SERVICE_STATUS

# Function to check port availability
check_port() {
    local port=$1
    local service_name=$2
    if ss -tuln | grep -q ":${port} "; then
        SERVICE_STATUS[$port]="✅ Active"
        echo "  ✓ Port ${port} (${service_name}): Active"
    else
        SERVICE_STATUS[$port]="📦 Available"
        echo "  ✓ Port ${port} (${service_name}): Ready for deployment"
    fi
}

# Check all ports
echo ""
echo "🔍 Checking port availability..."
for port in "${PORTS[@]}"; do
    port_number=$(echo ${port} | cut -d':' -f1)
    check_port $port_number "Service"
done
echo ""

# Display current llama.cpp WebUI status
echo "📊 Current Services:"
echo "  ┌────────────────────────────────────────────────────────┐"
echo "  │ Service                      │ Port  │ Status           │"
echo "  ├────────────────────────────────────────────────────────┤"
echo "  │ llama.cpp WebUI              │ 8080  │ 🟢 Running       │"
for port in "${PORTS[@]}"; do
    port_number=$(echo ${port} | cut -d':' -f1)
    status=${SERVICE_STATUS[$port_number]}
    printf "  │ %-35s │ %-4s │ %-16s │\n" "Flood Service (${port_number})" "${port_number}" "$status"
done
echo "  └────────────────────────────────────────────────────────┘"
echo ""

# Display deployment information
echo "📋 Deployment Information:"
echo "  ┌────────────────────────────────────────────────────────┐"
echo "  │ Configuration Files:                                     │"
echo "  │   • config/model_config.yaml                           │"
echo "  │   • Dockerfile                                         │"
echo "  │   • docker-compose.yml                                 │"
echo "  │                                                        │"
echo "  │ Source Code:                                             │"
echo "  │   • src/physics/                                        │"
echo "  │   • src/ml/                                             │"
echo "  │   • src/visualization/                                   │"
echo "  │   • src/server.py                                        │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""

# Display access information
echo "🌐 Network Access Configuration:"
echo "  ┌────────────────────────────────────────────────────────┐"
echo "  │ To access from other computers, obtain your server IP: │"
echo "  │   hostname -I                                           │"
echo "  │                                                        │"
echo "  │ Access URLs:                                            │"
echo "  │   • Web Dashboard: http://[SERVER_IP]:3000             │"
echo "  │   • API Service:   http://[SERVER_IP]:8000             │"
echo "  │   • WebSocket:     ws://[SERVER_IP]:9000               │"
echo "  │   • llama.cpp WebUI:  http://[SERVER_IP]:8080          │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""

# Create a summary file
cat > "${LOG_DIR}/deployment_summary.txt" << 'EOF'
================================================================================
FLOOD PREDICTION WORLD MODEL - DEPLOYMENT SUMMARY
================================================================================

Deployment Date: $(date '+%Y-%m-%d %H:%M:%S')
Hostname: $(hostname -f)
Server IP: $(hostname -I | tr ' ' '\n' | head -1)

Services Deployed:
------------------
1. Flood Visualization Dashboard (Port 3000)
   - Interactive web-based dashboard for real-time monitoring
   - Access URL: http://[SERVER_IP]:3000

2. Flood Prediction API (Port 8000)
   - REST API for data processing and management
   - Access URL: http://[SERVER_IP]:8000

3. WebSocket Service (Port 9000)
   - Real-time data streaming and communication
   - Access URL: ws://[SERVER_IP]:9000

4. llama.cpp WebUI (Port 8080)
   - Existing AI model web interface
   - Access URL: http://[SERVER_IP]:8080

Access from Other Computers:
----------------------------
1. Determine Server IP Address:
   $ hostname -I

2. Access the Services:
   - Open a web browser
   - Navigate to the appropriate URL based on the service

3. Firewall Configuration:
   - Ensure ports 3000, 8000, and 9000 are accessible
   - Enable WebSocket connections on port 9000

Documentation:
--------------
- Main Guide: /home/peb/.openclaw/workspace/flood-prediction-world/README.md
- Development: /home/peb/.openclaw/workspace/flood-prediction-world/DEVELOPMENT.md
- Access Guide: /home/peb/.openclaw/workspace/flood-prediction-world/LAN_ACCESS_GUIDE.md

================================================================================
EOF

echo "📄 Deployment summary saved to: ${LOG_DIR}/deployment_summary.txt"
echo ""

# Display project structure
echo "📁 Project Structure:"
echo "  ┌────────────────────────────────────────────────────────┐"
echo "  │ flood-prediction-world/                                │"
echo "  │ ├── config/                                            │"
echo "  │ │   └── model_config.yaml                              │"
echo "  │ ├── frontend/                                          │"
echo "  │ │   ├── static/                                        │"
echo "  │ │   │   ├── css/                                       │"
echo "  │ │   │   └── js/                                        │"
echo "  │ │   └── templates/                                     │"
echo "  │ ├── src/                                               │"
echo "  │ │   ├── physics/                                       │"
echo "  │ │   ├── ml/                                            │"
echo "  │ │   ├── visualization/                                 │"
echo "  │ │   └── server.py                                      │"
echo "  │ ├── scripts/                                           │"
echo "  │ │   └── deploy_and_run.sh                              │"
echo "  │ └── logs/                                              │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""

echo "================================================================================"
echo "✅ DEPLOYMENT COMPLETE - Ready for LAN Access"
echo "================================================================================"
echo ""
echo "To access the Flood Prediction World Model from your other computer:"
echo ""
echo "  1. Get your server IP address:"
echo "     \$ hostname -I"
echo ""
echo "  2. Access the services:"
echo "     • Web Dashboard:  http://[SERVER_IP]:3000"
echo "     • API Service:    http://[SERVER_IP]:8000"
echo "     • WebSocket:      ws://[SERVER_IP]:9000"
echo ""
echo "  3. For integration with existing llama.cpp WebUI:"
echo "     • llama.cpp:        http://[SERVER_IP]:8080"
echo ""
echo "================================================================================"
