"""
Tests for IngestProcessor.

Tests cover both sync (process) and async (process_async) APIs,
with mocked StorageProvider, BaseCarrier, and httpx for heavy
content resolution.
"""

from unittest.mock import MagicMock

import httpx
import pytest
import respx

from rpsd_storage.metadata import StorageMetadata
from rpsd_transport.carriers.base import BaseCarrier
from rpsd_transport.exceptions import ContentFetchError, StorageError
from rpsd_transport.models import MessageMetadata, TransportMessage
from rpsd_transport.processors.ingest import IngestProcessor, IngestResult


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
def mock_storage():
    """Create a mock StorageProvider."""
    storage = MagicMock()
    storage.save.return_value = (
        "file:///tmp/test-entity/test-content/uuid-123.json",
        StorageMetadata(
            provider="fs",
            url=("file:///tmp/test-entity/test-content/uuid-123.json"),
            content_type="application/json",
            content_length=16,
            hash="abc123hash",
            who="test-entity",
            what="test-content",
            original_filename="data.json",
            object_id="uuid-123",
            save_stamp="2026-01-01T00:00:00Z",
            schema_version=1,
            source_url="",
            custom_metadata={},
        ),
    )
    return storage


@pytest.fixture
def mock_forward_carrier():
    """Create a mock forward carrier with BaseCarrier spec.

    Using spec=BaseCarrier ensures hasattr() returns False
    for methods not on BaseCarrier (like send_slimfast_async),
    which is needed to test async fallback behavior.
    """
    carrier = MagicMock(spec=BaseCarrier)
    carrier.send_slimfast.return_value = {"status": "sent"}
    carrier.send_fatheavy.return_value = {"status": "sent"}
    return carrier


# =============================================================================
# Constructor Tests
# =============================================================================


class TestIngestProcessorInit:
    """Test IngestProcessor initialization."""

    def test_minimal_init(self):
        """Test init with no arguments."""
        processor = IngestProcessor()
        assert processor.storage is None
        assert processor.forward_carrier is None
        assert processor.forward_recipient is None
        assert processor.forward_options is None
        assert processor.forward_mode == "fatheavy"

    def test_init_with_storage(self, mock_storage):
        """Test init with storage only."""
        processor = IngestProcessor(storage=mock_storage)
        assert processor.storage is mock_storage
        assert processor.forward_carrier is None

    def test_init_with_forward(self, mock_forward_carrier):
        """Test init with forward carrier and recipient."""
        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        assert processor.forward_carrier is mock_forward_carrier
        assert processor.forward_recipient == "output-topic"

    def test_init_forward_without_recipient_raises(self, mock_forward_carrier):
        """Test that forward_carrier without recipient raises."""
        with pytest.raises(ValueError, match="forward_recipient"):
            IngestProcessor(forward_carrier=mock_forward_carrier)

    def test_init_with_forward_mode_slimfast(self, mock_forward_carrier):
        """Test init with slimfast forward mode."""
        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="topic",
            forward_mode="slimfast",
        )
        assert processor.forward_mode == "slimfast"


# =============================================================================
# Sync Process Tests
# =============================================================================


