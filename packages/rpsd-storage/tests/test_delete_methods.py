# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Test file for the new delete methods.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from rpsd_storage.providers.base import StorageProvider
from rpsd_storage.providers.fs import FSStorageProvider
from rpsd_storage.providers.http import HTTPStorageProvider
from rpsd_storage.providers.s3 import S3StorageProvider


class TestDeleteMethods:
    """Test the new delete methods across all providers."""

    def test_fs_delete_success(self):
        """Test FSStorageProvider delete method successfully removes files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            test_content = b"Test content to be deleted"
            url, metadata = provider.save(
                test_content, "test_delete.txt", who="testuser", what="testdata"
            )
            file_path = url.replace("file://", "")
            meta_path = f"{file_path}.meta"
            assert os.path.exists(file_path)
            assert os.path.exists(meta_path)
            provider.delete(url)
            assert not os.path.exists(file_path)
            assert not os.path.exists(meta_path)

    def test_fs_delete_nonexistent_file(self):
        """Test FSStorageProvider delete raises FileNotFoundError for nonexistent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            fake_url = f"file://{temp_dir}/nonexistent.txt"
            with pytest.raises(FileNotFoundError, match="Content file not found"):
                provider.delete(fake_url)

    def test_fs_delete_metadata_file_missing(self):
        """Test FSStorageProvider delete when metadata file is missing (should work)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            test_content = b"Test content"
            url, _ = provider.save(test_content, "test.txt", "testuser", "testdata")
            file_path = url.replace("file://", "")
            meta_path = f"{file_path}.meta"
            os.remove(meta_path)
            provider.delete(url)
            assert not os.path.exists(file_path)

    def test_fs_delete_invalid_url_scheme(self):
        """Test FSStorageProvider delete method with invalid URL scheme."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            with pytest.raises(ValueError, match="Invalid URL scheme"):
                provider.delete("http://example.com/file.txt")

    @patch("boto3.client")
    def test_s3_delete_success(self, mock_boto_client):
        """Test S3StorageProvider delete method calls delete_object correctly."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        provider = S3StorageProvider("test-bucket")
        url = "s3://test-bucket/testuser/testdata/test-object.txt"
        provider.delete(url)
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="testuser/testdata/test-object.txt"
        )

    @patch("boto3.client")
    def test_s3_delete_nonexistent_object(self, mock_boto_client):
        """Test S3StorageProvider delete method handles S3 errors correctly."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            }
        }
        mock_s3.delete_object.side_effect = ClientError(error_response, "DeleteObject")
        provider = S3StorageProvider("test-bucket")
        url = "s3://test-bucket/nonexistent/object.txt"
        with pytest.raises(FileNotFoundError, match="Object not found"):
            provider.delete(url)

    @patch("boto3.client")
    def test_s3_delete_invalid_bucket(self, mock_boto_client):
        """Test S3StorageProvider delete method with mismatched bucket."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        provider = S3StorageProvider("test-bucket")
        url = "s3://different-bucket/path/object.txt"
        with pytest.raises(
            ValueError, match="URL bucket different-bucket doesn't match"
        ):
            provider.delete(url)

    @patch("boto3.client")
    def test_s3_delete_invalid_url_scheme(self, mock_boto_client):
        """Test S3StorageProvider delete method with invalid URL scheme."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        provider = S3StorageProvider("test-bucket")
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            provider.delete("file:///path/to/file.txt")

    def test_http_delete_not_implemented(self):
        """Test HTTPStorageProvider delete method raises NotImplementedError."""
        provider = HTTPStorageProvider()
        with pytest.raises(
            NotImplementedError,
            match="HTTP provider delete\\(\\) method is not yet implemented",
        ):
            provider.delete("https://example.com/file.txt")

    def test_http_delete_invalid_url_scheme(self):
        """Test HTTPStorageProvider delete validates URL scheme before raising error."""
        provider = HTTPStorageProvider()
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            provider.delete("ftp://example.com/file.txt")

    def test_static_delete_from_url_s3(self):
        """Test static delete_from_url method with S3 URL."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            url = "s3://test-bucket/path/to/object.txt"
            StorageProvider.delete_from_url(url)
            mock_s3.delete_object.assert_called_once_with(
                Bucket="test-bucket", Key="path/to/object.txt"
            )

    def test_static_delete_from_url_fs(self):
        """Test static delete_from_url method with file URL."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_static_delete.txt")
            meta_path = f"{file_path}.meta"
            with open(file_path, "wb") as f:
                f.write(b"test content")
            with open(meta_path, "w") as f:
                f.write('{"object_id": "test"}')
            url = f"file://{file_path}"
            assert os.path.exists(file_path)
            assert os.path.exists(meta_path)
            StorageProvider.delete_from_url(url)
            assert not os.path.exists(file_path)
            assert not os.path.exists(meta_path)

    def test_static_delete_from_url_http(self):
        """Test static delete_from_url method with HTTP URL (raises error)."""
        url = "https://example.com/file.txt"
        with pytest.raises(
            NotImplementedError,
            match="HTTP provider delete\\(\\) method is not yet implemented",
        ):
            StorageProvider.delete_from_url(url)

    def test_static_delete_from_url_unsupported_scheme(self):
        """Test static delete_from_url method with unsupported URL scheme."""
        url = "ftp://example.com/file.txt"
        with pytest.raises(ValueError, match="Unsupported URL scheme: ftp"):
            StorageProvider.delete_from_url(url)


