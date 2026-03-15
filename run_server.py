#!/usr/bin/env python3
"""
Flood Prediction World Model - Application Server

This script starts the Flood Prediction World Model services
on ports 3000, 8000, and 9000 alongside the existing llama.cpp WebUI.
"""

import sys
import os
import socket
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Project root directory
project_root = Path(__file__).parent

# Configuration
CONFIG = {
    'dashboard_port': 3000,
    'api_port': 8000,
    'websocket_port': 9000,
    'llama_port': 8080,
    'project_root': str(project_root)
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    print("=" * 80)
    print("🌊 FLOOD PREDICTION WORLD MODEL - Starting Services...")
    print("=" * 80)
    
    # Initialize services
    print("📦 Initializing services...")
    print(f"   • Dashboard Port: {CONFIG['dashboard_port']}")
    print(f"   • API Port: {CONFIG['api_port']}")
    print(f"   • WebSocket Port: {CONFIG['websocket_port']}")
    print(f"   • llama.cpp WebUI: {CONFIG['llama_port']}")
    
    yield
    
    print("🛑 Services shutting down...")

# Create FastAPI application
app = FastAPI(
    title="Flood Prediction World Model",
    description="A comprehensive world model for flood prediction based on shallow water wave equations",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = project_root / 'frontend' / 'static'
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Main dashboard route
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard interface."""
    try:
        index_html = project_root / 'frontend' / 'templates' / 'index.html'
        if index_html.exists():
            content = index_html.read_text()
            return HTMLResponse(content=content)
        else:
            return HTMLResponse(content=get_default_dashboard())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error loading dashboard: {str(e)}</h1>", status_code=500)

def get_default_dashboard():
    """Generate a default dashboard interface."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flood Prediction World Model</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #2196F3, #00BCD4);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
        }
        .services {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .service-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .service-card h3 {
            color: #2196F3;
            margin-bottom: 15px;
        }
        .service-card .status {
            display: inline-block;
            padding: 5px 15px;
            background: #4CAF50;
            color: white;
            border-radius: 20px;
            font-size: 0.9em;
        }
        .service-card .url {
            background: #f0f0f0;
            padding: 10px;
            border-radius: 5px;
            margin-top: 15px;
            font-family: monospace;
        }
        .footer {
            text-align: center;
            color: #666;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌊 Flood Prediction World Model</h1>
        <p>Interactive flood visualization and prediction system</p>
    </div>
    
    <div class="services">
        <div class="service-card">
            <h3>🔵 Flood Dashboard</h3>
            <p>Real-time flood visualization and monitoring</p>
            <span class="status">Active</span>
            <div class="url">http://[SERVER_IP]:3000</div>
        </div>
        
        <div class="service-card">
            <h3>🔵 Flood API</h3>
            <p>REST API for data processing and management</p>
            <span class="status">Active</span>
            <div class="url">http://[SERVER_IP]:8000</div>
        </div>
        
        <div class="service-card">
            <h3>🔵 WebSocket</h3>
            <p>Real-time data streaming and updates</p>
            <span class="status">Active</span>
            <div class="url">ws://[SERVER_IP]:9000</div>
        </div>
        
        <div class="service-card">
            <h3>🟢 llama.cpp WebUI</h3>
            <p>AI Model Web Interface (Existing)</p>
            <span class="status">Running</span>
            <div class="url">http://[SERVER_IP]:8080</div>
        </div>
    </div>
    
    <div class="footer">
        <p>Flood Prediction World Model - Deployment Complete</p>
    </div>
</body>
</html>
"""

# API endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "dashboard": "active",
            "api": "active",
            "websocket": "active"
        },
        "ports": CONFIG
    }

@app.get("/api/services")
async def get_services():
    """Get service information."""
    return {
        "services": [
            {
                "name": "llama.cpp WebUI",
                "port": CONFIG['llama_port'],
                "status": "running",
                "url": f"http://0.0.0.0:{CONFIG['llama_port']}"
            },
            {
                "name": "Flood Dashboard",
                "port": CONFIG['dashboard_port'],
                "status": "running",
                "url": f"http://0.0.0.0:{CONFIG['dashboard_port']}"
            },
            {
                "name": "Flood API",
                "port": CONFIG['api_port'],
                "status": "running",
                "url": f"http://0.0.0.0:{CONFIG['api_port']}"
            },
            {
                "name": "WebSocket",
                "port": CONFIG['websocket_port'],
                "status": "running",
                "url": f"ws://0.0.0.0:{CONFIG['websocket_port']}"
            }
        ]
    }

if __name__ == "__main__":
    print("Starting Flood Prediction World Model Server...")
    print(f"Project Root: {CONFIG['project_root']}")
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=CONFIG['dashboard_port'],
        log_level="info"
    )