class TestProcessSync:
    """Test IngestProcessor.process() (sync)."""

    def test_slim_message_with_storage(self, slim_message, mock_storage):
        """Test processing slim message and saving to storage."""
        processor = IngestProcessor(storage=mock_storage)
        result = processor.process(slim_message)

        assert isinstance(result, IngestResult)
        assert result.message is slim_message
        assert result.content == b'{"key": "value"}'
        assert result.storage_url is not None
        assert result.storage_metadata is not None
        assert result.forwarded is False

        mock_storage.save.assert_called_once_with(
            content=b'{"key": "value"}',
            filename="data.json",
            who="test-entity",
            what="test-content",
            content_type="application/json",
            source_url=None,
            custom_metadata={},
        )

    @respx.mock
    def test_heavy_message_with_storage(self, heavy_message, mock_storage):
        """Test processing heavy message: fetch + save."""
        respx.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(200, content=b"<xml>data</xml>")
        )

        processor = IngestProcessor(storage=mock_storage)
        result = processor.process(heavy_message)

        assert result.content == b"<xml>data</xml>"
        assert result.storage_url is not None

        mock_storage.save.assert_called_once_with(
            content=b"<xml>data</xml>",
            filename="data.xml",
            who="test-entity",
            what="test-content",
            content_type="application/xml",
            source_url="https://storage.example.com/files/abc123",
            custom_metadata={},
        )

    def test_slim_message_forward_no_storage(self, slim_message, mock_forward_carrier):
        """Test forwarding slim message without storage."""
        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        result = processor.process(slim_message)

        assert result.storage_url is None
        assert result.forwarded is True

        mock_forward_carrier.send_slimfast.assert_called_once_with(
            recipient="output-topic",
            who="test-entity",
            what="test-content",
            content=b'{"key": "value"}',
            content_type="application/json",
            filename="data.json",
            options=None,
            custom_metadata=None,
        )

    @respx.mock
    def test_heavy_message_forward_no_storage(
        self, heavy_message, mock_forward_carrier
    ):
        """Test forwarding heavy message without storage."""
        respx.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(200, content=b"<xml>data</xml>")
        )

        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        result = processor.process(heavy_message)

        assert result.forwarded is True

        mock_forward_carrier.send_fatheavy.assert_called_once_with(
            recipient="output-topic",
            who="test-entity",
            what="test-content",
            content=None,
            content_type="application/xml",
            filename="data.xml",
            options=None,
            where="https://storage.example.com/files/abc123",
            custom_metadata=None,
        )

    def test_save_and_forward_fatheavy_mode(
        self, slim_message, mock_storage, mock_forward_carrier
    ):
        """Test save + forward in fatheavy mode."""
        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
            forward_mode="fatheavy",
        )
        result = processor.process(slim_message)

        assert result.storage_url is not None
        assert result.forwarded is True

        mock_forward_carrier.send_fatheavy.assert_called_once()
        call_kwargs = mock_forward_carrier.send_fatheavy.call_args.kwargs
        assert call_kwargs["where"] == result.storage_url

    def test_save_and_forward_slimfast_mode(
        self, slim_message, mock_storage, mock_forward_carrier
    ):
        """Test save + forward in slimfast mode."""
        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
            forward_mode="slimfast",
        )
        result = processor.process(slim_message)

        assert result.storage_url is not None
        assert result.forwarded is True

        mock_forward_carrier.send_slimfast.assert_called_once()
        call_kwargs = mock_forward_carrier.send_slimfast.call_args.kwargs
        assert call_kwargs["content"] == b'{"key": "value"}'

    def test_no_storage_no_forward(self, slim_message):
        """Test processing without storage or forward."""
        processor = IngestProcessor()
        result = processor.process(slim_message)

        assert result.content == b'{"key": "value"}'
        assert result.storage_url is None
        assert result.forwarded is False

    def test_storage_failure_raises(self, slim_message, mock_storage):
        """Test that storage failure raises StorageError."""
        mock_storage.save.side_effect = Exception("disk full")

        processor = IngestProcessor(storage=mock_storage)
        with pytest.raises(StorageError, match="disk full"):
            processor.process(slim_message)

    def test_storage_failure_no_forward(
        self,
        slim_message,
        mock_storage,
        mock_forward_carrier,
    ):
        """Test that storage failure prevents forwarding."""
        mock_storage.save.side_effect = Exception("disk full")

        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        with pytest.raises(StorageError):
            processor.process(slim_message)

        mock_forward_carrier.send_slimfast.assert_not_called()
        mock_forward_carrier.send_fatheavy.assert_not_called()

    def test_forward_failure_returns_false(self, slim_message, mock_forward_carrier):
        """Test that forward failure returns forwarded=False."""
        mock_forward_carrier.send_slimfast.side_effect = Exception("connection refused")

        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        result = processor.process(slim_message)

        assert result.forwarded is False
        assert result.content == b'{"key": "value"}'

    def test_forward_failure_after_save_preserves_url(
        self,
        slim_message,
        mock_storage,
        mock_forward_carrier,
    ):
        """Test forward failure after save keeps storage_url."""
        mock_forward_carrier.send_fatheavy.side_effect = Exception("connection refused")

        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
            forward_mode="fatheavy",
        )
        result = processor.process(slim_message)

        assert result.storage_url is not None
        assert result.forwarded is False

    @respx.mock
    def test_heavy_content_fetch_failure(self, heavy_message):
        """Test that heavy content fetch failure raises."""
        respx.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(404)
        )

        processor = IngestProcessor()
        with pytest.raises(ContentFetchError):
            processor.process(heavy_message)

    def test_slim_message_passes_custom_metadata_to_storage(self, mock_storage):
        """Test that custom_metadata is passed to storage.save()."""
        custom = {"workflow_id": "wf-123", "priority": "high"}
        message = TransportMessage(
            metadata=MessageMetadata(
                who="test-entity",
                what="test-content",
                content_type="application/json",
                filename="data.json",
                custom_metadata=custom,
            ),
            content=b'{"key": "value"}',
        )

        processor = IngestProcessor(storage=mock_storage)
        result = processor.process(message)

        assert result.storage_url is not None
        mock_storage.save.assert_called_once()
        call_kwargs = mock_storage.save.call_args.kwargs
        assert call_kwargs["custom_metadata"] == custom


