"""
Unified application settings combining transport and storage configuration.
"""

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from rpsd_storage.settings import StorageSettings
from rpsd_transport.settings import (
    ForwardSettings,
    KafkaSettings,
    RabbitMQSettings,
    TransportSettings,
)


class ConsumerSettings(BaseModel):
    """Consumer settings for the message broker consumer (consumer.py).

    Separate from ForwardSettings to demonstrate proper separation of
    concerns: publishing vs. consuming are different responsibilities.

    Environment variables (via AppSettings):
    - APP__CONSUMER__CARRIER=kafka
    - APP__CONSUMER__TOPIC=enriched-events
    - APP__CONSUMER__KAFKA__BOOTSTRAP_SERVERS=...
    - APP__CONSUMER__KAFKA__GROUP_ID=demo-consumer
    - APP__CONSUMER__RABBITMQ__URL=...
    """

    carrier: Literal["kafka", "rabbitmq"] | None = None
    topic: str | None = None
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)


class AppSettings(BaseSettings):
    """
    Unified application settings.

    Configuration via environment variables:
        APP__TRANSPORT__API_KEY=secret123
        APP__STORAGE__PROVIDER=fs
        APP__STORAGE__FS__BASE_PATH=/tmp/storage
        APP__STORAGE__S3__BUCKET_NAME=my-bucket
        APP__FORWARD__CARRIER=kafka
        APP__FORWARD__RECIPIENT=enriched-events
        APP__FORWARD__MODE=fatheavy
        APP__FORWARD__KAFKA__BOOTSTRAP_SERVERS=host.docker.internal:9092
        APP__CONSUMER__CARRIER=kafka
        APP__CONSUMER__TOPIC=enriched-events
        APP__CONSUMER__KAFKA__GROUP_ID=demo-consumer
    """

    model_config = SettingsConfigDict(
        env_prefix="APP__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    transport: TransportSettings = TransportSettings()
    storage: StorageSettings = StorageSettings()
    forward: ForwardSettings = Field(default_factory=ForwardSettings)
    consumer: ConsumerSettings = Field(default_factory=ConsumerSettings)