class TestDeleteIntegration:
    """Integration tests for delete functionality."""

    def test_fs_save_delete_cycle(self):
        """Test complete save-load-delete cycle with FSStorageProvider."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            files_data = [
                (b"File 1 content", "file1.txt"),
                (b"File 2 content", "file2.txt"),
                (b"File 3 content", "file3.txt"),
            ]
            urls = []
            for content, filename in files_data:
                url, _ = provider.save(content, filename, who="user", what="test")
                urls.append(url)
            for url in urls:
                loaded_content, loaded_metadata = provider.load(url)
                assert loaded_content in [
                    b"File 1 content",
                    b"File 2 content",
                    b"File 3 content",
                ]
            provider.delete(urls[1])
            provider.load(urls[0])
            provider.load(urls[2])
            with pytest.raises(FileNotFoundError):
                provider.load(urls[1])
            provider.delete(urls[0])
            provider.delete(urls[2])
            for url in [urls[0], urls[2]]:
                with pytest.raises(FileNotFoundError):
                    provider.load(url)

    @patch("boto3.client")
    def test_s3_save_delete_cycle(self, mock_boto_client):
        """Test save-delete cycle with S3StorageProvider (mocked)."""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        mock_s3.put_object.return_value = None
        provider = S3StorageProvider("test-bucket")
        test_content = b"Test content for deletion"
        url, metadata = provider.save(
            test_content, "test_delete.txt", "testuser", "testdata"
        )
        assert mock_s3.put_object.called
        provider.delete(url)
        expected_key = f"testuser/testdata/{metadata.object_id}"
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key=expected_key
        )

    def test_delete_after_load_operations(self):
        """Test that delete works after various load operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            test_content = b"Content for load operations test"
            url, metadata = provider.save(
                test_content, "load_test.txt", "testuser", "testdata"
            )
            loaded_content, loaded_metadata = provider.load(url)
            content_only = provider.load_content(url)
            metadata_only = provider.load_metadata(url)
            assert loaded_content == test_content
            assert content_only == test_content
            assert metadata_only.object_id == metadata.object_id
            provider.delete(url)
            file_path = url.replace("file://", "")
            assert not os.path.exists(file_path)

    def test_delete_error_handling_consistency(self):
        """Test that delete error handling is consistent across providers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            fs_provider = FSStorageProvider(temp_dir)
            http_provider = HTTPStorageProvider()
            fake_fs_url = f"file://{temp_dir}/nonexistent.txt"
            fake_http_url = "https://example.com/nonexistent.txt"
            with pytest.raises(FileNotFoundError):
                fs_provider.delete(fake_fs_url)
            with pytest.raises(NotImplementedError):
                http_provider.delete(fake_http_url)
            with pytest.raises(ValueError):
                fs_provider.delete("invalid://scheme/file.txt")
            with pytest.raises(ValueError):
                http_provider.delete("invalid://scheme/file.txt")
