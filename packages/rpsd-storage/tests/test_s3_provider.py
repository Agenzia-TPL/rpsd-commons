"""
Tests for S3StorageProvider.
"""

import uuid
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from rpsd_storage.s3 import S3StorageProvider

from .test_utils import (
    SampleMetadata,
    TestContent,
    create_test_file_data,
    verify_file_content,
    verify_metadata_structure,
)


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

        object_id = s3_storage_provider.save(
            content=content, filename=filename, content_type="text/plain"
        )

        assert object_id is not None
        assert isinstance(object_id, str)

        # Verify object exists in S3
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ingested/")
        assert "Contents" in response
        assert len(response["Contents"]) == 1

        # Verify the object key contains the object_id
        s3_key = response["Contents"][0]["Key"]
        assert object_id in s3_key
        assert s3_key.startswith("ingested/")

    def test_save_with_who_and_what(self, s3_storage_provider, mock_s3_setup):
        """Test saving with who and what parameters."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.get_json_bytes()
        filename = "data.json"

        object_id = s3_storage_provider.save(
            content=content,
            filename=filename,
            content_type="application/json",
            who="alice",
            what="test_data",
        )

        # Object ID should contain the who and what prefixes
        assert "alice" in object_id
        assert "test_data" in object_id

        # Verify object exists
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ingested/")
        assert "Contents" in response
        assert len(response["Contents"]) == 1

    def test_save_different_content_types(self, s3_storage_provider, content_type):
        """Test saving files with different content types."""
        content, filename, mime_type = create_test_file_data(content_type)

        object_id = s3_storage_provider.save(
            content=content, filename=filename, content_type=mime_type
        )

        assert object_id is not None

        # Verify content is correctly saved
        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["content"] == content
        assert loaded_data["metadata"]["content_type"] == mime_type

    def test_save_binary_content(self, s3_storage_provider):
        """Test saving binary content."""
        content = TestContent.FAKE_PNG
        filename = "image.png"

        object_id = s3_storage_provider.save(
            content=content, filename=filename, content_type="image/png"
        )

        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["content"] == content
        assert verify_file_content(loaded_data["content"], "png")

    def test_save_metadata_structure(self, s3_storage_provider, mock_s3_setup):
        """Test that saved metadata has correct structure."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT
        filename = "test.txt"

        object_id = s3_storage_provider.save(
            content=content,
            filename=filename,
            content_type="text/plain",
            source_url="https://example.com/test.txt",
            who="bob",
            what="documentation",
        )

        # Get the S3 object and check metadata
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ingested/")
        s3_key = response["Contents"][0]["Key"]

        obj_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        s3_metadata = obj_response["Metadata"]

        assert s3_metadata["object_id"] == object_id
        assert s3_metadata["original_filename"] == filename
        assert s3_metadata["source_url"] == "https://example.com/test.txt"
        assert s3_metadata["who"] == "bob"
        assert s3_metadata["what"] == "documentation"
        assert obj_response["ContentType"] == "text/plain"

    def test_save_without_filename(self, s3_storage_provider):
        """Test saving without providing filename."""
        content = TestContent.SIMPLE_TEXT

        object_id = s3_storage_provider.save(
            content=content, filename=None, content_type="text/plain"
        )

        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["metadata"]["original_filename"] == "unknown"

    def test_save_filename_without_extension(self, s3_storage_provider, mock_s3_setup):
        """Test saving with filename that has no extension."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT

        object_id = s3_storage_provider.save(
            content=content, filename="testfile", content_type="text/plain"
        )

        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["metadata"]["original_filename"] == "testfile"

        # Should default to .xml extension in S3 key
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ingested/")
        s3_key = response["Contents"][0]["Key"]
        assert s3_key.endswith(".xml")

    @pytest.mark.error_handling
    def test_save_with_s3_error(self):
        """Test saving when S3 operation fails."""
        with mock_aws():
            # Create provider with non-existent bucket
            provider = S3StorageProvider(bucket_name="non-existent-bucket")

            with pytest.raises(Exception):
                provider.save(
                    content=TestContent.SIMPLE_TEXT,
                    filename="test.txt",
                    content_type="text/plain",
                )


@pytest.mark.s3
class TestS3StorageProviderLoad:
    """Test S3StorageProvider load functionality."""

    def test_load_saved_file(
        self, s3_storage_provider, sample_content, sample_metadata
    ):
        """Test loading a previously saved file."""
        # Save a file first
        object_id = s3_storage_provider.save(
            content=sample_content["content"],
            filename=sample_content["filename"],
            content_type=sample_content["mime_type"],
            **sample_metadata,
        )

        # Load the file
        loaded_data = s3_storage_provider.load(object_id)

        assert loaded_data["content"] == sample_content["content"]
        assert verify_metadata_structure(loaded_data["metadata"])

    def test_load_different_content_types(self, s3_storage_provider, test_scenario):
        """Test loading files with different content types."""
        # Save the file
        object_id = s3_storage_provider.save(
            content=test_scenario["content"],
            filename=test_scenario["filename"],
            content_type=test_scenario["mime_type"],
            **test_scenario["metadata"],
        )

        # Load and verify
        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["content"] == test_scenario["content"]
        assert loaded_data["metadata"]["content_type"] == test_scenario["mime_type"]
        assert verify_file_content(
            loaded_data["content"], test_scenario["content_type"]
        )

    def test_load_with_who_what_prefixes(self, s3_storage_provider):
        """Test loading files that have who/what prefixes in object_id."""
        content = TestContent.SIMPLE_TEXT

        # Save with who and what
        object_id = s3_storage_provider.save(
            content=content,
            filename="test.txt",
            content_type="text/plain",
            who="alice",
            what="documentation",
        )

        # Load using the object_id
        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["content"] == content
        assert loaded_data["metadata"]["who"] == "alice"
        assert loaded_data["metadata"]["what"] == "documentation"

    def test_load_preserves_metadata(self, s3_storage_provider):
        """Test that load preserves all metadata fields."""
        content = TestContent.get_json_bytes()

        metadata = SampleMetadata.FULL.copy()
        object_id = s3_storage_provider.save(
            content=content,
            filename="data.json",
            content_type="application/json",
            **metadata,
        )

        loaded_data = s3_storage_provider.load(object_id)
        loaded_metadata = loaded_data["metadata"]

        # Check all original metadata is preserved
        for key, value in metadata.items():
            assert loaded_metadata[key] == value

    @pytest.mark.error_handling
    def test_load_nonexistent_object_id(self, s3_storage_provider):
        """Test loading with non-existent object_id raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No objects found in bucket"):
            s3_storage_provider.load("non-existent-id")

    @pytest.mark.error_handling
    def test_load_with_empty_bucket(self):
        """Test loading from empty bucket."""
        with mock_aws():
            s3_client = boto3.client("s3", region_name="us-east-1")
            bucket_name = "empty-bucket"
            s3_client.create_bucket(Bucket=bucket_name)

            provider = S3StorageProvider(bucket_name=bucket_name)
            with pytest.raises(FileNotFoundError, match="No objects found in bucket"):
                provider.load("any-object-id")

    @pytest.mark.error_handling
    def test_load_with_s3_error(self):
        """Test loading when S3 operation fails."""
        # Test with a provider that has no actual S3 setup
        provider = S3StorageProvider(bucket_name="test-bucket")

        # Mock the S3 client to raise an exception
        with patch.object(provider, "s3_client") as mock_client:
            mock_client.list_objects_v2.side_effect = ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
                "ListObjectsV2",
            )

            with pytest.raises(Exception, match="Failed to list S3 objects"):
                provider.load("any-object-id")

    @pytest.mark.error_handling
    def test_load_with_prefix_matching(self, s3_storage_provider, mock_s3_setup):
        """Test loading works correctly with prefix matching."""
        s3_client, bucket_name = mock_s3_setup

        # Create objects with different prefixes to test matching logic
        base_id = str(uuid.uuid4())

        # Create an object with a prefix (as would be created by save() with who/what)
        prefixed_id = f"user-data-{base_id}"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=f"ingested/{prefixed_id}.txt",
            Body=b"content1",
            ContentType="text/plain",
            Metadata={"object_id": prefixed_id, "original_filename": "test1.txt"},
        )

        # Should be able to load using the full prefixed object_id
        loaded_data = s3_storage_provider.load(prefixed_id)
        assert loaded_data["content"] == b"content1"

        # Should also be able to load using just the base UUID part
        loaded_data = s3_storage_provider.load(base_id)
        assert loaded_data["content"] == b"content1"


