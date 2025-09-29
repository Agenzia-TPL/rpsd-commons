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
            ingestion_timestamp="2024-01-01T10:00:00Z",
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Different timestamp
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
            ingestion_timestamp="2024-01-01T10:00:00Z",  # Earlier
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Later
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Later
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
            ingestion_timestamp="2024-01-01T10:00:00Z",  # Earlier
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
            ingestion_timestamp="2024-01-01T10:00:00Z",
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
            ingestion_timestamp="2024-01-01T11:00:00Z",
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
            ingestion_timestamp="2024-01-01T10:00:00Z",
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
            ingestion_timestamp="2024-01-01T11:00:00Z",
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
            ingestion_timestamp="2024-01-01T10:00:00Z",  # Earlier
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Later
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
            ingestion_timestamp="2024-01-01T10:00:00Z",  # Earlier
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Later
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Later
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
            ingestion_timestamp="2024-01-01T10:00:00Z",  # Earlier
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
            ingestion_timestamp="2024-01-01T10:00:00Z",
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
            ingestion_timestamp="2024-01-01T11:00:00Z",  # Different timestamp
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
            ingestion_timestamp="2024-01-01T10:00:00Z",
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
            ingestion_timestamp="2024-01-01T11:00:00Z",
            schema_version=1,
            source_url="http://example.com/test.txt",
            custom_metadata={},
        )

        with pytest.raises(
            ValueError, match="Cannot compare metadata for different entities"
        ):
            different_entity.is_update_of(current)