# =============================================================================
# Async Process Tests
# =============================================================================


class TestProcessAsync:
    """Test IngestProcessor.process_async() (async)."""

    @pytest.mark.anyio
    async def test_slim_message_with_storage(self, slim_message, mock_storage):
        """Test async processing slim message with storage."""
        processor = IngestProcessor(storage=mock_storage)
        result = await processor.process_async(slim_message)

        assert result.content == b'{"key": "value"}'
        assert result.storage_url is not None
        assert result.forwarded is False
        mock_storage.save.assert_called_once()

    @pytest.mark.anyio
    @respx.mock
    async def test_heavy_message_with_storage(self, heavy_message, mock_storage):
        """Test async processing heavy message: fetch + save."""
        respx.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(200, content=b"<xml>data</xml>")
        )

        processor = IngestProcessor(storage=mock_storage)
        result = await processor.process_async(heavy_message)

        assert result.content == b"<xml>data</xml>"
        assert result.storage_url is not None

    @pytest.mark.anyio
    async def test_slim_forward_no_storage(self, slim_message, mock_forward_carrier):
        """Test async forwarding slim message without storage."""
        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        result = await processor.process_async(slim_message)

        assert result.forwarded is True
        mock_forward_carrier.send_slimfast_async.assert_called_once()

    @pytest.mark.anyio
    @respx.mock
    async def test_heavy_forward_no_storage(self, heavy_message, mock_forward_carrier):
        """Test async forwarding heavy message without storage."""
        respx.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(200, content=b"<xml>data</xml>")
        )

        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        result = await processor.process_async(heavy_message)

        assert result.forwarded is True
        mock_forward_carrier.send_fatheavy_async.assert_called_once()

    @pytest.mark.anyio
    async def test_save_and_forward_fatheavy(
        self, slim_message, mock_storage, mock_forward_carrier
    ):
        """Test async save + forward in fatheavy mode."""
        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
            forward_mode="fatheavy",
        )
        result = await processor.process_async(slim_message)

        assert result.storage_url is not None
        assert result.forwarded is True
        mock_forward_carrier.send_fatheavy_async.assert_called_once()

    @pytest.mark.anyio
    async def test_save_and_forward_slimfast(
        self, slim_message, mock_storage, mock_forward_carrier
    ):
        """Test async save + forward in slimfast mode."""
        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
            forward_mode="slimfast",
        )
        result = await processor.process_async(slim_message)

        assert result.storage_url is not None
        assert result.forwarded is True
        mock_forward_carrier.send_slimfast_async.assert_called_once()

    @pytest.mark.anyio
    async def test_storage_failure_raises(self, slim_message, mock_storage):
        """Test async storage failure raises StorageError."""
        mock_storage.save.side_effect = Exception("disk full")

        processor = IngestProcessor(storage=mock_storage)
        with pytest.raises(StorageError, match="disk full"):
            await processor.process_async(slim_message)

    @pytest.mark.anyio
    async def test_forward_failure_returns_false(
        self, slim_message, mock_forward_carrier
    ):
        """Test async forward failure returns forwarded=False."""
        mock_forward_carrier.send_slimfast_async.side_effect = Exception(
            "connection refused"
        )

        processor = IngestProcessor(
            forward_carrier=mock_forward_carrier,
            forward_recipient="output-topic",
        )
        result = await processor.process_async(slim_message)

        assert result.forwarded is False

    @pytest.mark.anyio
    @respx.mock
    async def test_heavy_content_fetch_failure(self, heavy_message):
        """Test async heavy content fetch failure."""
        respx.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(404)
        )

        processor = IngestProcessor()
        with pytest.raises(ContentFetchError):
            await processor.process_async(heavy_message)

    @pytest.mark.anyio
    async def test_uses_async_send_when_available(self, slim_message):
        """Test that async process uses *_async send methods."""
        from unittest.mock import AsyncMock

        # Use a plain MagicMock (no spec) so we can add
        # send_slimfast_async dynamically
        carrier = MagicMock()
        carrier.send_slimfast_async = AsyncMock(return_value={"status": "sent"})

        processor = IngestProcessor(
            forward_carrier=carrier,
            forward_recipient="output-topic",
        )
        result = await processor.process_async(slim_message)

        assert result.forwarded is True
        carrier.send_slimfast_async.assert_called_once()
        carrier.send_slimfast.assert_not_called()

    @pytest.mark.anyio
    async def test_default_async_uses_thread_pool(self, slim_message):
        """Test that BaseCarrier's default async implementation works.

        The default implementation uses asyncio.to_thread to run
        the sync method in a thread pool.
        """
        from rpsd_transport.carriers.http import HTTPCarrier

        carrier = HTTPCarrier()
        # Mock the sync send method
        carrier.send_slimfast = MagicMock(return_value={"status": "sent"})

        processor = IngestProcessor(
            forward_carrier=carrier,
            forward_recipient="http://example.com/ingest",
        )
        result = await processor.process_async(slim_message)

        assert result.forwarded is True
        # The sync method should have been called via to_thread
        carrier.send_slimfast.assert_called_once()


