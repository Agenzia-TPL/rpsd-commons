from pydantic_settings import BaseSettings, SettingsConfigDict


class TransportSettings(BaseSettings):
    """
    Transport configuration for rpsd-transport package.

    Environment variables use double underscore delimiter:
    - TRANSPORT__API_KEY=your-secret-key
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSPORT__", env_nested_delimiter="__"
    )

    api_key: str | None = None
