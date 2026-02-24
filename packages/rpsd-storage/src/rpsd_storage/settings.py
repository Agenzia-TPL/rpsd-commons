from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Settings(BaseModel):
    """S3 storage provider settings."""

    bucket_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None


class FSSettings(BaseModel):
    """Filesystem storage provider settings."""

    base_path: str = "/tmp/ingested"


class HTTPSettings(BaseModel):
    """HTTP storage provider settings."""

    timeout: float = 30.0


class StorageSettings(BaseSettings):
    """
    Storage configuration for rpsd-storage package.

    Environment variables use double underscore delimiter:
    - STORAGE__PROVIDER=s3
    - STORAGE__S3__BUCKET_NAME=my-bucket
    - STORAGE__S3__AWS_ACCESS_KEY_ID=... (optional, for testing)
    - STORAGE__S3__AWS_SECRET_ACCESS_KEY=... (optional, for testing)
    - STORAGE__S3__AWS_SESSION_TOKEN=... (optional, for testing)
    - STORAGE__S3__REGION_NAME=us-east-1 (optional)
    - STORAGE__S3__ENDPOINT_URL=http://localhost:4566 (optional, for LocalStack/MinIO)
    - STORAGE__FS__BASE_PATH=/tmp/storage
    - STORAGE__HTTP__TIMEOUT=30.0
    """

    model_config = SettingsConfigDict(
        env_prefix="STORAGE__",
        env_nested_delimiter="__",
    )

    provider: Literal["s3", "fs", "http"] = "fs"
    compare_before_save: bool = False
    s3: S3Settings = Field(default_factory=S3Settings)
    fs: FSSettings = Field(default_factory=FSSettings)
    http: HTTPSettings = Field(default_factory=HTTPSettings)

    @model_validator(mode="after")
    def validate_provider_config(self) -> Self:
        """Ensure required settings exist for the selected provider."""
        if self.provider == "s3" and not self.s3.bucket_name:
            raise ValueError(
                "S3 bucket_name is required when provider='s3'. "
                "Set STORAGE__S3__BUCKET_NAME environment variable."
            )
        return self
