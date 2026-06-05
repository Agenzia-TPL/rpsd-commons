# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Tests for rpsd_transport.resolve utility functions.

Tests cover resolve_content, resolve_content_async, and
reconcile_metadata with both slim/fast and fat/heavy messages.
"""

from unittest.mock import patch

import pytest

from rpsd_storage.metadata import StorageMetadata
from rpsd_transport.exceptions import ContentFetchError
from rpsd_transport.models import MessageMetadata, TransportMessage
from rpsd_transport.resolve import (
    reconcile_metadata,
    resolve_content,
    resolve_content_async,
)


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only (trio not installed)."""
    return "asyncio"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def slim_message():
    """Create a slim/fast TransportMessage."""
    return TransportMessage(
        metadata=MessageMetadata(
            who="test-entity",
            what="test-content",
            content_type="application/json",
            filename="data.json",
        ),
        content=b'{"key": "value"}',
    )


@pytest.fixture
def heavy_message():
    """Create a fat/heavy TransportMessage."""
    return TransportMessage(
        metadata=MessageMetadata(
            who="test-entity",
            what="test-content",
            where="https://storage.example.com/files/abc123",
            content_type="application/xml",
            filename="data.xml",
        ),
        content=None,
    )


@pytest.fixture
def heavy_message_no_filename():
    """Create a fat/heavy TransportMessage without filename."""
    return TransportMessage(
        metadata=MessageMetadata(
            who="test-entity",
            what="test-content",
            where="https://storage.example.com/files/abc123",
            content_type="application/octet-stream",
        ),
        content=None,
    )


@pytest.fixture
def fetch_metadata():
    """Create a StorageMetadata as returned by load_from_url."""
    return StorageMetadata(
        provider="http",
        url="https://storage.example.com/files/abc123",
        content_type="application/json",
        content_length=42,
        hash="def456hash",
        who="http",
        what="resource",
        original_filename="fetched-data.json",
        object_id="http-uuid-123",
        save_stamp="20260101_120000",
        schema_version=1,
        source_url="https://storage.example.com/files/abc123",
    )


# =============================================================================
# resolve_content tests
# =============================================================================


class TestResolveContent:
    """Tests for resolve_content()."""

    def test_resolve_slim_message(self, slim_message):
        """Slim/fast message returns content directly."""
        content, fetch_meta = resolve_content(slim_message)

        assert content == b'{"key": "value"}'
        assert fetch_meta is None

    def test_resolve_slim_message_no_content_raises(self):
        """Slim/fast message with no content raises ValueError."""
        message = TransportMessage(
            metadata=MessageMetadata(
                who="test-entity",
                what="test-content",
            ),
            content=None,
        )

        with pytest.raises(ValueError, match="no content"):
            resolve_content(message)

    @patch("rpsd_storage.providers.base.StorageProvider.load_from_url")
    def test_resolve_heavy_message(self, mock_load, heavy_message, fetch_metadata):
        """Fat/heavy message fetches from where URL."""
        mock_load.return_value = (b"fetched content", fetch_metadata)

        content, fetch_meta = resolve_content(heavy_message)

        assert content == b"fetched content"
        assert fetch_meta is fetch_metadata
        mock_load.assert_called_once_with("https://storage.example.com/files/abc123")

    @patch("rpsd_storage.providers.base.StorageProvider.load_from_url")
    def test_resolve_heavy_message_fetch_failure(self, mock_load, heavy_message):
        """Fetch failure raises ContentFetchError."""
        mock_load.side_effect = Exception("Connection refused")

        with pytest.raises(ContentFetchError, match="Failed to fetch"):
            resolve_content(heavy_message)

    @patch("rpsd_storage.providers.base.StorageProvider.load_from_url")
    def test_resolve_heavy_preserves_content_fetch_error(
        self, mock_load, heavy_message
    ):
        """ContentFetchError from load_from_url is re-raised."""
        mock_load.side_effect = ContentFetchError("Already wrapped")

        with pytest.raises(ContentFetchError, match="Already wrapped"):
            resolve_content(heavy_message)


# =============================================================================
# resolve_content_async tests
# =============================================================================


class TestResolveContentAsync:
    """Tests for resolve_content_async()."""

    @pytest.mark.anyio
    async def test_resolve_slim_message(self, slim_message):
        """Async slim/fast message returns content directly."""
        content, fetch_meta = await resolve_content_async(slim_message)

        assert content == b'{"key": "value"}'
        assert fetch_meta is None

    @pytest.mark.anyio
    @patch("rpsd_storage.providers.base.StorageProvider.load_from_url")
    async def test_resolve_heavy_message(
        self, mock_load, heavy_message, fetch_metadata
    ):
        """Async fat/heavy message fetches from where URL."""
        mock_load.return_value = (b"fetched content", fetch_metadata)

        content, fetch_meta = await resolve_content_async(heavy_message)

        assert content == b"fetched content"
        assert fetch_meta is fetch_metadata
        mock_load.assert_called_once_with("https://storage.example.com/files/abc123")


# =============================================================================
# reconcile_metadata tests
# =============================================================================


class TestReconcileMetadata:
    """Tests for reconcile_metadata()."""

    def test_reconcile_slim_returns_original(self, slim_message):
        """Slim/fast message is returned unchanged."""
        result = reconcile_metadata(slim_message, None)

        assert result is slim_message

    def test_reconcile_updates_content_type(self, heavy_message, fetch_metadata):
        """Content type is updated from fetch metadata."""
        result = reconcile_metadata(heavy_message, fetch_metadata)

        assert result.metadata.content_type == "application/json"
        # Original should be unchanged
        assert heavy_message.metadata.content_type == "application/xml"

    def test_reconcile_preserves_existing_filename(self, heavy_message, fetch_metadata):
        """Existing filename is preserved."""
        result = reconcile_metadata(heavy_message, fetch_metadata)

        assert result.metadata.filename == "data.xml"

    def test_reconcile_updates_filename_when_none(
        self, heavy_message_no_filename, fetch_metadata
    ):
        """Filename is set from fetch when original is None."""
        result = reconcile_metadata(heavy_message_no_filename, fetch_metadata)

        assert result.metadata.filename == "fetched-data.json"

    def test_reconcile_skips_unknown_filename(self, heavy_message_no_filename):
        """Filename 'unknown' from fetch is not used."""
        fetch_meta = StorageMetadata(
            provider="http",
            url="https://example.com/file",
            content_type="text/plain",
            content_length=10,
            hash="abc",
            who="http",
            what="resource",
            original_filename="unknown",
            object_id="id-1",
            save_stamp="20260101_120000",
            schema_version=1,
            source_url="",
        )

        result = reconcile_metadata(heavy_message_no_filename, fetch_meta)

        assert result.metadata.filename is None

    def test_reconcile_preserves_who_what_where(self, heavy_message, fetch_metadata):
        """who, what, where, custom_metadata are preserved."""
        result = reconcile_metadata(heavy_message, fetch_metadata)

        assert result.metadata.who == "test-entity"
        assert result.metadata.what == "test-content"
        assert result.metadata.where == ("https://storage.example.com/files/abc123")
        assert result.metadata.custom_metadata == {}
