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


class TransportSettings(BaseSettings):
    """Transport configuration for rpsd-transport package.

    Environment variables use double underscore delimiter:
    - TRANSPORT__API_KEY=your-secret-key
    - TRANSPORT__CARRIER=http
    - TRANSPORT__KAFKA__BOOTSTRAP_SERVERS=localhost:9092
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSPORT__", env_nested_delimiter="__"
    )

    api_key: str | None = None
    carrier: Literal["http", "kafka"] = "http"
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
