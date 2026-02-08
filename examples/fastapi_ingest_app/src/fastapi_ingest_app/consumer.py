"""
Kafka consumer demonstrating how to consume forwarded messages.

This script shows how to:
- Connect to Kafka broker using KafkaPubSubCarrier
- Consume messages from enriched-events topic
- Process both slimfast (inline) and fatheavy (reference) messages
- Fetch content from storage URLs when needed
"""

import asyncio
import logging

import httpx

from fastapi_ingest_app.settings import AppSettings
from rpsd_transport.carriers.pubsub.kafka import KafkaPubSubCarrier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Consume and process messages from Kafka."""
    settings = AppSettings()

    if not settings.forward.carrier:
        logger.error("Forward carrier not configured. Set APP__FORWARD__CARRIER=kafka")
        return

    logger.info("Starting Kafka consumer...")
    logger.info("Bootstrap servers: %s", settings.forward.kafka.bootstrap_servers)
    logger.info("Topic: %s", settings.forward.recipient)

    # Create Kafka carrier
    carrier = KafkaPubSubCarrier(
        bootstrap_servers=settings.forward.kafka.bootstrap_servers,
        group_id="demo-consumer",
        client_id="demo-consumer-client",
    )

    # HTTP client for fetching fatheavy content
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            logger.info("Consuming messages (press Ctrl+C to stop)...")
            message_count = 0

            async for message in carrier.consume(settings.forward.recipient):
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

                    # Optionally fetch content from storage URL
                    try:
                        response = await http_client.get(message.where)
                        response.raise_for_status()
                        content = response.content
                        logger.info(
                            "  Content length (fetched): %d bytes",
                            len(content),
                        )
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
            if hasattr(carrier, "stop"):
                await carrier.stop()
            logger.info("Consumer stopped. Processed %d messages.", message_count)


if __name__ == "__main__":
    asyncio.run(main())