# =============================================================================
# Transformation Tests
# =============================================================================


class TestTransformations:
    """Tests for message transformations."""

    def test_pre_save_transform_enriches_metadata(self, slim_message, mock_storage):
        """Test that pre_save_transform modifies message before storage."""

        def enrich_metadata(msg: TransportMessage, content: bytes) -> TransportMessage:
            return msg.model_copy(
                update={
                    "metadata": msg.metadata.model_copy(
                        update={
                            "custom_metadata": {
                                **msg.metadata.custom_metadata,
                                "enriched": "true",
                                "size": len(content),
                            }
                        }
                    )
                }
            )

        processor = IngestProcessor(
            storage=mock_storage, pre_save_transform=enrich_metadata
        )
        processor.process(slim_message)

        # Verify storage received the enriched message
        mock_storage.save.assert_called_once()
        call_kwargs = mock_storage.save.call_args[1]
        assert call_kwargs["custom_metadata"]["enriched"] == "true"
        assert call_kwargs["custom_metadata"]["size"] == len(slim_message.content)

    def test_pre_save_transform_with_helper(self, slim_message, mock_storage):
        """Test pre_save_transform with with_custom_metadata helper."""
        from rpsd_transport.transformers import with_custom_metadata

        def add_timestamp(meta: dict, content: bytes) -> dict:
            return {**meta, "timestamp": "2024-01-01T00:00:00Z"}

        processor = IngestProcessor(
            storage=mock_storage, pre_save_transform=with_custom_metadata(add_timestamp)
        )
        processor.process(slim_message)

        # Verify custom_metadata was enriched
        mock_storage.save.assert_called_once()
        call_kwargs = mock_storage.save.call_args[1]
        assert call_kwargs["custom_metadata"]["timestamp"] == "2024-01-01T00:00:00Z"

    def test_pre_forward_transform_modifies_forward_message(self, slim_message):
        """Test that pre_forward_transform modifies message before forwarding."""
        carrier = MagicMock(spec=BaseCarrier)
        carrier.send_slimfast = MagicMock(return_value={"status": "sent"})

        def modify_who(msg: TransportMessage, content: bytes) -> TransportMessage:
            return msg.model_copy(
                update={
                    "metadata": msg.metadata.model_copy(update={"who": "modified-user"})
                }
            )

        processor = IngestProcessor(
            forward_carrier=carrier,
            forward_recipient="output-topic",
            pre_forward_transform=modify_who,
        )
        processor.process(slim_message)

        # Verify forward carrier received modified message
        carrier.send_slimfast.assert_called_once()
        call_kwargs = carrier.send_slimfast.call_args[1]
        assert call_kwargs["who"] == "modified-user"

    def test_different_transforms_for_save_and_forward(
        self, slim_message, mock_storage
    ):
        """Test using different transformers for save vs forward."""
        carrier = MagicMock(spec=BaseCarrier)
        carrier.send_slimfast = MagicMock(return_value={"status": "sent"})

        def save_transform(msg: TransportMessage, content: bytes) -> TransportMessage:
            return msg.model_copy(
                update={
                    "metadata": msg.metadata.model_copy(
                        update={
                            "custom_metadata": {
                                **msg.metadata.custom_metadata,
                                "saved": "true",
                            }
                        }
                    )
                }
            )

        def forward_transform(
            msg: TransportMessage, content: bytes
        ) -> TransportMessage:
            return msg.model_copy(
                update={
                    "metadata": msg.metadata.model_copy(
                        update={
                            "custom_metadata": {
                                **msg.metadata.custom_metadata,
                                "forwarded": "true",
                            }
                        }
                    )
                }
            )

        processor = IngestProcessor(
            storage=mock_storage,
            forward_carrier=carrier,
            forward_recipient="output-topic",
            forward_mode="slimfast",  # Use slimfast to test send_slimfast
            pre_save_transform=save_transform,
            pre_forward_transform=forward_transform,
        )
        result = processor.process(slim_message)

        # Verify storage received save transform
        storage_kwargs = mock_storage.save.call_args[1]
        assert storage_kwargs["custom_metadata"]["saved"] == "true"
        assert "forwarded" not in storage_kwargs["custom_metadata"]

        # Verify forward carrier was called (transforms were applied in sequence)
        carrier.send_slimfast.assert_called_once()
        assert result.forwarded is True

    def test_transform_error_aborts_pipeline(self, slim_message, mock_storage):
        """Test that transformer exceptions abort the pipeline."""
        from rpsd_transport.exceptions import TransformError

        def failing_transform(
            msg: TransportMessage, content: bytes
        ) -> TransportMessage:
            raise ValueError("Transform failed")

        processor = IngestProcessor(
            storage=mock_storage, pre_save_transform=failing_transform
        )

        with pytest.raises(TransformError) as exc_info:
            processor.process(slim_message)

        assert "Transform failed" in str(exc_info.value)
        # Verify storage was not called
        mock_storage.save.assert_not_called()

    def test_transform_preserves_original_message_in_result(self, slim_message):
        """Test that IngestResult contains original message, not transformed."""

        def modify_who(msg: TransportMessage, content: bytes) -> TransportMessage:
            return msg.model_copy(
                update={"metadata": msg.metadata.model_copy(update={"who": "modified"})}
            )

        processor = IngestProcessor(pre_save_transform=modify_who)
        result = processor.process(slim_message)

        # Result should contain original message
        assert result.message.who == "test-entity"
        assert result.message.who != "modified"

    @pytest.mark.anyio
    async def test_async_transform_with_process_async(self, slim_message, mock_storage):
        """Test async transformer with process_async."""

        class AsyncTransformer:
            async def transform(
                self, msg: TransportMessage, content: bytes
            ) -> TransportMessage:
                return msg.model_copy(
                    update={
                        "metadata": msg.metadata.model_copy(
                            update={
                                "custom_metadata": {
                                    **msg.metadata.custom_metadata,
                                    "async": "true",
                                }
                            }
                        )
                    }
                )

        processor = IngestProcessor(
            storage=mock_storage, pre_save_transform=AsyncTransformer()
        )
        await processor.process_async(slim_message)

        # Verify async transform was applied
        mock_storage.save.assert_called_once()
        call_kwargs = mock_storage.save.call_args[1]
        assert call_kwargs["custom_metadata"]["async"] == "true"

    @pytest.mark.anyio
    async def test_sync_transform_with_process_async(self, slim_message, mock_storage):
        """Test sync transformer works with process_async (via thread pool)."""

        def sync_transform(msg: TransportMessage, content: bytes) -> TransportMessage:
            return msg.model_copy(
                update={
                    "metadata": msg.metadata.model_copy(
                        update={
                            "custom_metadata": {
                                **msg.metadata.custom_metadata,
                                "sync": "true",
                            }
                        }
                    )
                }
            )

        processor = IngestProcessor(
            storage=mock_storage, pre_save_transform=sync_transform
        )
        await processor.process_async(slim_message)

        # Verify sync transform was applied via thread pool
        mock_storage.save.assert_called_once()
        call_kwargs = mock_storage.save.call_args[1]
        assert call_kwargs["custom_metadata"]["sync"] == "true"

    def test_no_transform_backward_compatibility(self, slim_message, mock_storage):
        """Test that processor works without transformers (backward compat)."""
        processor = IngestProcessor(storage=mock_storage)
        result = processor.process(slim_message)

        # Should work as before
        assert result.storage_url is not None
        mock_storage.save.assert_called_once()

    def test_transform_receives_resolved_content(self, mock_storage, respx_mock):
        """Test that transformer receives resolved content for heavy messages."""
        heavy_message = TransportMessage(
            metadata=MessageMetadata(
                who="test-entity",
                what="test-content",
                where="https://storage.example.com/files/abc123",
            )
        )

        received_content = None

        def capture_content(msg: TransportMessage, content: bytes) -> TransportMessage:
            nonlocal received_content
            received_content = content
            return msg

        # Mock the heavy content fetch
        respx_mock.get("https://storage.example.com/files/abc123").mock(
            return_value=httpx.Response(200, content=b"heavy content")
        )

        processor = IngestProcessor(
            storage=mock_storage, pre_save_transform=capture_content
        )
        processor.process(heavy_message)

        # Verify transformer received the fetched content
        assert received_content == b"heavy content"
