#!/bin/bash

# Start script for Prefect workflow engine infrastructure
# This script starts Prefect server, PostgreSQL, and Redis on the host machine
# Usage: ./start.sh

set -e  # Exit on any error

echo "🚀 Starting Prefect Workflow Engine Infrastructure..."
echo "===================================================="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Docker is installed and running
print_status "Checking Docker availability..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed."
    print_error "Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker is installed but not running."
    print_error "Please start Docker and try again."
    exit 1
fi

print_success "Docker is available and running"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found in $SCRIPT_DIR"
    exit 1
fi

# Check if port 4200 is already in use
print_status "Checking if port 4200 is available..."
if lsof -Pi :4200 -sTCP:LISTEN -t &> /dev/null || nc -z localhost 4200 &> /dev/null; then
    print_warning "Port 4200 is already in use."
    print_status "Checking if it's our Prefect container..."
    if docker ps --filter "name=rpsd-prefect" --filter "status=running" --format "{{.Names}}" | grep -q "rpsd-prefect"; then
        print_success "Prefect is already running!"
        docker ps --filter "name=rpsd-prefect"
        echo
        print_status "Connection information:"
        echo -e "  • ${GREEN}From host machine:${NC}       http://localhost:4200"
        echo -e "  • ${GREEN}From devcontainer:${NC}       http://host.docker.internal:4200"
        echo -e "  • ${GREEN}Prefect UI:${NC}              http://localhost:4200"
        echo
        print_status "Use ./stop.sh to stop Prefect"
        exit 0
    else
        print_error "Port 4200 is in use by another process."
        print_status "Find what's using the port:"
        echo -e "  ${BLUE}lsof -i :4200${NC}  # On macOS/Linux"
        echo -e "  ${BLUE}netstat -ano | findstr :4200${NC}  # On Windows"
        exit 1
    fi
fi

print_success "Port 4200 is available"

# Start services
print_status "Starting Prefect services (postgres, redis, prefect)..."
docker compose up -d

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
echo

MAX_WAIT=60
WAITED=0
INTERVAL=2

while [ $WAITED -lt $MAX_WAIT ]; do
    # Check postgres health
    POSTGRES_HEALTHY=$(docker inspect rpsd-prefect-postgres --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    # Check redis health
    REDIS_HEALTHY=$(docker inspect rpsd-prefect-redis --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    # Check prefect health
    PREFECT_HEALTHY=$(docker inspect rpsd-prefect --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")

    echo -ne "  PostgreSQL: $POSTGRES_HEALTHY | Redis: $REDIS_HEALTHY | Prefect: $PREFECT_HEALTHY\r"

    if [ "$POSTGRES_HEALTHY" = "healthy" ] && [ "$REDIS_HEALTHY" = "healthy" ] && [ "$PREFECT_HEALTHY" = "healthy" ]; then
        echo -ne "\033[2K\r"  # Clear the entire line and return cursor
        print_success "All services are healthy!"
        break
    fi

    if [ $WAITED -ge $MAX_WAIT ]; then
        echo -ne "\033[2K\r"  # Clear the entire line and return cursor
        print_warning "Services are taking longer than expected to start."
        print_status "Current status:"
        echo "  PostgreSQL: $POSTGRES_HEALTHY"
        echo "  Redis: $REDIS_HEALTHY"
        echo "  Prefect: $PREFECT_HEALTHY"
        print_status ""
        print_status "Check logs with:"
        echo -e "  ${BLUE}docker logs rpsd-prefect-postgres${NC}"
        echo -e "  ${BLUE}docker logs rpsd-prefect-redis${NC}"
        echo -e "  ${BLUE}docker logs rpsd-prefect${NC}"
        break
    fi

    sleep $INTERVAL
    WAITED=$((WAITED + INTERVAL))
done

echo

# Show running containers
print_status "Running containers:"
docker ps --filter "name=rpsd-prefect"

echo
echo "🎉 Prefect Infrastructure Started!"
echo "=================================="
echo
print_success "Connection Information:"
echo
echo "📍 From Host Machine:"
echo -e "   ${GREEN}PREFECT_API_URL=${NC}http://localhost:4200/api"
echo
echo "📍 From Devcontainer:"
echo -e "   ${GREEN}PREFECT_API_URL=${NC}http://host.docker.internal:4200/api"
echo
echo "🌐 Web Interfaces:"
echo -e "   ${GREEN}Prefect UI:${NC} http://localhost:4200"
echo
print_status "To stop Prefect:"
echo -e "   ${BLUE}./stop.sh${NC}             # Keep data"
echo -e "   ${BLUE}./stop.sh --clean${NC}     # Remove all data"
echo
print_status "View logs:"
echo -e "   ${BLUE}docker logs -f rpsd-prefect${NC}"
echo