@pytest.mark.s3
@pytest.mark.integration
class TestS3StorageProviderIntegration:
    """Integration tests for S3StorageProvider."""

    def test_save_load_roundtrip(self, s3_storage_provider):
        """Test complete save/load roundtrip."""
        content = TestContent.get_json_bytes()
        filename = "roundtrip.json"

        # Save
        object_id = s3_storage_provider.save(
            content=content,
            filename=filename,
            content_type="application/json",
            source_url="https://api.example.com/data",
            who="integration_test",
            what="roundtrip_data",
        )

        # Load
        loaded_data = s3_storage_provider.load(object_id)

        # Verify everything matches
        assert loaded_data["content"] == content
        metadata = loaded_data["metadata"]
        assert metadata["original_filename"] == filename
        assert metadata["content_type"] == "application/json"
        assert metadata["source_url"] == "https://api.example.com/data"
        assert metadata["who"] == "integration_test"
        assert metadata["what"] == "roundtrip_data"
        assert metadata["object_id"] == object_id

    def test_concurrent_saves(self, s3_storage_provider):
        """Test that concurrent saves don't interfere with each other."""
        contents = [
            (TestContent.SIMPLE_TEXT, "file1.txt", "text/plain"),
            (TestContent.get_json_bytes(), "file2.json", "application/json"),
            (TestContent.XML_DATA, "file3.xml", "application/xml"),
        ]

        object_ids = []
        for i, (content, filename, content_type) in enumerate(contents):
            object_id = s3_storage_provider.save(
                content=content,
                filename=filename,
                content_type=content_type,
                who=f"user_{i}",
                what=f"test_data_{i}",
            )
            object_ids.append(object_id)

        # All should be loadable independently
        for i, object_id in enumerate(object_ids):
            loaded_data = s3_storage_provider.load(object_id)
            assert loaded_data["content"] == contents[i][0]
            assert loaded_data["metadata"]["who"] == f"user_{i}"
            assert loaded_data["metadata"]["what"] == f"test_data_{i}"

    def test_large_file_handling(self, s3_storage_provider):
        """Test handling of larger files."""
        # Create a larger content (1MB)
        large_content = b"x" * (1024 * 1024)
        filename = "large_file.bin"

        object_id = s3_storage_provider.save(
            content=large_content,
            filename=filename,
            content_type="application/octet-stream",
        )

        loaded_data = s3_storage_provider.load(object_id)
        assert loaded_data["content"] == large_content
        assert len(loaded_data["content"]) == 1024 * 1024

    def test_s3_key_structure(self, s3_storage_provider, mock_s3_setup):
        """Test that S3 keys follow the expected structure."""
        s3_client, bucket_name = mock_s3_setup
        content = TestContent.SIMPLE_TEXT

        object_id = s3_storage_provider.save(
            content=content,
            filename="test.txt",
            content_type="text/plain",
            who="user",
            what="data",
        )

        # Check S3 key structure
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="ingested/")
        s3_key = response["Contents"][0]["Key"]

        assert s3_key.startswith("ingested/")
        assert object_id in s3_key
        assert s3_key.endswith(".txt")

    def test_metadata_case_sensitivity(self, s3_storage_provider):
        """Test that S3 metadata handling preserves case correctly."""
        content = TestContent.SIMPLE_TEXT

        object_id = s3_storage_provider.save(
            content=content,
            filename="test.txt",
            content_type="text/plain",
            who="TestUser",
            what="TestData",
        )

        loaded_data = s3_storage_provider.load(object_id)
        metadata = loaded_data["metadata"]

        # S3 metadata keys are lowercase, but values should preserve case
        assert metadata["who"] == "TestUser"
        assert metadata["what"] == "TestData"
