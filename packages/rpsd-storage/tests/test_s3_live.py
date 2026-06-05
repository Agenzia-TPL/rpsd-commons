# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Live integration tests for S3StorageProvider against a real S3-compatible endpoint.

These tests are SKIPPED unless STORAGE__S3__BUCKET_NAME is set in the environment
(or a .env file), so they never run in normal CI.

The bucket must already exist. Objects written during the test session are cleaned
up on teardown; the bucket itself is never created or deleted.

To run against real AWS (credentials from IAM role / ~/.aws/credentials):

    STORAGE__S3__BUCKET_NAME=my-existing-bucket

To run against LocalStack or MinIO, also set:

    STORAGE__S3__ENDPOINT_URL=http://localhost:4566
    STORAGE__S3__AWS_ACCESS_KEY_ID=test
    STORAGE__S3__AWS_SECRET_ACCESS_KEY=test
    STORAGE__S3__REGION_NAME=us-east-1

Then run:

    uv run pytest packages/rpsd-storage/ -m live_s3 -v
"""

import time

import pytest


@pytest.mark.live_s3
class TestLiveS3CompareBeforeSave:
    """
    Verify compare-before-save against a real S3-compatible endpoint.

    These mirror TestS3CompareBeforeSave in test_compare_before_save.py
    to confirm that the UUID sort-order invariant holds on real infrastructure.
    """

    def test_dedup_skips_identical_content(self, s3_live_provider):
        """Second save with same content returns deduplicated=True."""
        content = b"live test content"

        url1, meta1 = s3_live_provider.save(
            content,
            "test.txt",
            "live_user",
            "dedup_doc",
            content_type="text/plain",
        )
        assert not meta1.deduplicated

        url2, meta2 = s3_live_provider.save(
            content,
            "test.txt",
            "live_user",
            "dedup_doc",
            content_type="text/plain",
        )
        assert meta2.deduplicated
        assert url2 == url1
        assert meta2.object_id == meta1.object_id

    def test_saves_different_content(self, s3_live_provider):
        """Different content is saved normally as a new object."""
        url1, meta1 = s3_live_provider.save(
            b"live version 1",
            "test.txt",
            "live_user",
            "diff_doc",
            content_type="text/plain",
        )
        url2, meta2 = s3_live_provider.save(
            b"live version 2",
            "test.txt",
            "live_user",
            "diff_doc",
            content_type="text/plain",
        )
        assert not meta1.deduplicated
        assert not meta2.deduplicated
        assert url2 != url1

    def test_first_save_always_writes(self, s3_live_provider):
        """First save for a (who, what) pair always writes to S3."""
        url, meta = s3_live_provider.save(
            b"first live save",
            "test.txt",
            "live_user",
            "first_doc",
            content_type="text/plain",
        )
        assert url.startswith("s3://")
        assert not meta.deduplicated

    def test_different_who_what_not_compared(self, s3_live_provider):
        """Same content under different (who, what) pairs is saved independently."""
        content = b"shared live content"

        url1, _ = s3_live_provider.save(
            content,
            "test.txt",
            "alice_live",
            "shared_doc",
            content_type="text/plain",
        )
        url2, meta2 = s3_live_provider.save(
            content,
            "test.txt",
            "bob_live",
            "shared_doc",
            content_type="text/plain",
        )
        assert url2 != url1
        assert not meta2.deduplicated


@pytest.mark.live_s3
class TestLiveS3FindLatestMetadata:
    """
    Verify that _find_latest_metadata returns the correct object on real S3.

    This is the core of the sort-order invariant: bit-flipped UUID7 keys must
    sort so that the newest object appears first in an ascending S3 listing.
    """

    def test_empty_prefix_returns_none(self, s3_live_provider):
        """No previous saves -> None."""
        result = s3_live_provider._find_latest_metadata("nobody_live", "nothing")
        assert result is None

    def test_returns_newest_after_multiple_saves(self, s3_live_provider):
        """After multiple saves, _find_latest_metadata returns the newest object."""
        s3_live_provider.save(
            b"live first",
            "test.txt",
            "live_order",
            "order_doc",
            content_type="text/plain",
        )
        time.sleep(0.01)
        s3_live_provider.save(
            b"live second",
            "test.txt",
            "live_order",
            "order_doc",
            content_type="text/plain",
        )
        time.sleep(0.01)
        _, meta3 = s3_live_provider.save(
            b"live third",
            "test.txt",
            "live_order",
            "order_doc",
            content_type="text/plain",
        )

        latest = s3_live_provider._find_latest_metadata("live_order", "order_doc")
        assert latest is not None
        assert latest.hash == meta3.hash
