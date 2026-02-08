# Kafka Infrastructure for rpsd-commons

This directory contains scripts and configuration to run Kafka infrastructure on your host machine for use with rpsd-commons examples.

## Purpose

The `rpsd-transport` package includes optional Kafka support via the `aiokafka` library. To keep the devcontainer lightweight and the Kafka dependency truly optional, Kafka infrastructure runs externally on the host machine rather than inside the devcontainer.

## Architecture

```
Host Machine:
  ├─ Kafka Broker (localhost:9092)
  ├─ Kafka UI (localhost:8080)
  └─ Schema Registry (localhost:8081)
       ↕
  host.docker.internal:9092
       ↕
Devcontainer:
  └─ rpsd-commons development environment
     └─ Examples using KafkaPubSubCarrier
```

## Prerequisites

- **Docker** installed on your host machine
- Docker must be running before starting Kafka

## Quick Start

### Start Kafka

From your **host machine** (not from inside the devcontainer):

```bash
cd /path/to/rpsd-commons/host-scripts
./kafka-start.sh
```

This will:
1. Start Kafka broker (KRaft mode, no Zookeeper)
2. Start Kafka UI for visualization
3. Start Schema Registry for schema management
4. Create default topics (`enriched-events`)
5. Print connection information

### Stop Kafka

```bash
./kafka-stop.sh
```

To stop Kafka and remove all data:

```bash
./kafka-stop.sh --clean
```

## Connection Information

### From Host Machine

When connecting from applications running directly on your host:

```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

### From Devcontainer

When connecting from applications running inside the devcontainer:

```bash
KAFKA_BOOTSTRAP_SERVERS=host.docker.internal:9092
```

Docker provides the special DNS name `host.docker.internal` that resolves to the host machine's IP address.

### Web Interfaces

- **Kafka UI**: http://localhost:8080
  - Browse topics, messages, consumer groups
  - View broker configuration
  - Create/delete topics

- **Schema Registry**: http://localhost:8081
  - Manage Avro/Protobuf/JSON schemas
  - View schema versions
  - Check compatibility

## Configuration

### Docker Compose Services

The `docker-compose.yml` defines three services:

1. **kafka** - Apache Kafka broker
   - KRaft mode (no Zookeeper dependency)
   - Port 9092: Client connections
   - Port 9093: Internal controller
   - Data persisted in named volume

2. **kafka-ui** - Kafka UI web interface
   - Browse and manage Kafka resources
   - Port 8080

3. **schema-registry** - Confluent Schema Registry
   - Schema management and validation
   - Port 8081

### Data Persistence

Kafka data is stored in a Docker named volume `kafka-data`. This persists across container restarts unless you use `--clean` flag.

## Using with rpsd-commons Examples

### 1. Install Kafka Optional Dependency

From inside the devcontainer:

```bash
cd examples/fastapi_ingest_app
uv sync --extra kafka
```

Or add to your .env file:

```bash
APP__FORWARD__CARRIER=kafka
APP__FORWARD__RECIPIENT=enriched-events
APP__FORWARD__MODE=fatheavy
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092
APP__FORWARD__KAFKA__CLIENT_ID=fastapi-forwarder
```

### 2. Start Kafka (from host)

```bash
./host-scripts/kafka-start.sh
```

### 3. Run Example (from devcontainer)

```bash
cd examples/fastapi_ingest_app
uv run uvicorn fastapi_ingest_app.main:app --reload
```

### 4. Verify

- Open http://localhost:8080 in your browser
- Navigate to Topics → enriched-events
- Send test requests to see messages appear

## Troubleshooting

### Kafka Won't Start

**Check if port is already in use:**

```bash
lsof -i :9092  # On macOS/Linux
netstat -ano | findstr :9092  # On Windows
```

**View Kafka logs:**

```bash
docker logs rpsd-kafka
```

### Can't Connect from Devcontainer

**Test connectivity:**

```bash
# From inside devcontainer
nc -zv host.docker.internal 9092
```

**Check if Kafka is running:**

```bash
# From host
docker ps | grep kafka
```

### Wrong Bootstrap Server

**Common mistakes:**

- ❌ Using `localhost:9092` from devcontainer (won't work)
- ❌ Using `kafka:9092` from devcontainer (kafka service isn't in devcontainer network)
- ✅ Using `host.docker.internal:9092` from devcontainer
- ✅ Using `localhost:9092` from host machine

### Topics Don't Exist

**Create topic manually:**

```bash
docker exec rpsd-kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create \
    --topic my-topic \
    --partitions 3 \
    --replication-factor 1
```

**List all topics:**

```bash
docker exec rpsd-kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --list
```

## Advanced Usage

### Creating Additional Topics

```bash
docker exec rpsd-kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create \
    --topic your-topic-name \
    --partitions 3 \
    --replication-factor 1 \
    --config retention.ms=604800000
```

### Consuming Messages from CLI

```bash
docker exec rpsd-kafka kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic enriched-events \
    --from-beginning \
    --property print.headers=true
```

### Producing Test Messages

```bash
docker exec -it rpsd-kafka kafka-console-producer.sh \
    --bootstrap-server localhost:9092 \
    --topic enriched-events
```

### Viewing Consumer Groups

```bash
docker exec rpsd-kafka kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --list
```

## Alternative Setups

### Using Cloud Kafka

Instead of running Kafka locally, you can use cloud-managed Kafka:

- **Confluent Cloud**: https://confluent.cloud
- **AWS MSK**: https://aws.amazon.com/msk/
- **Azure Event Hubs**: https://azure.microsoft.com/en-us/services/event-hubs/

Update your `.env` with the cloud broker URLs:

```bash
APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
```

### Using Different Kafka Version

Edit `docker-compose.yml` and change the image tag:

```yaml
kafka:
  image: apache/kafka:3.6.0  # Specify version
```

## Cleanup

### Remove All Kafka Data

```bash
./kafka-stop.sh --clean
```

This removes:
- All topics and their data
- Consumer group offsets
- Schema registry data

### Remove Docker Images

```bash
docker rmi apache/kafka:latest
docker rmi provectuslabs/kafka-ui:latest
docker rmi confluentinc/cp-schema-registry:latest
```

## Resources

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [KRaft Mode](https://kafka.apache.org/documentation/#kraft)
- [Kafka UI Documentation](https://docs.kafka-ui.provectus.io/)
- [Schema Registry Documentation](https://docs.confluent.io/platform/current/schema-registry/index.html)
