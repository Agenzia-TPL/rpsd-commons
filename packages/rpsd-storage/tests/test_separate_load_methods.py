"""
Test file specifically for the new load_content and load_metadata methods.
"""

import json
import tempfile
from unittest.mock import Mock, patch

import pytest
import respx
from httpx import Response
from src.rpsd_storage.fs import FSStorageProvider
from src.rpsd_storage.http import HTTPStorageProvider
from src.rpsd_storage.provider import StorageProvider
from src.rpsd_storage.s3 import S3StorageProvider


class TestSeparateLoadMethods:
    """Test the new load_content and load_metadata methods across all providers."""

    def test_fs_load_content_only(self):
        """Test FSStorageProvider load_content method returns only content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save test content
            test_content = b"This is test content for load_content method"
            url, metadata = provider.save(
                test_content, "test.txt", who="testuser", what="testdata"
            )

            # Load only content
            loaded_content = provider.load_content(url)

            # Verify content matches
            assert loaded_content == test_content
            assert isinstance(loaded_content, bytes)

    def test_fs_load_metadata_only(self):
        """Test FSStorageProvider load_metadata method returns only metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save test content
            test_content = b"This is test content for load_metadata method"
            url, original_metadata = provider.save(
                test_content,
                "test.txt",
                content_type="text/plain",
                who="testuser",
                what="testdata",
                custom_metadata={"key": "value"},
            )

            # Load only metadata
            loaded_metadata = provider.load_metadata(url)

            # Verify metadata structure and content
            assert isinstance(loaded_metadata, dict)
            assert loaded_metadata["object_id"] == original_metadata["object_id"]
            assert loaded_metadata["original_filename"] == "test.txt"
            assert loaded_metadata["content_type"] == "text/plain"
            assert loaded_metadata["who"] == "testuser"
            assert loaded_metadata["what"] == "testdata"
            assert loaded_metadata["custom_metadata"] == {"key": "value"}

    def test_fs_load_by_parts_methods(self):
        """Test FSStorageProvider load_content_by_parts and load_metadata_by_parts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save test content
            test_content = b"Test content for by_parts methods"
            url, metadata = provider.save(
                test_content, "test.txt", who="testuser", what="testdata"
            )

            # Load using by_parts methods
            content_by_parts = provider.load_content_by_parts(
                "testuser", "testdata", metadata["object_id"]
            )
            metadata_by_parts = provider.load_metadata_by_parts(
                "testuser", "testdata", metadata["object_id"]
            )

            # Verify content and metadata
            assert content_by_parts == test_content
            assert metadata_by_parts["object_id"] == metadata["object_id"]

    @patch("boto3.client")
    def test_s3_load_content_only(self, mock_boto_client):
        """Test S3StorageProvider load_content method returns only content."""
        # Mock S3 client
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        # Mock S3 response
        test_content = b"S3 test content for load_content"
        mock_response = {"Body": Mock(), "ContentType": "text/plain"}
        mock_response["Body"].read.return_value = test_content
        mock_s3.get_object.return_value = mock_response

        provider = S3StorageProvider("test-bucket")
        url = "s3://test-bucket/testuser/testdata/test-object.txt"

        # Load only content
        loaded_content = provider.load_content(url)

        # Verify content
        assert loaded_content == test_content
        assert isinstance(loaded_content, bytes)

        # Verify S3 get_object was called correctly
        mock_s3.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="testuser/testdata/test-object.txt"
        )

    @patch("boto3.client")
    def test_s3_load_metadata_only(self, mock_boto_client):
        """Test S3StorageProvider load_metadata method uses head_object efficiently."""
        # Mock S3 client
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        # Mock S3 head_object response (more efficient than get_object)
        mock_response = {
            "ContentType": "text/plain",
            "Metadata": {
                "object_id": "test-object-id",
                "original_filename": "test.txt",
                "ingestion_timestamp": "20240101_120000",
                "who": "testuser",
                "what": "testdata",
                "custom_metadata": json.dumps({"key": "value"}),
            },
        }
        mock_s3.head_object.return_value = mock_response

        provider = S3StorageProvider("test-bucket")
        url = "s3://test-bucket/testuser/testdata/test-object.txt"

        # Load only metadata
        loaded_metadata = provider.load_metadata(url)

        # Verify metadata structure
        assert isinstance(loaded_metadata, dict)
        assert loaded_metadata["object_id"] == "test-object-id"
        assert loaded_metadata["original_filename"] == "test.txt"
        assert loaded_metadata["content_type"] == "text/plain"
        assert loaded_metadata["who"] == "testuser"
        assert loaded_metadata["what"] == "testdata"
        assert loaded_metadata["custom_metadata"] == {"key": "value"}

        # Verify head_object was used (not get_object for efficiency)
        mock_s3.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="testuser/testdata/test-object.txt"
        )
        mock_s3.get_object.assert_not_called()

    @respx.mock
    def test_http_load_content_only(self):
        """Test HTTPStorageProvider load_content method returns only content."""
        test_url = "https://example.com/test-file.txt"
        test_content = b"HTTP test content for load_content"

        # Mock HTTP GET response
        respx.get(test_url).mock(
            return_value=Response(
                200, content=test_content, headers={"content-type": "text/plain"}
            )
        )

        provider = HTTPStorageProvider()

        # Load only content
        loaded_content = provider.load_content(test_url)

        # Verify content
        assert loaded_content == test_content
        assert isinstance(loaded_content, bytes)

    @respx.mock
    def test_http_load_metadata_only(self):
        """Test HTTPStorageProvider load_metadata method uses HEAD efficiently."""
        test_url = "https://example.com/test-file.txt"

        # Mock HTTP HEAD response (more efficient than GET)
        respx.head(test_url).mock(
            return_value=Response(
                200,
                headers={
                    "content-type": "text/plain",
                    "content-length": "100",
                    "content-encoding": "gzip",
                    "last-modified": "Wed, 21 Oct 2015 07:28:00 GMT",
                },
            )
        )

        provider = HTTPStorageProvider()

        # Load only metadata
        loaded_metadata = provider.load_metadata(test_url)

        # Verify metadata structure
        assert isinstance(loaded_metadata, dict)
        assert loaded_metadata["url"] == test_url
        assert loaded_metadata["status_code"] == 200
        assert loaded_metadata["content_type"] == "text/plain"
        assert loaded_metadata["content_length"] == 100
        assert loaded_metadata["content_encoding"] == "gzip"
        assert loaded_metadata["provider"] == "http"
        assert "headers" in loaded_metadata

    def test_static_load_content_from_url_s3(self):
        """Test static load_content_from_url method with S3 URL."""
        with patch("boto3.client") as mock_boto_client:
            # Mock S3 client
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3

            test_content = b"Static method test content"
            mock_response = {"Body": Mock(), "ContentType": "text/plain"}
            mock_response["Body"].read.return_value = test_content
            mock_s3.get_object.return_value = mock_response

            url = "s3://test-bucket/path/to/object.txt"

            # Use static method
            loaded_content = StorageProvider.load_content_from_url(url)

            # Verify content
            assert loaded_content == test_content

    def test_static_load_metadata_from_url_fs(self):
        """Test static load_metadata_from_url method with file URL."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file and metadata
            provider = FSStorageProvider(temp_dir)
            test_content = b"Static metadata test"
            url, original_metadata = provider.save(test_content, "test.txt")

            # Use static method
            loaded_metadata = StorageProvider.load_metadata_from_url(url)

            # Verify metadata
            assert isinstance(loaded_metadata, dict)
            assert loaded_metadata["object_id"] == original_metadata["object_id"]

    @respx.mock
    def test_static_load_content_from_url_http(self):
        """Test static load_content_from_url method with HTTP URL."""
        test_url = "https://example.com/static-test.txt"
        test_content = b"Static HTTP test content"

        respx.get(test_url).mock(return_value=Response(200, content=test_content))

        # Use static method
        loaded_content = StorageProvider.load_content_from_url(test_url)

        # Verify content
        assert loaded_content == test_content

    def test_error_handling_consistency(self):
        """Test that error handling is consistent across all methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            non_existent_url = "file:///non/existent/path.txt"

            # All methods should raise FileNotFoundError for non-existent files
            with pytest.raises(FileNotFoundError):
                provider.load(non_existent_url)

            with pytest.raises(FileNotFoundError):
                provider.load_content(non_existent_url)

            with pytest.raises(FileNotFoundError):
                provider.load_metadata(non_existent_url)

    def test_performance_comparison(self):
        """Demonstrate performance difference between load and separate methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save a test file
            large_content = b"x" * 10000  # 10KB of data
            url, metadata = provider.save(large_content, "large.txt")

            # When you only need content, load_content is more efficient
            # (doesn't read .meta file)
            content_only = provider.load_content(url)
            assert len(content_only) == 10000

            # When you only need metadata, load_metadata is more efficient
            # (doesn't read large content file)
            metadata_only = provider.load_metadata(url)
            assert "object_id" in metadata_only

            # Traditional load method reads both
            full_content, full_metadata = provider.load(url)
            assert len(full_content) == 10000
            assert "object_id" in full_metadata


