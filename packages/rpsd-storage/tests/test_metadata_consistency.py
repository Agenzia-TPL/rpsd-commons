"""
Tests for metadata consistency between storage providers.
"""

import hashlib

import pytest

from .test_utils import TestContent


@pytest.mark.fs
def test_fs_metadata_consistency(fs_storage_provider):
    """
    Tests that content_length and hash are consistent between save and load
    for the FSStorageProvider.
    """
    content = TestContent.SIMPLE_TEXT
    filename = "test.txt"

    url, save_metadata = fs_storage_provider.save(
        content, filename, "testuser", "testdata"
    )
    loaded_content, loaded_metadata = fs_storage_provider.load(url)

    assert loaded_content == content
    assert "content_length" in save_metadata
    assert "hash" in save_metadata
    assert "content_length" in loaded_metadata
    assert "hash" in loaded_metadata

    expected_content_length = len(content)
    expected_hash = hashlib.md5(content).hexdigest()

    assert save_metadata["content_length"] == expected_content_length
    assert loaded_metadata["content_length"] == expected_content_length
    assert save_metadata["hash"] == expected_hash
    assert loaded_metadata["hash"] == expected_hash


@pytest.mark.s3
def test_s3_metadata_consistency(s3_storage_provider):
    """
    Tests that content_length and hash are consistent between save and load
    for the S3StorageProvider.
    """
    content = TestContent.SIMPLE_TEXT
    filename = "test.txt"

    url, save_metadata = s3_storage_provider.save(
        content, filename, "testuser", "testdata"
    )
    loaded_content, loaded_metadata = s3_storage_provider.load(url)

    assert loaded_content == content
    assert "content_length" in save_metadata
    assert "hash" in save_metadata
    assert "content_length" in loaded_metadata
    assert "hash" in loaded_metadata

    expected_content_length = len(content)
    expected_hash = hashlib.md5(content).hexdigest()

    assert save_metadata["content_length"] == expected_content_length
    assert loaded_metadata["content_length"] == expected_content_length
    assert save_metadata["hash"] == expected_hash
    assert loaded_metadata["hash"] == expected_hash


@pytest.mark.integration
def test_cross_provider_metadata_consistency(fs_storage_provider, s3_storage_provider):
    """
    Tests that the same content saved to FS and S3 providers has the same
    content_length and hash.
    """
    content = TestContent.SIMPLE_TEXT
    filename = "test.txt"

    # Save to FS
    fs_url, fs_save_metadata = fs_storage_provider.save(
        content, filename, "testuser", "testdata"
    )
    fs_loaded_content, fs_loaded_metadata = fs_storage_provider.load(fs_url)

    # Save to S3
    s3_url, s3_save_metadata = s3_storage_provider.save(
        content, filename, "testuser", "testdata"
    )
    s3_loaded_content, s3_loaded_metadata = s3_storage_provider.load(s3_url)

    # Verify content is the same
    assert fs_loaded_content == s3_loaded_content

    # Verify metadata fields are consistent
    assert fs_save_metadata["content_length"] == s3_save_metadata["content_length"]
    assert fs_loaded_metadata["content_length"] == s3_loaded_metadata["content_length"]
    assert fs_save_metadata["hash"] == s3_save_metadata["hash"]
    assert fs_loaded_metadata["hash"] == s3_loaded_metadata["hash"]
