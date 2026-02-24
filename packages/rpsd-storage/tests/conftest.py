"""
Pytest configuration and fixtures for rpsd-storage tests.
"""

import os
import tempfile
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from test_utils import TEST_SCENARIOS, create_test_file_data, create_test_metadata

from rpsd_storage import FSStorageProvider, S3StorageProvider


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file system tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def fs_storage_provider(temp_dir):
    """Create an FSStorageProvider instance with temporary directory."""
    return FSStorageProvider(base_path=str(temp_dir))


@pytest.fixture
def mock_s3_setup():
    """Set up mocked S3 environment."""
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3_client.create_bucket(Bucket=bucket_name)
        yield (s3_client, bucket_name)


@pytest.fixture
def s3_storage_provider(mock_s3_setup):
    """Create an S3StorageProvider instance with mocked S3."""
    s3_client, bucket_name = mock_s3_setup
    return S3StorageProvider(bucket_name=bucket_name)


@pytest.fixture(params=["text", "json", "xml", "csv", "pdf", "png"])
def content_type(request):
    """Parametrized fixture for different content types."""
    return request.param


@pytest.fixture
def sample_content(content_type):
    """Create sample content based on content type."""
    content, filename, mime_type = create_test_file_data(content_type)
    return {
        "content": content,
        "filename": filename,
        "mime_type": mime_type,
        "content_type": content_type,
    }


@pytest.fixture(params=["basic", "full", "minimal", "user_export"])
def metadata_preset(request):
    """Parametrized fixture for different metadata presets."""
    return request.param


@pytest.fixture
def sample_metadata(metadata_preset):
    """Create sample metadata based on preset."""
    return create_test_metadata(metadata_preset)


@pytest.fixture(params=TEST_SCENARIOS)
def test_scenario(request):
    """Parametrized fixture for comprehensive test scenarios."""
    scenario = request.param
    content, filename, mime_type = create_test_file_data(scenario["content_type"])
    metadata = create_test_metadata(scenario["metadata_preset"])
    return {
        "name": scenario["name"],
        "description": scenario["description"],
        "content": content,
        "filename": filename,
        "mime_type": mime_type,
        "metadata": metadata,
        "content_type": scenario["content_type"],
    }


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "file: tests for file system storage provider")
    config.addinivalue_line("markers", "s3: tests for S3 storage provider")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "error_handling: tests for error conditions")
    config.addinivalue_line(
        "markers",
        "live_s3: tests against a real S3-compatible endpoint "
        "(requires STORAGE__S3__BUCKET_NAME)",
    )


@pytest.fixture(scope="session")
def s3_live_settings():
    """
    Load S3Settings from the environment. Skips if STORAGE__S3__BUCKET_NAME
    is not set, so normal CI runs are completely unaffected.

    Reads packages/rpsd-storage/.env (STORAGE__* vars only) if it exists.
    For real AWS: set STORAGE__S3__BUCKET_NAME; credentials come from the
    standard AWS chain (IAM role, ~/.aws/credentials, etc.).
    For LocalStack/MinIO: also set STORAGE__S3__ENDPOINT_URL and credentials.
    """
    from rpsd_storage.settings import StorageSettings

    env_file = Path(__file__).parent.parent / ".env"
    s3 = StorageSettings(_env_file=env_file if env_file.exists() else None).s3
    if not s3.bucket_name:
        pytest.skip(
            "Live S3 tests skipped: set STORAGE__S3__BUCKET_NAME to enable",
            allow_module_level=True,
        )
    return s3


@pytest.fixture(scope="session")
def s3_live_bucket(s3_live_settings):
    """
    Use the configured bucket and clean up only the objects written during
    this test session (those under the 'live_' prefixes used by the tests).

    The bucket must already exist; this fixture does NOT create or delete it,
    so it works against real AWS where you may not have CreateBucket permission.
    """
    bucket_name = s3_live_settings.bucket_name
    client = boto3.client(
        "s3",
        endpoint_url=s3_live_settings.endpoint_url,
        aws_access_key_id=s3_live_settings.aws_access_key_id,
        aws_secret_access_key=s3_live_settings.aws_secret_access_key,
        aws_session_token=s3_live_settings.aws_session_token,
        region_name=s3_live_settings.region_name or "us-east-1",
    )
    yield bucket_name
    # Clean up only objects written by these tests (all use a "live_*" who prefix)
    for prefix in ("live_user/", "alice_live/", "bob_live/", "live_order/"):
        response = client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        for obj in response.get("Contents", []):
            client.delete_object(Bucket=bucket_name, Key=obj["Key"])


@pytest.fixture
def s3_live_provider(s3_live_settings, s3_live_bucket):
    """S3StorageProvider pointed at the live endpoint, compare_before_save enabled."""
    return S3StorageProvider(
        bucket_name=s3_live_bucket,
        compare_before_save=True,
        aws_access_key_id=s3_live_settings.aws_access_key_id,
        aws_secret_access_key=s3_live_settings.aws_secret_access_key,
        aws_session_token=s3_live_settings.aws_session_token,
        region_name=s3_live_settings.region_name,
        endpoint_url=s3_live_settings.endpoint_url,
    )


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before and after each test."""
    original_env = {}
    storage_env_vars = ["STORAGE_PROVIDER", "FS_BASE_PATH", "S3_BUCKET_NAME"]
    for var in storage_env_vars:
        if var in os.environ:
            original_env[var] = os.environ[var]
            del os.environ[var]
    yield
    for var in storage_env_vars:
        if var in os.environ:
            del os.environ[var]
        if var in original_env:
            os.environ[var] = original_env[var]
