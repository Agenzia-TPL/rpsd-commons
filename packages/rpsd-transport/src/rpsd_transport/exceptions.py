"""Custom exceptions for rpsd-transport."""


class TransportError(Exception):
    """Base exception for transport errors."""

    pass


class DuplicateMetadataError(TransportError):
    """Raised when metadata is specified in both header and query parameter."""

    pass


class MissingMetadataError(TransportError):
    """Raised when required metadata (who/what) is missing."""

    pass


class InvalidJsonError(TransportError):
    """Raised when JSON body is invalid or malformed."""

    pass


class CompressionError(TransportError):
    """Raised when decompression fails."""

    pass


class ContentFetchError(TransportError):
    """Raised when fetching content from URL fails."""

    pass


class StorageError(TransportError):
    """Raised when storage operation fails."""

    pass


class InvalidMetadataError(TransportError):
    """Raised when metadata values are invalid (e.g., bad characters)."""

    pass