class TestNewMethodsIntegration:
    """Integration tests showing real-world usage scenarios."""

    def test_metadata_inspection_workflow(self):
        """Test workflow where you inspect metadata before deciding to load content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save different types of files
            files = [
                (b"Small text", "small.txt", "text/plain"),
                (b"x" * 1000000, "large.bin", "application/octet-stream"),  # 1MB
                (b'{"key": "value"}', "data.json", "application/json"),
            ]

            urls = []
            for content, filename, content_type in files:
                url, _ = provider.save(content, filename, content_type=content_type)
                urls.append(url)

            # Workflow: Check metadata first, then load content based on criteria
            for url in urls:
                metadata = provider.load_metadata(url)

                # Only load content for small text files
                if metadata["content_type"] == "text/plain" and metadata[
                    "original_filename"
                ].endswith(".txt"):
                    content = provider.load_content(url)
                    assert content == b"Small text"

    def test_bulk_metadata_scanning(self):
        """Test scenario where you scan metadata of many files efficiently."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Create multiple files
            file_urls = []
            for i in range(5):
                content = f"File content {i}".encode()
                url, _ = provider.save(
                    content,
                    f"file_{i}.txt",
                    who="user",
                    what=f"dataset_{i % 2}",  # Alternate datasets
                )
                file_urls.append(url)

            # Efficiently scan metadata without loading content
            dataset_0_files = []
            for url in file_urls:
                metadata = provider.load_metadata(url)
                if metadata.get("what") == "dataset_0":
                    dataset_0_files.append(metadata["original_filename"])

            # Should find files 0, 2, 4
            assert len(dataset_0_files) == 3
            assert "file_0.txt" in dataset_0_files
            assert "file_2.txt" in dataset_0_files
            assert "file_4.txt" in dataset_0_files

    @respx.mock
    def test_http_head_vs_get_efficiency(self):
        """Demonstrate efficiency of HEAD vs GET for HTTP metadata."""
        test_url = "https://api.example.com/large-dataset.csv"

        # Mock HEAD request (efficient)
        respx.head(test_url).mock(
            return_value=Response(
                200,
                headers={
                    "content-type": "text/csv",
                    "content-length": "50000000",  # 50MB
                    "last-modified": "Wed, 21 Oct 2015 07:28:00 GMT",
                },
            )
        )

        # Mock GET request (inefficient for metadata-only)
        large_content = b"," * 1000  # Simulate large CSV
        respx.get(test_url).mock(
            return_value=Response(
                200,
                content=large_content,
                headers={
                    "content-type": "text/csv",
                    "content-length": str(len(large_content)),
                },
            )
        )

        provider = HTTPStorageProvider()

        # Efficient: Use load_metadata (HEAD request)
        metadata = provider.load_metadata(test_url)
        assert metadata["content_length"] == 50000000
        assert metadata["content_type"] == "text/csv"

        # Less efficient: Use load for metadata only (GET request)
        content, metadata_from_load = provider.load(test_url)
        assert len(content) == 1000  # Downloaded content unnecessarily
