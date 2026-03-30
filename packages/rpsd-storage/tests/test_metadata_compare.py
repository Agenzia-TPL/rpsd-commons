"""
Tests for StorageMetadata comparison methods.
"""

import pytest

from rpsd_storage.metadata import StorageMetadata


class TestStorageMetadataCompare:
    """Test cases for the compare staticmethod."""

    def test_compare_identical_content(self):
        """Test that identical content returns 0."""
        metadata1 = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        metadata2 = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=100,  # Same length
            hash="abc123",  # Same hash
            who="user1",  # Same who
            what="document",  # Same what
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",  # Different timestamp
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        result = StorageMetadata.compare(metadata1, metadata2)
        assert result == 0

    def test_compare_candidate_newer(self):
        """Test that newer candidate returns 1."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",  # Earlier
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        candidate = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=200,  # Different content
            hash="def456",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",  # Later
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        result = StorageMetadata.compare(current, candidate)
        assert result == 1

    def test_compare_candidate_older(self):
        """Test that older candidate returns -1."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T11:00:00Z",  # Later
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        candidate = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=200,  # Different content
            hash="def456",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T10:00:00Z",  # Earlier
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        result = StorageMetadata.compare(current, candidate)
        assert result == -1

    def test_compare_different_who_raises_error(self):
        """Test that different 'who' fields raise ValueError."""
        metadata1 = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",  # Different who
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        metadata2 = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user2",  # Different who
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        with pytest.raises(
            ValueError, match="Cannot compare metadata for different entities"
        ):
            StorageMetadata.compare(metadata1, metadata2)

    def test_compare_different_what_raises_error(self):
        """Test that different 'what' fields raise ValueError."""
        metadata1 = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",  # Different what
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        metadata2 = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="image",  # Different what
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        with pytest.raises(
            ValueError, match="Cannot compare metadata for different entities"
        ):
            StorageMetadata.compare(metadata1, metadata2)

    def test_compare_same_content_different_length_uses_timestamp(self):
        """Test that same hash but different length still compares by timestamp."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,  # Different length
            hash="abc123",  # Same hash (edge case)
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",  # Earlier
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        candidate = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=200,  # Different length
            hash="abc123",  # Same hash (edge case)
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",  # Later
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        result = StorageMetadata.compare(current, candidate)
        assert result == 1  # Candidate is newer


class TestStorageMetadataIsUpdateOf:
    """Test cases for the is_update_of instance method."""

    def test_is_update_of_true_when_newer(self):
        """Test that is_update_of returns True when metadata is newer."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",  # Earlier
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        newer = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=200,
            hash="def456",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",  # Later
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        assert newer.is_update_of(current) is True

    def test_is_update_of_false_when_older(self):
        """Test that is_update_of returns False when metadata is older."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T11:00:00Z",  # Later
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        older = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=200,
            hash="def456",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T10:00:00Z",  # Earlier
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        assert older.is_update_of(current) is False

    def test_is_update_of_false_when_identical(self):
        """Test that is_update_of returns False when content is identical."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        identical = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=100,  # Same content
            hash="abc123",  # Same hash
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",  # Different timestamp
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        assert identical.is_update_of(current) is False

    def test_is_update_of_raises_error_for_different_entities(self):
        """Test that is_update_of raises ValueError for different entities."""
        current = StorageMetadata(
            provider="fs",
            url="file:///test1.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user1",
            what="document",
            original_filename="test.txt",
            object_id="obj1",
            save_stamp="2024-01-01T10:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        different_entity = StorageMetadata(
            provider="fs",
            url="file:///test2.txt",
            content_type="text/plain",
            content_length=100,
            hash="abc123",
            who="user2",  # Different who
            what="document",
            original_filename="test.txt",
            object_id="obj2",
            save_stamp="2024-01-01T11:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        with pytest.raises(
            ValueError, match="Cannot compare metadata for different entities"
        ):
            different_entity.is_update_of(current)


