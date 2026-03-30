"""Tests for compression utilities."""

import gzip
import io
import zipfile

import pytest

from rpsd_transport.compression import (
    CompressionError,
    decompress_content,
    is_compressed,
)


class TestDecompressContent:
    """Tests for decompress_content function."""

    def test_decompress_gzip_by_magic_bytes(self):
        """Test GZIP detection via magic bytes."""
        original = b"Hello, World!"
        compressed = gzip.compress(original)

        result = decompress_content(compressed)

        assert result == original

    def test_decompress_gzip_by_filename(self):
        """Test GZIP detection via .gz extension."""
        original = b"Hello, World!"
        compressed = gzip.compress(original)

        result = decompress_content(compressed, filename="test.gz")

        assert result == original

    def test_decompress_gzip_by_filename_case_insensitive(self):
        """Test GZIP detection is case-insensitive for extension."""
        original = b"Hello, World!"
        compressed = gzip.compress(original)

        result = decompress_content(compressed, filename="test.GZ")

        assert result == original

    def test_decompress_zip(self):
        """Test ZIP decompression."""
        original = b"Hello from ZIP!"

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("test.txt", original)
        zip_data = zip_buffer.getvalue()

        result = decompress_content(zip_data, filename="archive.zip")

        assert result == original

    def test_decompress_zip_extracts_first_file(self):
        """Test ZIP extracts the first file when multiple files exist."""
        first_content = b"First file content"
        second_content = b"Second file content"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("first.txt", first_content)
            zf.writestr("second.txt", second_content)
        zip_data = zip_buffer.getvalue()

        result = decompress_content(zip_data, filename="archive.zip")

        assert result == first_content

    def test_no_decompression_needed(self):
        """Test pass-through for uncompressed content."""
        original = b"Plain text content"

        result = decompress_content(original)

        assert result == original

    def test_no_decompression_with_non_matching_extension(self):
        """Test pass-through when filename has non-compressed extension."""
        original = b"Plain text content"

        result = decompress_content(original, filename="data.txt")

        assert result == original

    def test_decompression_error_corrupt_gzip(self):
        """Test error handling for corrupt GZIP data."""
        # GZIP magic bytes but corrupt data
        corrupt_gzip = b"\x1f\x8b\x08\x00corrupt_data"

        with pytest.raises(CompressionError) as exc_info:
            decompress_content(corrupt_gzip)

        assert "Failed to decompress" in str(exc_info.value)

    def test_decompression_error_corrupt_zip(self):
        """Test error handling for corrupt ZIP data."""
        corrupt_zip = b"not a valid zip file"

        with pytest.raises(CompressionError) as exc_info:
            decompress_content(corrupt_zip, filename="archive.zip")

        assert "Invalid ZIP archive" in str(exc_info.value)

    def test_decompression_error_empty_zip(self):
        """Test error handling for empty ZIP archive."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w"):
            pass  # Create empty ZIP
        empty_zip = zip_buffer.getvalue()

        with pytest.raises(CompressionError) as exc_info:
            decompress_content(empty_zip, filename="empty.zip")

        assert "ZIP archive is empty" in str(exc_info.value)


class TestIsCompressed:
    """Tests for is_compressed function."""

    def test_gzip_magic_bytes_detected(self):
        """Test GZIP detection via magic bytes."""
        compressed = gzip.compress(b"test")

        assert is_compressed(compressed) is True

    def test_gzip_extension_detected(self):
        """Test GZIP detection via .gz extension."""
        content = b"not actually compressed"

        assert is_compressed(content, filename="test.gz") is True

    def test_zip_extension_detected(self):
        """Test ZIP detection via .zip extension."""
        content = b"not actually compressed"

        assert is_compressed(content, filename="archive.zip") is True

    def test_uncompressed_not_detected(self):
        """Test uncompressed content returns False."""
        content = b"plain text"

        assert is_compressed(content) is False

    def test_uncompressed_with_txt_extension(self):
        """Test uncompressed content with .txt extension returns False."""
        content = b"plain text"

        assert is_compressed(content, filename="data.txt") is False
