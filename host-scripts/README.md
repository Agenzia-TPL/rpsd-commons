# Message Broker Infrastructure for rpsd-commons

This directory contains scripts and configuration to run message broker infrastructure (Kafka and RabbitMQ) on your host machine for use with rpsd-commons examples.

## Purpose

The `rpsd-transport` package includes optional support for multiple message brokers:
- **Kafka** via the `aiokafka` library
- **RabbitMQ** via the `aio-pika` library

To keep the devcontainer lightweight and these dependencies truly optional, broker infrastructure runs externally on the host machine rather than inside the devcontainer.

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
cd /path/to/rpsd-commons/host-scripts/kafka
./start.sh
```

This will:
1. Start Kafka broker (KRaft mode, no Zookeeper)
2. Start Kafka UI for visualization
3. Start Schema Registry for schema management
4. Create default topics (`enriched-events`)
5. Print connection information

### Stop Kafka

```bash
./stop.sh
```

To stop Kafka and remove all data:

```bash
./stop.sh --clean
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
./host-scripts/kafka/start.sh
```

### 3. Run Example (from devcontainer)

```bash
cd examples/fastapi_ingest_app
uv run uvicorn fastapi_ingest_app.main:app --reload
```

**Or run the automated demo:**

```bash
cd examples/fastapi_ingest_app
./demo.sh kafka  # Runs complete end-to-end test with Kafka
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
./stop.sh --clean
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

---

# RabbitMQ Infrastructure

## Quick Start

### Start RabbitMQ

From your **host machine** (not from inside the devcontainer):

```bash
cd /path/to/rpsd-commons/host-scripts
./start.sh
```

This will:
1. Start RabbitMQ broker with management plugin
2. Wait for RabbitMQ to be healthy
3. Print connection information

### Stop RabbitMQ

```bash
./stop.sh
```

To stop RabbitMQ and remove all data:

```bash
./stop.sh --clean
```

## Connection Information

### From Host Machine

When connecting from applications running directly on your host:

```bash
RABBITMQ_URL=amqp://guest:guest@localhost/
```

### From Devcontainer

When connecting from applications running inside the devcontainer:

```bash
RABBITMQ_URL=amqp://guest:guest@host.docker.internal/
```

Docker provides the special DNS name `host.docker.internal` that resolves to the host machine's IP address.

### Web Interfaces

- **RabbitMQ Management UI**: http://localhost:15672
  - Username: `guest`
  - Password: `guest`
  - Browse queues, exchanges, bindings
  - View message rates and statistics
  - Manage users and permissions

## Configuration

### Docker Compose Service

The `rabbitmq-compose.yml` defines one service:

1. **rabbitmq** - RabbitMQ broker with management plugin
   - Image: `rabbitmq:3-management-alpine`
   - Port 5672: AMQP protocol connections
   - Port 15672: Management UI
   - Data persisted in named volume `rabbitmq-data`
   - Default credentials: guest/guest

### Data Persistence

RabbitMQ data is stored in a Docker named volume `rabbitmq-data`. This persists across container restarts unless you use `--clean` flag.

## Using with rpsd-commons Examples

### 1. Install RabbitMQ Optional Dependency

From inside the devcontainer:

```bash
cd examples/fastapi_ingest_app
uv sync
```

The example already includes `rpsd-transport[rabbitmq]` dependency.

Or add to your .env file:

```bash
APP__FORWARD__CARRIER=rabbitmq
APP__FORWARD__RECIPIENT=enriched-events
APP__FORWARD__MODE=fatheavy
APP__FORWARD__RABBITMQ__URL=amqp://guest:guest@host.docker.internal/
```

### 2. Start RabbitMQ (from host)

```bash
./host-scripts/rabbitmq/start.sh
```

### 3. Run Example (from devcontainer)

```bash
cd examples/fastapi_ingest_app
uv run fastapi-ingest-app
```

**Or run the automated demo:**

```bash
cd examples/fastapi_ingest_app
./demo.sh rabbitmq  # Runs complete end-to-end test with RabbitMQ
```

### 4. Verify

- Open http://localhost:15672 in your browser
- Login with guest/guest
- Navigate to Queues tab
- Send test requests to see queues and messages appear

## Troubleshooting

### RabbitMQ Won't Start

**Check if port is already in use:**

```bash
lsof -i :5672  # On macOS/Linux
lsof -i :15672  # Management UI port
netstat -ano | findstr :5672  # On Windows
```

**View RabbitMQ logs:**

