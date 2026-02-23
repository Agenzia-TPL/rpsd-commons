from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HTTPSettings(BaseModel):
    """HTTP carrier settings.

    Environment variables (via TransportSettings):
    - TRANSPORT__HTTP__BASE_URL=http://localhost:8000
    - TRANSPORT__HTTP__TIMEOUT=30
    """

    base_url: str | None = None
    timeout: int = 30


class KafkaSettings(BaseModel):
    """Kafka broker settings.

    Environment variables (via TransportSettings):
    - TRANSPORT__KAFKA__BOOTSTRAP_SERVERS=localhost:9092
    - TRANSPORT__KAFKA__GROUP_ID=my-group
    - TRANSPORT__KAFKA__CLIENT_ID=my-client
    - TRANSPORT__KAFKA__TIMEOUT=30
    """

    bootstrap_servers: str = "localhost:9092"
    group_id: str | None = None
    client_id: str | None = None
    timeout: int = 30


class RabbitMQSettings(BaseModel):
    """RabbitMQ broker settings.

    Environment variables (via TransportSettings):
    - TRANSPORT__RABBITMQ__URL=amqp://guest:guest@localhost/
    - TRANSPORT__RABBITMQ__EXCHANGE=
    - TRANSPORT__RABBITMQ__EXCHANGE_TYPE=direct
    - TRANSPORT__RABBITMQ__QUEUE_DURABLE=true
    - TRANSPORT__RABBITMQ__PREFETCH_COUNT=10
    - TRANSPORT__RABBITMQ__TIMEOUT=30
    """

    url: str = "amqp://guest:guest@localhost/"
    exchange: str = ""
    exchange_type: str = "direct"
    queue_durable: bool = True
    prefetch_count: int = 10
    timeout: int = 30


class ForwardSettings(BaseModel):
    """Forward carrier settings for IngestProcessor.

    Environment variables (via TransportSettings):
    - TRANSPORT__INGEST__FORWARD__CARRIER=kafka
    - TRANSPORT__INGEST__FORWARD__RECIPIENT=output-topic
    - TRANSPORT__INGEST__FORWARD__MODE=fatheavy
    - TRANSPORT__INGEST__FORWARD__KAFKA__BOOTSTRAP_SERVERS=...
    - TRANSPORT__INGEST__FORWARD__RABBITMQ__URL=...
    """

    carrier: Literal["http", "kafka", "rabbitmq"] | None = None
    recipient: str | None = None
    mode: Literal["fatheavy", "slimfast"] = "fatheavy"
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)


class IngestSettings(BaseModel):
    """Ingest processor settings.

    Environment variables (via TransportSettings):
    - TRANSPORT__INGEST__FORWARD__CARRIER=kafka
    - TRANSPORT__INGEST__FORWARD__RECIPIENT=output-topic
    - TRANSPORT__INGEST__FORWARD__MODE=fatheavy
    """

    forward: ForwardSettings = Field(default_factory=ForwardSettings)


class TransportSettings(BaseSettings):
    """Transport configuration for rpsd-transport package.

    Environment variables use double underscore delimiter:
    - TRANSPORT__API_KEY=your-secret-key
    - TRANSPORT__CARRIER=http
    - TRANSPORT__KAFKA__BOOTSTRAP_SERVERS=localhost:9092
    - TRANSPORT__RABBITMQ__URL=amqp://guest:guest@localhost/
    - TRANSPORT__INGEST__FORWARD__CARRIER=kafka
    - TRANSPORT__INGEST__FORWARD__RECIPIENT=output-topic
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSPORT__",
        env_nested_delimiter="__",
    )

    api_key: str | None = None
    carrier: Literal["http", "kafka", "rabbitmq"] = "http"
    http: HTTPSettings = Field(default_factory=HTTPSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    ingest: IngestSettings = Field(default_factory=IngestSettings)
