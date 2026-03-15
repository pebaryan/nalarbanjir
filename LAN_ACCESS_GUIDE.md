# 🌐 Flood Prediction World Model - LAN Access Guide

## Overview

This guide provides comprehensive instructions for accessing the Flood Prediction World Model from other computers on your local network (LAN).

## Quick Access

### Primary Access URL

```
http://[SERVER_IP]:8080
```

Replace `[SERVER_IP]` with the actual server IP address to access the web interface from any device on your LAN.

## Server Configuration

### Server Details

- **Hostname**: mi25
- **Primary Port**: 8080 (Web Interface)
- **API Port**: 8000 (REST API & WebSocket)
- **Environment**: Production
- **Configuration**: model_config.yaml

### Network Ports

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Web Interface | 8080 | HTTP | User-facing dashboard |
| API Service | 8000 | HTTP | REST API endpoints |
| WebSocket | 8000 | WebSocket | Real-time data streaming |

## Access Methods

### Method 1: Direct Browser Access

1. **From Same Network**:
   ```
   Open browser and navigate to:
   http://[SERVER_IP]:8080
   ```

2. **From External Network**:
   ```
   Ensure port forwarding is configured:
   - Port 8080 (Web Interface)
   - Port 8000 (API & WebSocket)
   ```

### Method 2: Mobile Device Access

For accessing the dashboard from tablets or smartphones:

1. Ensure mobile device is connected to the same WiFi network
2. Open browser and enter the server's IP address with port 8080
3. The responsive design automatically adapts the interface for mobile viewing

### Method 3: API Integration

For developers integrating with the system:

```bash
# Get system state
curl http://[SERVER_IP]:8000/api/state

# Run simulation
curl -X POST http://[SERVER_IP]:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"steps": 100, "output_format": "full"}'

# Get predictions
curl -X POST http://[SERVER_IP]:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"prediction_type": "flood_risk", "forecast_horizon": 24}'
```

## Firewall Configuration

### Required Firewall Rules

To enable LAN access, configure the following firewall rules:

```bash
# Open web interface port
sudo ufw allow 8080/tcp

# Open API service port
sudo ufw allow 8000/tcp

# Enable WebSocket connections
sudo ufw allow 8000/tcp

# Verify firewall status
sudo ufw status verbose
```

### Firewall Rules Summary

| Port | Protocol | Service | Status |
|------|----------|---------|--------|
| 8080 | TCP | Web Interface | Required |
| 8000 | TCP | API Service | Required |
| 8000 | TCP | WebSocket | Required |

## Deployment Information

### Application Structure

```
Flood Prediction World Model
├── Web Interface (Port 8080)
│   ├── HTML/CSS/JavaScript Dashboard
│   ├── Real-time Visualization
│   └── Interactive Controls
├── API Service (Port 8000)
│   ├── REST API Endpoints
│   ├── WebSocket Communication
│   └── Data Management
└── Data Layer
    ├── Physics Engine
    ├── Machine Learning Models
    └── Static Assets
```

### Containerized Deployment

The application is deployed using containerization principles:

- **Container**: Flood Prediction World Application
- **Image**: Python-based web application
- **Orchestration**: Service-based architecture
- **Persistence**: Configured data volumes

## Usage Instructions

### For End Users

1. **Access the Web Interface**:
   - Open a web browser on any device
   - Navigate to the server's IP address with port 8080
   - Example: `http://192.168.1.100:8080`

2. **Explore Features**:
   - View real-time flood predictions
   - Monitor water surface dynamics
   - Analyze flow patterns and risk zones

3. **Interact with Data**:
   - Use interactive dashboards
   - Configure simulation parameters
   - Export reports and visualizations

### For Developers

1. **API Integration**:
   - Refer to API documentation for endpoint details
   - Use REST API for data retrieval and updates
   - Implement WebSocket for real-time updates

2. **Extension Points**:
   - Customize visualization components
   - Extend ML prediction models
   - Integrate with external data sources

## Troubleshooting

### Common Issues and Solutions

#### 1. Connection Issues

**Symptom**: Unable to connect to the web interface

**Solution**:
- Verify server IP address is accessible
- Check firewall rules allow required ports
- Ensure network connectivity between devices

```bash
# Test connectivity
ping [SERVER_IP]
curl http://[SERVER_IP]:8080/health
```

#### 2. Port Accessibility

**Symptom**: Services not responding

**Solution**:
- Verify ports are open and listening
- Check service status and logs
- Ensure network routing is configured correctly

```bash
# Check listening ports
sudo netstat -tuln | grep -E '8080|8000'

# View service logs
journalctl -u flood-prediction-world -f
```

#### 3. Performance Optimization

**Symptom**: Slow response times

**Solution**:
- Monitor resource utilization
- Optimize data processing pipelines
- Configure caching mechanisms

```bash
# Monitor resource usage
top -p $(pgrep -f flood-prediction)
```

## Advanced Configuration

### Custom Domain Access

For organizations wanting to use a custom domain:

1. Configure DNS to point to the server IP
2. Set up SSL certificates for secure connections
3. Update application configuration to use HTTPS

### Load Balancing

For high-traffic environments:

1. Deploy multiple instances behind a load balancer
2. Configure session persistence for WebSocket connections
3. Implement health checks for service availability

## Contact and Support

For assistance with the Flood Prediction World Model:

- **Documentation**: Refer to this guide and the main documentation
- **Technical Support**: Contact the development team
- **Community**: Join the user community for insights and best practices

---

**Last Updated**: 2024  
**Version**: 1.0.0