```bash
docker logs rpsd-rabbitmq
```

### Can't Connect from Devcontainer

**Test connectivity:**

```bash
# From inside devcontainer
nc -zv host.docker.internal 5672
```

**Check if RabbitMQ is running:**

```bash
# From host
docker ps | grep rabbitmq
```

### Wrong Connection URL

**Common mistakes:**

- ❌ Using `amqp://localhost/` from devcontainer (won't work)
- ❌ Using `amqp://rabbitmq/` from devcontainer (service isn't in devcontainer network)
- ✅ Using `amqp://guest:guest@host.docker.internal/` from devcontainer
- ✅ Using `amqp://guest:guest@localhost/` from host machine

### Management UI Won't Load

**Check if management plugin is enabled:**

```bash
docker exec rpsd-rabbitmq rabbitmq-plugins list
```

The `rabbitmq_management` plugin should show `[E*]` (explicitly enabled).

## Advanced Usage

### Declaring Queues

Queues are automatically created when messages are published using the default exchange. For explicit queue configuration:

```bash
# Durable queue with message TTL
docker exec rpsd-rabbitmq rabbitmqadmin declare queue \
    name=my-queue \
    durable=true \
    arguments='{"x-message-ttl":3600000}'
```

### Declaring Exchanges

```bash
# Topic exchange
docker exec rpsd-rabbitmq rabbitmqadmin declare exchange \
    name=my-exchange \
    type=topic \
    durable=true
```

### Creating Bindings

```bash
# Bind queue to exchange with routing key
docker exec rpsd-rabbitmq rabbitmqadmin declare binding \
    source=my-exchange \
    destination=my-queue \
    routing_key="events.#"
```

### Viewing Queue Messages

From Management UI:
1. Go to Queues tab
2. Click on queue name
3. Expand "Get messages" section
4. Click "Get Message(s)" to preview without consuming

### Purging Queues

```bash
docker exec rpsd-rabbitmq rabbitmqadmin purge queue name=my-queue
```

### Listing Queues and Exchanges

```bash
# List queues
docker exec rpsd-rabbitmq rabbitmqctl list_queues

# List exchanges
docker exec rpsd-rabbitmq rabbitmqctl list_exchanges

# List bindings
docker exec rpsd-rabbitmq rabbitmqctl list_bindings
```

## Alternative Setups

### Using Cloud RabbitMQ

Instead of running RabbitMQ locally, you can use cloud-managed RabbitMQ:

- **CloudAMQP**: https://www.cloudamqp.com/
- **AWS Amazon MQ**: https://aws.amazon.com/amazon-mq/
- **Azure Service Bus**: https://azure.microsoft.com/en-us/services/service-bus/

Update your `.env` with the cloud broker URL:

```bash
APP__FORWARD__RABBITMQ__URL=amqps://username:password@host.cloudamqp.com/vhost
```

### Using Different RabbitMQ Version

Edit `rabbitmq-compose.yml` and change the image tag:

```yaml
rabbitmq:
  image: rabbitmq:3.12-management-alpine  # Specify version
```

## Cleanup

### Remove All RabbitMQ Data

```bash
./stop.sh --clean
```

This removes:
- All queues and their messages
- All exchanges and bindings
- User configurations

### Remove Docker Images

```bash
docker rmi rabbitmq:3-management-alpine
```

## Comparison: Kafka vs RabbitMQ

| Feature | Kafka | RabbitMQ |
|---------|-------|----------|
| **Architecture** | Distributed log | Message broker |
| **Performance** | Very high throughput | High throughput |
| **Message Ordering** | Per partition | Per queue |
| **Message Retention** | Time/size based | Until consumed (or TTL) |
| **Consumer Model** | Pull-based | Push + Pull |
| **Use Cases** | Event streaming, logs | Task queues, RPC |
| **Complexity** | Higher (KRaft, partitions) | Lower (simpler setup) |
| **Management UI** | Third-party (kafka-ui) | Built-in |

**When to use Kafka:**
- High-throughput event streaming
- Message replay needed
- Multiple consumers per message
- Log aggregation

**When to use RabbitMQ:**
- Task queues and job processing
- Request-reply patterns (RPC)
- Flexible routing (exchanges)
- Simpler operational requirements

## Resources

- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [RabbitMQ Management Plugin](https://www.rabbitmq.com/management.html)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [AMQP 0-9-1 Protocol](https://www.rabbitmq.com/amqp-0-9-1-reference.html)
