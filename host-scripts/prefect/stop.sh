#!/bin/bash

# Stop script for Prefect workflow engine infrastructure
# This script stops Prefect server, PostgreSQL, and Redis
# Usage: ./stop.sh [--clean]
#   --clean: Remove all data volumes (cannot be undone!)

set -e  # Exit on any error

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

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found in $SCRIPT_DIR"
    exit 1
fi

# Parse command line arguments
CLEAN_DATA=false
if [ "$1" = "--clean" ]; then
    CLEAN_DATA=true
    echo "🧹 Stopping Prefect Infrastructure and Removing Data..."
    echo "======================================================"
    echo
    print_warning "This will remove all Prefect data permanently!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled. No changes made."
        exit 0
    fi
else
    echo "🛑 Stopping Prefect Infrastructure..."
    echo "====================================="
    echo
fi

# Check if any containers are running
RUNNING_CONTAINERS=$(docker ps --filter "name=rpsd-prefect" --format "{{.Names}}" | wc -l)

if [ "$RUNNING_CONTAINERS" -eq 0 ]; then
    print_warning "No Prefect containers are currently running."
    if [ "$CLEAN_DATA" = true ]; then
        print_status "Checking for volumes to clean up..."
    else
        print_status "Nothing to stop."
        exit 0
    fi
fi

# Stop services
if [ "$CLEAN_DATA" = true ]; then
    print_status "Stopping containers and removing volumes..."
    docker compose down -v
    print_success "Containers stopped and volumes removed"
    echo
    print_status "The following data was removed:"
    echo "  • PostgreSQL database (Prefect metadata)"
    echo "  • Redis cache data"
    echo
    print_success "Next start will be a fresh installation"
else
    print_status "Stopping containers (keeping data volumes)..."
    docker compose down
    print_success "Containers stopped (data preserved)"
    echo
    print_status "Data volumes retained:"
    echo "  • rpsd-prefect-postgres-data (PostgreSQL database)"
    echo "  • rpsd-prefect-redis-data (Redis cache)"
    echo
    print_status "To remove all data, run:"
    echo -e "  ${BLUE}./stop.sh --clean${NC}"
fi

echo
print_success "Prefect infrastructure stopped successfully"
echo
print_status "To start again:"
echo -e "  ${BLUE}./start.sh${NC}"
echo
