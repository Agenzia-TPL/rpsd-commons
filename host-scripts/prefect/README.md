# Workflow engine Infrastructure for rpsd-commons

This directory contains scripts and configuration to run workflow engine infrastructure (Prefect) on your host machine for use with rpsd-commons examples.

## Purpose

To keep the devcontainer lightweight, workflow engine infrastructure runs externally on the host machine rather than inside the devcontainer.

## Architecture

```
Host Machine:
  ├─ Prefect Server (localhost:4200)
  ├─ PostgreSQL (internal)
  └─ Redis (internal)
       ↕
  host.docker.internal:4200
       ↕
Devcontainer:
  └─ rpsd-commons development environment
     └─ Examples using Prefect
```

## Prerequisites

- **Docker** installed on your host machine
- Docker must be running before starting Prefect
- **Platform Support**: Works on both Intel (x86_64) and Apple Silicon (ARM64) Macs thanks to multi-architecture images

## Quick Start

### Start Prefect

From your **host machine** (not from inside the devcontainer):

```bash
cd /path/to/rpsd-commons/host-scripts/prefect
./start.sh
```

This will:
1. Start PostgreSQL database
2. Start Redis cache
3. Start Prefect server with UI
4. Print connection information

### Stop Prefect

```bash
./stop.sh
```

To stop Prefect and remove all data:

```bash
./stop.sh --clean
```

## Connection Information

### From Host Machine

When connecting from applications running directly on your host:

```bash
PREFECT_API_URL=http://localhost:4200/api
```

### From Devcontainer

When connecting from applications running inside the devcontainer:

```bash
PREFECT_API_URL=http://host.docker.internal:4200/api
```

Docker provides the special DNS name `host.docker.internal` that resolves to the host machine's IP address.

### Web Interfaces

- **Prefect UI**: http://localhost:4200

## Configuration

### Docker Compose Services

The `docker-compose.yml` defines three services:

1. **postgres** - PostgreSQL 17 database for Prefect metadata
   - Image: `postgres:17`
   - Container: `rpsd-prefect-postgres`
   - Data persisted in volume: `rpsd-prefect-postgres-data`

2. **redis** - Redis 8 server for caching/queuing
   - Image: `redis:8-alpine`
   - Container: `rpsd-prefect-redis`
   - Data persisted in volume: `rpsd-prefect-redis-data`

3. **prefect** - Prefect server
   - Image: `prefecthq/prefect:3-latest` (multi-arch: amd64 + arm64)
   - Container: `rpsd-prefect`
   - Port 4200: API & UI
   - Depends on postgres and redis
   - **Note**: Supports both Intel (x86_64) and Apple Silicon (ARM64) Macs

### Data Persistence

Data is stored in Docker named volumes:
- `rpsd-prefect-postgres-data` - PostgreSQL database (Prefect metadata)
- `rpsd-prefect-redis-data` - Redis cache data

Data persists across container restarts unless you use the `--clean` flag with `./stop.sh`.

## Using with rpsd-commons

### 1. Start Prefect (from host)

```bash
./host-scripts/prefect/start.sh
```

### 2. Configure your Python code (from devcontainer)

Set the Prefect API URL to connect to the host-based server:

```python
import os
os.environ["PREFECT_API_URL"] = "http://host.docker.internal:4200/api"
```

Or set it in your shell:

```bash
export PREFECT_API_URL=http://host.docker.internal:4200/api
```

### 3. Verify

- Open http://localhost:4200 in your browser to access the Prefect UI

## Troubleshooting

### Prefect Won't Start

**Check if port is already in use:**

```bash
lsof -i :4200  # On macOS/Linux
netstat -ano | findstr :4200  # On Windows
```

**View container logs:**

```bash
docker logs rpsd-prefect          # Prefect server logs
docker logs rpsd-prefect-postgres # PostgreSQL logs
docker logs rpsd-prefect-redis    # Redis logs
docker logs -f rpsd-prefect       # Follow Prefect logs in real-time
```

**Check service health:**

```bash
docker ps --filter "name=rpsd-prefect"  # Shows all Prefect containers
docker inspect rpsd-prefect --format='{{.State.Health.Status}}'  # Check health
```

### Can't Connect from Devcontainer

**Test connectivity:**

```bash
# From inside devcontainer
nc -zv host.docker.internal 4200
```

**Check if Prefect is running:**

```bash
# From host
docker ps | grep prefect
```

### Wrong API URL

**Common mistakes:**

- ❌ Using `localhost:4200` from devcontainer (won't work - localhost refers to the container itself)
- ❌ Using `prefect:4200` from devcontainer (prefect service isn't in devcontainer network)
- ✅ Using `host.docker.internal:4200` from devcontainer (correct)
- ✅ Using `localhost:4200` from host machine (correct)

## Cleanup

### Remove All Prefect Data

```bash
./stop.sh --clean
```

This removes:
- All PostgreSQL data (flow definitions, run history, metadata)
- All Redis cache data
- All Docker volumes

**Warning:** This action cannot be undone. You will be prompted for confirmation.
