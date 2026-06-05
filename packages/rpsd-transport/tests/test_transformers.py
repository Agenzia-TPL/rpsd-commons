# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""Tests for message transformers."""

import hashlib
from datetime import UTC, datetime

import pytest

from rpsd_transport.models import MessageMetadata, TransportMessage
from rpsd_transport.transformers import (
    AsyncMessageTransformer,
    MessageTransformer,
    with_async_custom_metadata,
    with_custom_metadata,
)


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only (trio not installed)."""
    return "asyncio"


def test_with_custom_metadata_enriches_metadata():
    """Test that with_custom_metadata enriches custom_metadata."""

    def add_timestamp(meta: dict, content: bytes) -> dict:
        return {**meta, "timestamp": "2024-01-01T00:00:00Z"}

    transformer = with_custom_metadata(add_timestamp)

    # Create message
    message = TransportMessage(
        metadata=MessageMetadata(
            who="test-user",
            what="test-data",
            custom_metadata={"existing": "value"},
        ),
        content=b"test content",
    )

    # Transform
    result = transformer.transform(message, b"test content")

    # Verify enrichment
    assert result.metadata.custom_metadata == {
        "existing": "value",
        "timestamp": "2024-01-01T00:00:00Z",
    }


def test_with_custom_metadata_preserves_existing_metadata():
    """Test that existing metadata is preserved."""

    def add_hash(meta: dict, content: bytes) -> dict:
        return {
            **meta,
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    transformer = with_custom_metadata(add_hash)

    # Create message with existing custom_metadata
    message = TransportMessage(
        metadata=MessageMetadata(
            who="test-user",
            what="test-data",
            custom_metadata={"existing1": "value1", "existing2": "value2"},
        ),
        content=b"test content",
    )

    # Transform
    result = transformer.transform(message, b"test content")

    # Verify all metadata is preserved
    assert "existing1" in result.metadata.custom_metadata
    assert "existing2" in result.metadata.custom_metadata
    assert "sha256" in result.metadata.custom_metadata
    assert result.metadata.custom_metadata["existing1"] == "value1"
    assert result.metadata.custom_metadata["existing2"] == "value2"


def test_with_custom_metadata_receives_content():
    """Test that enricher receives content bytes."""

    def add_content_info(meta: dict, content: bytes) -> dict:
        return {
            **meta,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    transformer = with_custom_metadata(add_content_info)

    message = TransportMessage(
        metadata=MessageMetadata(who="test-user", what="test-data"),
        content=b"hello world",
    )

    result = transformer.transform(message, b"hello world")

    assert result.metadata.custom_metadata["size"] == 11
    assert (
        result.metadata.custom_metadata["sha256"]
        == hashlib.sha256(b"hello world").hexdigest()
    )


def test_with_custom_metadata_returns_new_message():
    """Test that transformer returns a new message (immutability)."""

    def add_timestamp(meta: dict, content: bytes) -> dict:
        return {**meta, "timestamp": "2024-01-01"}

    transformer = with_custom_metadata(add_timestamp)

    original = TransportMessage(
        metadata=MessageMetadata(who="test-user", what="test-data"),
        content=b"test",
    )

    result = transformer.transform(original, b"test")

    # Verify it's a different object
    assert result is not original
    assert result.metadata is not original.metadata

    # Verify original is unchanged
    assert "timestamp" not in original.metadata.custom_metadata

    # Verify result has the change
    assert "timestamp" in result.metadata.custom_metadata


def test_with_custom_metadata_empty_initial_metadata():
    """Test enriching when custom_metadata is empty."""

    def add_field(meta: dict, content: bytes) -> dict:
        return {**meta, "new_field": "value"}

    transformer = with_custom_metadata(add_field)

    message = TransportMessage(
        metadata=MessageMetadata(who="test-user", what="test-data", custom_metadata={}),
        content=b"test",
    )

    result = transformer.transform(message, b"test")

    assert result.metadata.custom_metadata == {"new_field": "value"}


@pytest.mark.anyio
async def test_with_async_custom_metadata():
    """Test async metadata enricher."""

    async def add_timestamp(meta: dict, content: bytes) -> dict:
        # Simulate async operation
        return {**meta, "timestamp": datetime.now(UTC).isoformat()}

    transformer = with_async_custom_metadata(add_timestamp)

    message = TransportMessage(
        metadata=MessageMetadata(who="test-user", what="test-data"),
        content=b"test",
    )

    result = await transformer.transform(message, b"test")

    assert "timestamp" in result.metadata.custom_metadata


def test_protocol_compliance_sync_transformer():
    """Test that custom transformers can implement the protocol."""

    class CustomTransformer:
        def transform(
            self, message: TransportMessage, content: bytes
        ) -> TransportMessage:
            return message.model_copy(
                update={
                    "metadata": message.metadata.model_copy(
                        update={
                            "custom_metadata": {
                                **message.metadata.custom_metadata,
                                "custom": "value",
                            }
                        }
                    )
                }
            )

    # Verify it's recognized as a MessageTransformer
    transformer = CustomTransformer()
    assert isinstance(transformer, MessageTransformer)

    # Test it works
    message = TransportMessage(
        metadata=MessageMetadata(who="test-user", what="test-data"),
        content=b"test",
    )

    result = transformer.transform(message, b"test")
    assert result.metadata.custom_metadata["custom"] == "value"


@pytest.mark.anyio
async def test_protocol_compliance_async_transformer():
    """Test that async transformers can implement the protocol."""

    class CustomAsyncTransformer:
        async def transform(
            self, message: TransportMessage, content: bytes
        ) -> TransportMessage:
            return message.model_copy(
                update={
                    "metadata": message.metadata.model_copy(
                        update={
                            "custom_metadata": {
                                **message.metadata.custom_metadata,
                                "async_custom": "value",
                            }
                        }
                    )
                }
            )

    # Verify it's recognized as an AsyncMessageTransformer
    transformer = CustomAsyncTransformer()
    assert isinstance(transformer, AsyncMessageTransformer)

    # Test it works
    message = TransportMessage(
        metadata=MessageMetadata(who="test-user", what="test-data"),
        content=b"test",
    )

    result = await transformer.transform(message, b"test")
    assert result.metadata.custom_metadata["async_custom"] == "value"
