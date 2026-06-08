# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Tests for the streaming open_content family across all providers.

Streaming counterpart of test_separate_load_methods.py: open_content,
open_content_by_parts and the static open_content_from_url.
"""

import tempfile

import pytest
import respx
from httpx import Response

from rpsd_storage.providers.base import StorageProvider
from rpsd_storage.providers.fs import FSStorageProvider
from rpsd_storage.providers.http import HTTPStorageProvider

CHUNK = 4096


def _read_chunked(stream) -> bytes:
    """Read a stream in CHUNK-sized pieces until EOF."""
    out = bytearray()
    while True:
        chunk = stream.read(CHUNK)
        if not chunk:
            break
        out.extend(chunk)
    return bytes(out)


class TestFSOpenContent:
    """FSStorageProvider.open_content (seekable file handle)."""

    def test_chunked_read_equals_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            content = b"x" * (CHUNK * 3 + 17)
            url, _ = provider.save(content, "big.xml", who="u", what="data")
            with provider.open_content(url) as stream:
                assert _read_chunked(stream) == content
            assert provider.load_content(url) == content

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            url, _ = provider.save(b"", "empty.xml", who="u", what="data")
            with provider.open_content(url) as stream:
                assert _read_chunked(stream) == b""

    def test_missing_url_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            missing = f"file://{temp_dir}/u/data/nope.xml"
            with pytest.raises(FileNotFoundError):
                with provider.open_content(missing):
                    pass

    def test_early_break_closes_stream(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            url, _ = provider.save(b"a" * (CHUNK * 2), "f.xml", who="u", what="data")
            with provider.open_content(url) as stream:
                first = stream.read(CHUNK)
                assert len(first) == CHUNK
            assert stream.closed

    def test_by_parts_matches_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            content = b"by-parts content"
            url, meta = provider.save(content, "f.xml", who="u", what="data")
            with provider.open_content_by_parts("u", "data", meta.object_id) as s:
                assert _read_chunked(s) == content

    def test_from_url_dispatches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = FSStorageProvider(temp_dir)
            content = b"from-url content"
            url, _ = provider.save(content, "f.xml", who="u", what="data")
            with StorageProvider.open_content_from_url(url) as stream:
                assert _read_chunked(stream) == content


class TestS3OpenContent:
    """S3StorageProvider.open_content (botocore StreamingBody, non-seekable)."""

    def test_chunked_read_equals_bytes(self, s3_storage_provider):
        content = b"y" * (CHUNK * 3 + 5)
        url, _ = s3_storage_provider.save(content, "big.xml", who="u", what="data")
        with s3_storage_provider.open_content(url) as stream:
            assert _read_chunked(stream) == content
        assert s3_storage_provider.load_content(url) == content

    def test_empty_object(self, s3_storage_provider):
        url, _ = s3_storage_provider.save(b"", "empty.xml", who="u", what="data")
        with s3_storage_provider.open_content(url) as stream:
            assert _read_chunked(stream) == b""

    def test_missing_url_raises(self, s3_storage_provider):
        missing = f"s3://{s3_storage_provider.bucket_name}/u/data/nope.xml"
        with pytest.raises(FileNotFoundError):
            with s3_storage_provider.open_content(missing):
                pass

    def test_by_parts_matches_url(self, s3_storage_provider):
        content = b"s3 by-parts"
        url, meta = s3_storage_provider.save(content, "f.xml", who="u", what="data")
        with s3_storage_provider.open_content_by_parts(
            "u", "data", meta.object_id
        ) as s:
            assert _read_chunked(s) == content


class TestHTTPOpenContent:
    """HTTPStorageProvider.open_content (streamed body, non-seekable)."""

    @respx.mock
    def test_chunked_read_equals_bytes(self):
        url = "https://example.com/big.xml"
        content = b"z" * (CHUNK * 3 + 9)
        respx.get(url).mock(return_value=Response(200, content=content))
        provider = HTTPStorageProvider()
        with provider.open_content(url) as stream:
            assert _read_chunked(stream) == content

    @respx.mock
    def test_empty_body(self):
        url = "https://example.com/empty.xml"
        respx.get(url).mock(return_value=Response(200, content=b""))
        provider = HTTPStorageProvider()
        with provider.open_content(url) as stream:
            assert _read_chunked(stream) == b""

    @respx.mock
    def test_404_raises_file_not_found(self):
        url = "https://example.com/notfound.xml"
        respx.get(url).mock(return_value=Response(404))
        provider = HTTPStorageProvider()
        with pytest.raises(FileNotFoundError):
            with provider.open_content(url):
                pass

    def test_invalid_scheme_raises(self):
        provider = HTTPStorageProvider()
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            with provider.open_content("ftp://example.com/x.xml"):
                pass

    @respx.mock
    def test_from_url_dispatches(self):
        url = "https://example.com/data.xml"
        content = b"http from-url"
        respx.get(url).mock(return_value=Response(200, content=content))
        with StorageProvider.open_content_from_url(url) as stream:
            assert _read_chunked(stream) == content
