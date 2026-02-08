from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseModel):
    """Kafka broker settings.

    Environment variables (via TransportSettings):
    - TRANSPORT__KAFKA__BOOTSTRAP_SERVERS=localhost:9092
    - TRANSPORT__KAFKA__GROUP_ID=my-group
    - TRANSPORT__KAFKA__CLIENT_ID=my-client
    """

    bootstrap_servers: str = "localhost:9092"
    group_id: str | None = None
    client_id: str | None = None


class ForwardSettings(BaseModel):
    """Forward carrier settings for IngestProcessor.

    Environment variables (via TransportSettings):
    - TRANSPORT__INGEST__FORWARD__CARRIER=kafka
    - TRANSPORT__INGEST__FORWARD__RECIPIENT=output-topic
    - TRANSPORT__INGEST__FORWARD__MODE=fatheavy
    - TRANSPORT__INGEST__FORWARD__KAFKA__BOOTSTRAP_SERVERS=...
    """

    carrier: Literal["http", "kafka"] | None = None
    recipient: str | None = None
    mode: Literal["fatheavy", "slimfast"] = "fatheavy"
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)


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
    - TRANSPORT__INGEST__FORWARD__CARRIER=kafka
    - TRANSPORT__INGEST__FORWARD__RECIPIENT=output-topic
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSPORT__", env_nested_delimiter="__"
    )

    api_key: str | None = None
    carrier: Literal["http", "kafka"] = "http"
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    ingest: IngestSettings = Field(default_factory=IngestSettings)
