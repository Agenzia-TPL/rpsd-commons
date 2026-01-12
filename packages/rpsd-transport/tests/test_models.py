"""Tests for transport models."""

import pytest
from pydantic import ValidationError

from rpsd_transport.models import (
    InlineMessagePayload,
    MessageMetadata,
    TransportMessage,
)


class TestMessageMetadata:
    """Tests for MessageMetadata model."""

    def test_is_heavy_with_where(self):
        """Test is_heavy returns True when where is set."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="https://storage.example.com/file.xml",
        )

        assert metadata.is_fatheavy is True
        assert metadata.is_slimfast is False

    def test_is_heavy_without_where(self):
        """Test is_heavy returns False when where is None."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
        )

        assert metadata.is_fatheavy is False
        assert metadata.is_slimfast is True

    def test_valid_identifier_alphanumeric(self):
        """Test valid alphanumeric identifiers are accepted."""
        metadata = MessageMetadata(
            who="user123",
            what="documentType",
        )

        assert metadata.who == "user123"
        assert metadata.what == "documentType"

    def test_valid_identifier_with_dashes(self):
        """Test identifiers with dashes are accepted."""
        metadata = MessageMetadata(
            who="user-123",
            what="document-type",
        )

        assert metadata.who == "user-123"
        assert metadata.what == "document-type"

    def test_valid_identifier_with_underscores(self):
        """Test identifiers with underscores are accepted."""
        metadata = MessageMetadata(
            who="user_123",
            what="document_type",
        )

        assert metadata.who == "user_123"
        assert metadata.what == "document_type"

    def test_invalid_identifier_with_spaces(self):
        """Test identifiers with spaces are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MessageMetadata(
                who="user 123",
                what="document",
            )

        assert "alphanumeric" in str(exc_info.value).lower()

    def test_invalid_identifier_with_special_chars(self):
        """Test identifiers with special characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MessageMetadata(
                who="user@123",
                what="document",
            )

        assert "alphanumeric" in str(exc_info.value).lower()

    def test_empty_identifier_rejected(self):
        """Test empty identifiers are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MessageMetadata(
                who="",
                what="document",
            )

        assert "empty" in str(exc_info.value).lower()

    def test_valid_where_url_https(self):
        """Test valid HTTPS URL is accepted."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="https://storage.example.com/file.xml",
        )

        assert metadata.where == "https://storage.example.com/file.xml"

    def test_valid_where_url_s3(self):
        """Test valid S3 URL is accepted."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="s3://bucket-name/path/to/file.xml",
        )

        assert metadata.where == "s3://bucket-name/path/to/file.xml"

    def test_valid_where_url_file(self):
        """Test valid file URL is accepted."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="file:///storage/path/to/file.xml",
        )

        assert metadata.where == "file:///storage/path/to/file.xml"

    def test_invalid_where_url_no_scheme(self):
        """Test URL without scheme is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MessageMetadata(
                who="user123",
                what="document",
                where="storage.example.com/file.xml",
            )

        assert "url" in str(exc_info.value).lower()

    def test_invalid_where_url_no_host(self):
        """Test URL without host is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MessageMetadata(
                who="user123",
                what="document",
                where="https:///path/to/file",
            )

        assert "url" in str(exc_info.value).lower()

    def test_default_content_type(self):
        """Test default content_type is application/octet-stream."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
        )

        assert metadata.content_type == "application/octet-stream"

    def test_custom_content_type(self):
        """Test custom content_type is preserved."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            content_type="application/xml",
        )

        assert metadata.content_type == "application/xml"


class TestTransportMessage:
    """Tests for TransportMessage model."""

    def test_mode_property_fast(self):
        """Test mode property returns 'fast' for no where."""
        metadata = MessageMetadata(who="user123", what="document")
        message = TransportMessage(metadata=metadata, content=b"test content")

        assert message.is_slimfast is True
        assert message.is_fatheavy is False

    def test_mode_property_heavy(self):
        """Test mode property returns 'heavy' with where."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="https://example.com/file",
        )
        message = TransportMessage(metadata=metadata)

        assert message.is_fatheavy is True
        assert message.is_slimfast is False

    def test_convenience_accessors(self):
        """Test convenience accessors for metadata fields."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="https://example.com/file",
        )
        message = TransportMessage(metadata=metadata)

        assert message.who == "user123"
        assert message.what == "document"
        assert message.where == "https://example.com/file"

    def test_content_bytes(self):
        """Test content field accepts bytes."""
        metadata = MessageMetadata(who="user123", what="document")
        message = TransportMessage(metadata=metadata, content=b"binary content")

        assert message.content == b"binary content"

    def test_content_none_for_heavy(self):
        """Test content can be None for heavy messages."""
        metadata = MessageMetadata(
            who="user123",
            what="document",
            where="https://example.com/file",
        )
        message = TransportMessage(metadata=metadata, content=None)

        assert message.content is None


class TestInlineMessagePayload:
    """Tests for InlineMessagePayload model."""

    def test_valid_fast_payload(self):
        """Test valid fast message payload."""
        payload = InlineMessagePayload(
            metadata=MessageMetadata(who="user123", what="document"),
            content="SGVsbG8gV29ybGQh",  # base64 "Hello World!"
        )

        assert payload.metadata.who == "user123"
        assert payload.metadata.what == "document"
        assert payload.content == "SGVsbG8gV29ybGQh"

    def test_valid_heavy_payload(self):
        """Test valid heavy message payload (no content)."""
        payload = InlineMessagePayload(
            metadata=MessageMetadata(
                who="user123",
                what="document",
                where="https://example.com/file",
            ),
        )

        assert payload.metadata.where == "https://example.com/file"
        assert payload.content is None

    def test_nested_metadata_structure(self):
        """Test payload accepts nested metadata structure from dict."""
        data = {
            "metadata": {
                "who": "user123",
                "what": "document",
                "content_type": "application/xml",
            },
            "content": "SGVsbG8h",
        }

        payload = InlineMessagePayload.model_validate(data)

        assert payload.metadata.who == "user123"
        assert payload.metadata.what == "document"
        assert payload.metadata.content_type == "application/xml"
        assert payload.content == "SGVsbG8h"

    def test_missing_required_metadata_fields(self):
        """Test payload rejects missing required metadata fields."""
        data = {
            "metadata": {
                "who": "user123",
                # missing 'what'
            },
            "content": "SGVsbG8h",
        }

        with pytest.raises(ValidationError):
            InlineMessagePayload.model_validate(data)
