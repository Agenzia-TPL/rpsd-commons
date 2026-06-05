# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Tests for S3StorageProvider.
"""

from unittest.mock import patch

import boto3
import pytest
import respx
from botocore.exceptions import ClientError
from moto import mock_aws
from test_utils import (
    SampleMetadata,
    TestContent,
    create_test_file_data,
    verify_file_content,
    verify_metadata_structure,
)

from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.providers.http import HTTPStorageProvider
from rpsd_storage.providers.s3 import S3StorageProvider


class TestS3StorageProviderInit:
    """Test S3StorageProvider initialization."""

    def test_init_with_valid_bucket(self):
        """Test initialization with a valid bucket name."""
        bucket_name = "test-bucket"
        with mock_aws():
            provider = S3StorageProvider(bucket_name=bucket_name)
            assert provider.bucket_name == bucket_name
            assert provider.s3_client is not None

    def test_init_with_empty_bucket_name(self):
        """Test initialization with empty bucket name raises exception."""
        with pytest.raises(Exception, match="S3 bucket not configured"):
            S3StorageProvider(bucket_name="")

    def test_init_with_none_bucket_name(self):
        """Test initialization with None bucket name raises exception."""
        with pytest.raises(Exception, match="S3 bucket not configured"):
            S3StorageProvider(bucket_name=None)


@pytest.mark.s3
class TestS3StorageProviderSave:
    """Test S3StorageProvider save functionality."""

    def test_save_simple_file(self, s3_storage_provider, mock_s3_setup):
        """Test saving a simple file to S3."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT
        filename = "test.txt"
        url, metadata = s3_storage_provider.save(
            content, filename, "testuser", "testdata", content_type="text/plain"
        )
        assert url is not None
        assert isinstance(url, str)
        assert url.startswith("s3://")
        assert metadata is not None
        assert isinstance(metadata, StorageMetadata)
        assert metadata.object_id is not None
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        assert "Contents" in response
        assert len(response["Contents"]) == 1
        s3_key = response["Contents"][0]["Key"]
        assert metadata.object_id in s3_key

    def test_save_with_who_and_what(self, s3_storage_provider, mock_s3_setup):
        """Test saving with who and what parameters."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.get_json_bytes()
        filename = "data.json"
        url, metadata = s3_storage_provider.save(
            content, filename, "alice", "test_data", content_type="application/json"
        )
        assert "alice" in url
        assert "test_data" in url
        assert metadata.who == "alice"
        assert metadata.what == "test_data"
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="alice/")
        assert "Contents" in response
        assert len(response["Contents"]) == 1

    def test_save_different_content_types(self, s3_storage_provider, content_type):
        """Test saving files with different content types."""
        content, filename, mime_type = create_test_file_data(content_type)
        url, metadata = s3_storage_provider.save(
            content, filename, "testuser", "testdata", content_type=mime_type
        )
        assert url is not None
        assert metadata is not None
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == content
        assert metadata_loaded.content_type == mime_type

    def test_save_binary_content(self, s3_storage_provider):
        """Test saving binary content."""
        content = TestContent.FAKE_PNG
        filename = "image.png"
        url, metadata = s3_storage_provider.save(
            content, filename, "testuser", "testdata", content_type="image/png"
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == content
        assert verify_file_content(content_loaded, "png")

    def test_save_metadata_structure(self, s3_storage_provider, mock_s3_setup):
        """Test that saved metadata has correct structure."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT
        filename = "test.txt"
        url, metadata = s3_storage_provider.save(
            content,
            filename,
            "bob",
            "documentation",
            content_type="text/plain",
            source_url="https://example.com/test.txt",
        )
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="bob/")
        s3_key = response["Contents"][0]["Key"]
        obj_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        s3_metadata = obj_response["Metadata"]
        assert s3_metadata["object_id"] == metadata.object_id
        assert s3_metadata["original_filename"] == filename
        assert s3_metadata["source_url"] == "https://example.com/test.txt"
        assert s3_metadata["who"] == "bob"
        assert s3_metadata["what"] == "documentation"
        assert obj_response["ContentType"] == "text/plain"

    def test_save_without_filename(self, s3_storage_provider):
        """Test saving without providing filename."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = s3_storage_provider.save(
            content, None, "testuser", "testdata", content_type="text/plain"
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert metadata_loaded.original_filename == "unknown"

    def test_save_filename_without_extension(self, s3_storage_provider, mock_s3_setup):
        """Test saving with filename that has no extension."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT
        url, metadata = s3_storage_provider.save(
            content, "testfile", "testuser", "testdata", content_type="text/plain"
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert metadata_loaded.original_filename == "testfile"
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        s3_key = response["Contents"][0]["Key"]
        # Should use extension from content_type (text/plain -> .txt)
        assert s3_key.endswith(".txt")

    @pytest.mark.error_handling
    def test_save_with_s3_error(self):
        """Test saving when S3 operation fails."""
        with mock_aws():
            provider = S3StorageProvider(bucket_name="non-existent-bucket")
            with pytest.raises(Exception):
                provider.save(
                    TestContent.SIMPLE_TEXT,
                    "test.txt",
                    "testuser",
                    "testdata",
                    content_type="text/plain",
                )


@pytest.mark.s3
class TestS3StorageProviderLoad:
    """Test S3StorageProvider load functionality."""

    def test_load_saved_file(
        self, s3_storage_provider, sample_content, sample_metadata
    ):
        """Test loading a previously saved file."""
        url, metadata = s3_storage_provider.save(
            sample_content["content"],
            sample_content["filename"],
            "testuser",
            "testdata",
            content_type=sample_content["mime_type"],
            **sample_metadata,
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == sample_content["content"]
        assert verify_metadata_structure(metadata_loaded)

    def test_load_different_content_types(self, s3_storage_provider, test_scenario):
        """Test loading files with different content types."""
        url, metadata = s3_storage_provider.save(
            test_scenario["content"],
            test_scenario["filename"],
            "testuser",
            "testdata",
            content_type=test_scenario["mime_type"],
            **test_scenario["metadata"],
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == test_scenario["content"]
        assert metadata_loaded.content_type == test_scenario["mime_type"]
        assert verify_file_content(content_loaded, test_scenario["content_type"])

    def test_load_with_who_what_organization(self, s3_storage_provider):
        """Test loading files that are organized by who/what structure."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = s3_storage_provider.save(
            content, "test.txt", "alice", "documentation", content_type="text/plain"
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == content
        assert metadata_loaded.who == "alice"
        assert metadata_loaded.what == "documentation"

    def test_load_preserves_metadata(self, s3_storage_provider):
        """Test that load preserves all metadata fields."""
        content = TestContent.get_json_bytes()
        metadata = SampleMetadata.FULL.copy()
        url, save_metadata = s3_storage_provider.save(
            content,
            "data.json",
            "testuser",
            "testdata",
            content_type="application/json",
            **metadata,
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        for key, value in metadata.items():
            assert getattr(metadata_loaded, key) == value

    @pytest.mark.error_handling
    def test_load_nonexistent_url(self, s3_storage_provider):
        """Test loading with non-existent URL raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Object not found"):
            s3_storage_provider.load("s3://test-bucket/non/existent/path.txt")

    @pytest.mark.error_handling
    def test_load_with_empty_bucket(self):
        """Test loading from empty bucket."""
        with mock_aws():
            s3_client = boto3.client("s3", region_name="us-east-1")
            bucket_name = "empty-bucket"
            s3_client.create_bucket(Bucket=bucket_name)
            provider = S3StorageProvider(bucket_name=bucket_name)
            with pytest.raises(FileNotFoundError, match="Object not found"):
                provider.load(f"s3://{bucket_name}/any/object/id.txt")

    @pytest.mark.error_handling
    def test_load_with_s3_error(self):
        """Test loading when S3 operation fails."""
        provider = S3StorageProvider(bucket_name="test-bucket")
        with patch.object(provider, "s3_client") as mock_client:
            mock_client.get_object.side_effect = ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
                "GetObject",
            )
            with pytest.raises(Exception, match="Failed to get S3 object"):
                provider.load("s3://test-bucket/any/object/id.txt")

    @pytest.mark.error_handling
    def test_load_by_parts_convenience_method(self, s3_storage_provider):
        """Test the load_by_parts convenience method."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = s3_storage_provider.save(
            content, "test.txt", "user", "data", content_type="text/plain"
        )
        content_loaded, metadata_loaded = s3_storage_provider.load_by_parts(
            "user", "data", metadata.object_id
        )
        assert content_loaded == content


@pytest.mark.s3
@pytest.mark.integration
class TestS3StorageProviderIntegration:
    """Integration tests for S3StorageProvider."""

    def test_save_load_roundtrip(self, s3_storage_provider):
        """Test complete save/load roundtrip."""
        content = TestContent.get_json_bytes()
        filename = "roundtrip.json"
        url, metadata = s3_storage_provider.save(
            content,
            filename,
            "integration_test",
            "roundtrip_data",
            content_type="application/json",
            source_url="https://api.example.com/data",
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == content
        assert metadata_loaded.original_filename == filename
        assert metadata_loaded.content_type == "application/json"
        assert metadata_loaded.source_url == "https://api.example.com/data"
        assert metadata_loaded.who == "integration_test"
        assert metadata_loaded.what == "roundtrip_data"
        assert metadata_loaded.object_id == metadata.object_id

    def test_concurrent_saves(self, s3_storage_provider):
        """Test that concurrent saves don't interfere with each other."""
        contents = [
            (TestContent.SIMPLE_TEXT, "file1.txt", "text/plain"),
            (TestContent.get_json_bytes(), "file2.json", "application/json"),
            (TestContent.XML_DATA, "file3.xml", "application/xml"),
        ]
        urls = []
        for i, (content, filename, content_type) in enumerate(contents):
            url, metadata = s3_storage_provider.save(
                content,
                filename,
                f"user_{i}",
                f"test_data_{i}",
                content_type=content_type,
            )
            urls.append(url)
        for i, url in enumerate(urls):
            content_loaded, metadata_loaded = s3_storage_provider.load(url)
            assert content_loaded == contents[i][0]
            assert metadata_loaded.who == f"user_{i}"
            assert metadata_loaded.what == f"test_data_{i}"

    def test_large_file_handling(self, s3_storage_provider):
        """Test handling of larger files."""
        large_content = b"x" * (1024 * 1024)
        filename = "large_file.bin"
        url, metadata = s3_storage_provider.save(
            large_content,
            filename,
            "testuser",
            "testdata",
            content_type="application/octet-stream",
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert content_loaded == large_content
        assert len(content_loaded) == 1024 * 1024

    def test_s3_key_structure(self, s3_storage_provider, mock_s3_setup):
        """Test that S3 keys follow the expected structure."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT
        url, metadata = s3_storage_provider.save(
            content, "test.txt", "user", "data", content_type="text/plain"
        )
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="user/")
        s3_key = response["Contents"][0]["Key"]
        assert "user/data/" in s3_key
        assert metadata.object_id in s3_key
        assert s3_key.endswith(".txt")

    def test_metadata_case_sensitivity(self, s3_storage_provider):
        """Test that S3 metadata handling preserves case correctly."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = s3_storage_provider.save(
            content, "test.txt", "TestUser", "TestData", content_type="text/plain"
        )
        content_loaded, metadata_loaded = s3_storage_provider.load(url)
        assert metadata_loaded.who == "TestUser"
        assert metadata_loaded.what == "TestData"

    @respx.mock
    def test_s3_presigned_url_with_http_provider(
        self, s3_storage_provider, mock_s3_setup
    ):
        """Test loading S3 object via presigned URL using HTTP provider."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.get_json_bytes()
        filename = "presigned_test.json"
        s3_url, s3_metadata = s3_storage_provider.save(
            content,
            filename,
            "test_user",
            "presigned_data",
            content_type="application/json",
        )
        s3_key = s3_url.split(f"s3://{bucket_name}/", 1)[1]
        presigned_url = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket_name, "Key": s3_key}, ExpiresIn=3600
        )
        respx.get(presigned_url).mock(
            return_value=respx.MockResponse(
                200,
                content=content,
                headers={
                    "content-type": "application/json",
                    "content-length": str(len(content)),
                    "etag": '"test-etag"',
                    "last-modified": "Wed, 21 Oct 2023 07:28:00 GMT",
                    "server": "AmazonS3",
                    "x-amz-request-id": "test-request-id",
                },
            )
        )
        http_provider = HTTPStorageProvider()
        http_content, http_metadata = http_provider.load(presigned_url)
        assert http_content == content
        assert http_metadata.provider == "http"
        assert http_metadata.status_code == 200
        assert http_metadata.content_type == "application/json"
        assert http_metadata.content_length == len(content)
        headers = http_metadata.headers
        assert headers["etag"] == '"test-etag"'
        assert headers["server"] == "AmazonS3"
        assert "x-amz-request-id" in headers
        assert http_metadata.url == presigned_url

    def test_s3_presigned_url_binary_content(self, s3_storage_provider, mock_s3_setup):
        """Test presigned URL integration with binary content."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.FAKE_PNG
        filename = "test_image.png"
        s3_url, s3_metadata = s3_storage_provider.save(
            content, filename, "testuser", "testdata", content_type="image/png"
        )
        s3_key = s3_url.split(f"s3://{bucket_name}/", 1)[1]
        presigned_url = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket_name, "Key": s3_key}, ExpiresIn=3600
        )
        with respx.mock:
            respx.get(presigned_url).mock(
                return_value=respx.MockResponse(
                    200,
                    content=content,
                    headers={
                        "content-type": "image/png",
                        "content-length": str(len(content)),
                        "server": "AmazonS3",
                    },
                )
            )
            http_provider = HTTPStorageProvider()
            http_content, http_metadata = http_provider.load(presigned_url)
            assert http_content == content
            assert http_metadata.content_type == "image/png"
            assert http_metadata.content_length == len(content)
