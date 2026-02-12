"""
Message broker consumer demonstrating how to consume forwarded messages.

This script shows how to:
- Connect to message broker (Kafka or RabbitMQ) using carrier factory
- Consume messages from configured topic/queue
- Process both slimfast (inline) and fatheavy (reference) messages
- Use rpsd-storage to fetch content from any URL scheme (file://, http://, https://, s3://)
- Display rich metadata from storage providers
"""

import asyncio
import logging

from fastapi_ingest_app.settings import AppSettings
from rpsd_storage.providers.base import StorageProvider
from rpsd_transport import TransportSettings, get_carrier
from rpsd_transport.carriers.pubsub.base import PubSubCarrier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Consume and process messages from configured message broker."""
    settings = AppSettings()

    if not settings.consumer.carrier:
        logger.error(
            "Consumer carrier not configured. "
            "Set APP__CONSUMER__CARRIER=kafka or APP__CONSUMER__CARRIER=rabbitmq"
        )
        return

    if not settings.consumer.topic:
        logger.error(
            "Consumer topic not configured. "
            "Set APP__CONSUMER__TOPIC=<topic-or-queue-name>"
        )
        return

    # Type-safe assignment
    topic = settings.consumer.topic

    logger.info("Starting %s consumer...", settings.consumer.carrier.upper())
    logger.info("Topic/Queue: %s", topic)

    # Log carrier-specific connection info
    if settings.consumer.carrier == "kafka":
        logger.info(
            "Kafka bootstrap servers: %s",
            settings.consumer.kafka.bootstrap_servers,
        )
        logger.info("Consumer group: %s", settings.consumer.kafka.group_id or "None")
        if not settings.consumer.kafka.group_id:
            logger.error(
                "Kafka group_id is required for consuming. "
                "Set APP__CONSUMER__KAFKA__GROUP_ID=<group-name>"
            )
            return
    elif settings.consumer.carrier == "rabbitmq":
        logger.info("RabbitMQ URL: %s", settings.consumer.rabbitmq.url)
        logger.info("Exchange: %s", settings.consumer.rabbitmq.exchange or "(default)")

    # Create carrier using factory with consumer settings
    transport_settings = TransportSettings(
        carrier=settings.consumer.carrier,
        kafka=settings.consumer.kafka,
        rabbitmq=settings.consumer.rabbitmq,
    )
    carrier = get_carrier(transport_settings)

    # Ensure we have a PubSub carrier (not HTTP)
    if not isinstance(carrier, PubSubCarrier):
        logger.error(
            "Carrier type '%s' does not support consumption. "
            "Use 'kafka' or 'rabbitmq' carrier.",
            settings.forward.carrier,
        )
        return

    try:
        logger.info("Consuming messages (press Ctrl+C to stop)...")
        message_count = 0

        async for message in carrier.consume(topic):
            message_count += 1
            logger.info("=" * 60)
            logger.info("Message #%d received", message_count)
            logger.info("  Who: %s", message.who)
            logger.info("  What: %s", message.what)
            logger.info("  Content-Type: %s", message.metadata.content_type)

            # Check if message is fatheavy (content by reference)
            if message.where:
                logger.info("  Storage URL: %s", message.where)
                logger.info("  Message type: fatheavy (content by reference)")

                # Fetch content from storage URL using rpsd-storage
                try:
                    content, metadata = StorageProvider.load_from_url(message.where)

                    logger.info("  Content retrieved successfully:")
                    logger.info("    Provider: %s", metadata.provider)
                    logger.info("    Content length: %d bytes", metadata.content_length)
                    logger.info("    Content type: %s", metadata.content_type)
                    logger.info("    Original filename: %s", metadata.original_filename)
                    logger.info("    Hash (MD5): %s", metadata.hash)

                    # Log provider-specific metadata if available
                    if metadata.status_code is not None:
                        logger.info("    HTTP status: %d", metadata.status_code)
                    if metadata.etag is not None:
                        logger.info("    S3 ETag: %s", metadata.etag)

                except FileNotFoundError as e:
                    logger.warning("  Content not found: %s", e)
                except ValueError as e:
                    logger.warning("  Unsupported URL scheme: %s", e)
                except Exception as e:
                    logger.warning("  Failed to fetch content: %s", e)

            # Check if message is slimfast (content inline)
            elif message.content:
                logger.info("  Message type: slimfast (content inline)")
                logger.info("  Content length: %d bytes", len(message.content))

            else:
                logger.warning("  Message has neither content nor storage URL!")

            logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\nShutting down consumer...")
    except Exception as e:
        logger.exception("Error consuming messages: %s", e)
    finally:
        await carrier.stop()
        logger.info("Consumer stopped. Processed %d messages.", message_count)


if __name__ == "__main__":
    asyncio.run(main())