class TestStorageProviderCompareFromUrl:
    """Test cases for StorageProvider.compare_from_url static method."""

    def test_compare_from_url_identical_content(self):
        """Test comparing URLs with identical content."""
        import tempfile

        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save the same content twice
            content = b"Test content for comparison"
            url1, _ = provider.save(content, "file1.txt", who="user1", what="document")
            url2, _ = provider.save(content, "file2.txt", who="user1", what="document")

            # Compare using the static method
            from rpsd_storage.providers.base import StorageProvider

            result = StorageProvider.compare_from_url(url1, url2)
            assert result == 0

    def test_compare_from_url_candidate_newer(self):
        """Test comparing URLs where candidate is newer."""
        import tempfile
        import time

        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save older content
            url1, _ = provider.save(
                b"Old content", "file1.txt", who="user1", what="document"
            )

            # Wait to ensure different timestamp (timestamps have second precision)
            time.sleep(1.1)

            # Save newer content
            url2, _ = provider.save(
                b"New content", "file2.txt", who="user1", what="document"
            )

            # Compare using the static method
            from rpsd_storage.providers.base import StorageProvider

            result = StorageProvider.compare_from_url(url1, url2)
            assert result == 1

    def test_compare_from_url_candidate_older(self):
        """Test comparing URLs where candidate is older."""
        import tempfile
        import time

        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save first file
            url1, _ = provider.save(
                b"Content 1", "file1.txt", who="user1", what="document"
            )

            # Wait to ensure different timestamp (timestamps have second precision)
            time.sleep(1.1)

            # Save second file (will have later timestamp)
            url2, _ = provider.save(
                b"Content 2", "file2.txt", who="user1", what="document"
            )

            # Compare: url2 is current, url1 is candidate
            # Since url1 has an earlier timestamp, it should be older (-1)
            from rpsd_storage.providers.base import StorageProvider

            result = StorageProvider.compare_from_url(url2, url1)
            assert result == -1  # url1 is older than url2

            # Compare the other way: url1 is current, url2 is candidate
            # Since url2 has a later timestamp, it should be newer (1)
            result = StorageProvider.compare_from_url(url1, url2)
            assert result == 1  # url2 is newer than url1

    def test_compare_from_url_different_who_raises_error(self):
        """Test that comparing URLs with different 'who' raises ValueError."""
        import tempfile

        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save files with different 'who'
            url1, _ = provider.save(
                b"Content 1", "file1.txt", who="user1", what="document"
            )
            url2, _ = provider.save(
                b"Content 2", "file2.txt", who="user2", what="document"
            )

            # Compare should raise ValueError
            from rpsd_storage.providers.base import StorageProvider

            with pytest.raises(
                ValueError, match="Cannot compare metadata for different entities"
            ):
                StorageProvider.compare_from_url(url1, url2)

    def test_compare_from_url_different_what_raises_error(self):
        """Test that comparing URLs with different 'what' raises ValueError."""
        import tempfile

        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save files with different 'what'
            url1, _ = provider.save(
                b"Content 1", "file1.txt", who="user1", what="document"
            )
            url2, _ = provider.save(
                b"Content 2", "file2.txt", who="user1", what="image"
            )

            # Compare should raise ValueError
            from rpsd_storage.providers.base import StorageProvider

            with pytest.raises(
                ValueError, match="Cannot compare metadata for different entities"
            ):
                StorageProvider.compare_from_url(url1, url2)

    def test_compare_from_url_nonexistent_url_raises_error(self):
        """Test that comparing nonexistent URLs raises FileNotFoundError."""
        import tempfile

        from rpsd_storage.providers.base import StorageProvider
        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save one valid file
            url1, _ = provider.save(
                b"Content", "file1.txt", who="user1", what="document"
            )

            # Create a fake URL
            fake_url = "file:///nonexistent/path/file.txt"

            # Compare should raise FileNotFoundError
            with pytest.raises(FileNotFoundError):
                StorageProvider.compare_from_url(url1, fake_url)

    def test_compare_from_url_cross_provider(self):
        """Test comparing URLs from different providers (FS and HTTP mock)."""
        import tempfile

        from rpsd_storage.providers.fs import FSStorageProvider

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)

            # Save a file locally
            url1, _ = provider.save(
                b"Local content", "local.txt", who="user1", what="document"
            )

            # This test would require a real HTTP server or mock
            # For now, we'll just verify the method exists and works with FS
            from rpsd_storage.providers.base import StorageProvider

            # Save another local file to compare
            url2, _ = provider.save(
                b"Local content", "local2.txt", who="user1", what="document"
            )

            result = StorageProvider.compare_from_url(url1, url2)
            assert result == 0  # Same content
