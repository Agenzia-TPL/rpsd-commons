"""Compression handling utilities for rpsd-transport."""

import gzip
import io
import zipfile

from rpsd_transport.exceptions import CompressionError


def decompress_content(content: bytes, filename: str | None = None) -> bytes:
    """
    Decompress content if compressed, otherwise return as-is.

    Detection order:
    1. GZIP magic bytes (0x1f 0x8b)
    2. Filename extension (.gz, .zip)
    3. Return as-is if not compressed

    Args:
        content: Potentially compressed content bytes
        filename: Optional filename for extension-based detection

    Returns:
        Decompressed content bytes

    Raises:
        CompressionError: If decompression fails
    """
    try:
        # Check GZIP magic bytes first (most reliable)
        if content.startswith(b"\x1f\x8b"):
            return gzip.decompress(content)

        # Check filename extension
        if filename:
            lower_filename = filename.lower()
            if lower_filename.endswith(".gz"):
                return gzip.decompress(content)
            elif lower_filename.endswith(".zip"):
                return _decompress_zip(content)

        # Not compressed, return as-is
        return content

    except CompressionError:
        raise
    except Exception as e:
        raise CompressionError(f"Failed to decompress content: {e}") from e


def _decompress_zip(content: bytes) -> bytes:
    """
    Extract first file from ZIP archive.

    Args:
        content: ZIP archive bytes

    Returns:
        Content of the first file in the archive

    Raises:
        CompressionError: If ZIP is empty or extraction fails
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            files = zip_file.namelist()
            if not files:
                raise CompressionError("ZIP archive is empty")
            return zip_file.read(files[0])
    except zipfile.BadZipFile as e:
        raise CompressionError(f"Invalid ZIP archive: {e}") from e


def is_compressed(content: bytes, filename: str | None = None) -> bool:
    """
    Check if content appears to be compressed.

    Args:
        content: Content bytes to check
        filename: Optional filename for extension-based detection

    Returns:
        True if content appears compressed, False otherwise
    """
    # Check GZIP magic bytes
    if content.startswith(b"\x1f\x8b"):
        return True

    # Check filename extension
    if filename:
        lower_filename = filename.lower()
        if lower_filename.endswith(".gz") or lower_filename.endswith(".zip"):
            return True

    return False
