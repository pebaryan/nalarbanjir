#!/bin/bash
#
# Flood Prediction World Model - Deployment Script
#
# This script provides comprehensive deployment capabilities for the
# flood prediction world model, including building Docker images,
# managing containers, and monitoring the application.
#

set -e  # Exit on error

# Configuration
PROJECT_NAME="flood-prediction-world"
DOCKER_IMAGE="${PROJECT_NAME}:latest"
DOCKER_CONTAINER="${PROJECT_NAME}-app"
COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;32m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
print_banner() {
    echo -e "${GREEN}========================================"
    echo -e "  ${PROJECT_NAME}"
    echo -e "  Flood Prediction World Model"
    echo -e "========================================"
    echo
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    log_success "Docker is installed"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    log_success "Docker Compose is installed"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_success "Python 3 is installed"
}

# Build Docker image
build_image() {
    log_info "Building Docker image: ${DOCKER_IMAGE}"
    
    docker build \
        -t ${DOCKER_IMAGE} \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%d_%H:%M:%S') \
        --build-arg VERSION=1.0.0 \
        .
    
    log_success "Docker image built successfully"
}

# Start Docker containers
start_containers() {
    log_info "Starting Docker containers..."
    
    docker-compose -f ${COMPOSE_FILE} up -d
    
    log_success "Containers started successfully"
    
    # Wait for containers to be ready
    log_info "Waiting for containers to be ready..."
    sleep 10
    
    # Check container status
    docker-compose -f ${COMPOSE_FILE} ps
}

# Stop Docker containers
stop_containers() {
    log_info "Stopping Docker containers..."
    
    docker-compose -f ${COMPOSE_FILE} down
    
    log_success "Containers stopped successfully"
}

# Restart Docker containers
restart_containers() {
    log_info "Restarting Docker containers..."
    
    docker-compose -f ${COMPOSE_FILE} restart
    
    log_success "Containers restarted successfully"
}

# Monitor container logs
monitor_logs() {
    log_info "Monitoring container logs (Ctrl+C to exit)..."
    
    docker-compose -f ${COMPOSE_FILE} logs -f
}

# Execute commands in running containers
exec_in_container() {
    local service=$1
    local command=$2
    
    log_info "Executing command in ${service}: ${command}"
    
    docker exec -it ${DOCKER_CONTAINER}-${service} bash -c "${command}"
}

# Run simulation
run_simulation() {
    log_info "Running flood prediction simulation..."
    
    docker exec -it ${DOCKER_CONTAINER}-flood-world \
        python /app/scripts/run_simulation.py \
        --config /app/config/model_config.yaml \
        --duration 1000 \
        --output /app/output \
        --log-level INFO
}

# Generate deployment report
generate_report() {
    log_info "Generating deployment report..."
    
    REPORT_FILE="deployment_report.md"
    
    cat > ${REPORT_FILE} << EOF
# ${PROJECT_NAME} Deployment Report

## Deployment Information

- **Deployment Date**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
- **Version**: 1.0.0
- **Image**: ${DOCKER_IMAGE}

## Container Status

\`\`\`
\$(docker-compose -f ${COMPOSE_FILE} ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}")
\`\`\`

## Resource Usage

\`\`\`
\$(docker stats --no-stream --format "table {{.ContainerName}}\t{{.CPUPerc}}\t{{.MemUsage}}")
\`\`\`

## Configuration

- **Configuration File**: ${COMPOSE_FILE}
- **Environment**: Production
- **Services**:
  - flood-world: Main application service
  - frontend: Web interface service
  - ml-training: ML training service

## Next Steps

1. Monitor container health regularly
2. Review logs for any warnings or errors
3. Schedule periodic updates and maintenance

EOF

    log_success "Deployment report generated: ${REPORT_FILE}"
}

# Clean up resources
cleanup() {
    log_info "Cleaning up resources..."
    
    # Remove old images
    docker image prune -f --filter "until=24h"
    
    # Remove unused volumes
    docker volume prune -f
    
    log_success "Cleanup completed"
}

# Show help information
show_help() {
    cat << EOF
${PROJECT_NAME} - Deployment Script

Usage: $(basename $0) [command] [options]

Commands:
    start           Start all containers
    stop            Stop all containers
    restart         Restart all containers
    build           Build Docker images
    logs            Monitor container logs
    run             Run simulation
    report          Generate deployment report
    cleanup         Clean up resources
    help            Show this help message

Options:
    --all           Perform all operations
    --verbose       Enable verbose output
    --interactive   Run in interactive mode

Examples:
    $(basename $0) start
    $(basename $0) build --all
    $(basename $0) logs --verbose

For more information, visit the project documentation.
EOF
}

# Main execution
main() {
    print_banner
    
    # Parse command line arguments
    local command=${1:-start}
    shift || true
    
    case $command in
        start)
            check_prerequisites
            build_image
            start_containers
            generate_report
            ;;
        stop)
            stop_containers
            generate_report
            ;;
        restart)
            check_prerequisites
            restart_containers
            generate_report
            ;;
        build)
            check_prerequisites
            build_image
            cleanup
            ;;
        logs)
            check_prerequisites
            monitor_logs
            ;;
        run)
            check_prerequisites
            run_simulation
            ;;
        report)
            generate_report
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
    
    echo
    log_success "Deployment completed successfully!"
}

# Run main function
main "$@"
