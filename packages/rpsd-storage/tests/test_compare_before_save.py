"""
Tests for compare-before-save functionality.

Tests the opt-in deduplication mechanism where save() checks
for existing identical content and skips the write.
"""

import os
import time

import boto3
import pytest
from moto import mock_aws
from test_utils import SampleContent

from rpsd_storage import (
    FSStorageProvider,
    S3StorageProvider,
    StorageSettings,
    get_storage_provider,
)
from rpsd_storage.metadata import StorageMetadata
from rpsd_storage.settings import FSSettings, S3Settings

# -- Fixtures -------------------------------------------------------


@pytest.fixture
def fs_dedup(temp_dir):
    """FS provider with compare_before_save enabled."""
    return FSStorageProvider(
        base_path=str(temp_dir),
        compare_before_save=True,
    )


@pytest.fixture
def s3_dedup(mock_s3_setup):
    """S3 provider with compare_before_save enabled."""
    _, bucket_name = mock_s3_setup
    return S3StorageProvider(
        bucket_name=bucket_name,
        compare_before_save=True,
    )


# -- FS deduplication tests -----------------------------------------


@pytest.mark.file
class TestFSCompareBeforeSave:
    """Test compare-before-save on FSStorageProvider."""

    def test_dedup_skips_identical_content(self, fs_dedup, temp_dir):
        """Second save with same content returns existing
        metadata with deduplicated=True."""
        content = SampleContent.SIMPLE_TEXT

        url1, meta1 = fs_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert not meta1.deduplicated

        url2, meta2 = fs_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert meta2.deduplicated
        assert url2 == url1
        assert meta2.object_id == meta1.object_id

        # Only one content file on disk
        dir_path = os.path.join(str(temp_dir), "user1", "doc")
        content_files = [f for f in os.listdir(dir_path) if not f.endswith(".meta")]
        assert len(content_files) == 1

    def test_saves_different_content(self, fs_dedup, temp_dir):
        """Different content is saved normally."""
        url1, meta1 = fs_dedup.save(
            b"version 1",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        url2, meta2 = fs_dedup.save(
            b"version 2",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert not meta1.deduplicated
        assert not meta2.deduplicated
        assert url2 != url1

        # Two content files on disk
        dir_path = os.path.join(str(temp_dir), "user1", "doc")
        content_files = [f for f in os.listdir(dir_path) if not f.endswith(".meta")]
        assert len(content_files) == 2

    def test_disabled_by_default(self, fs_storage_provider, temp_dir):
        """Without compare_before_save, duplicate saves are
        written."""
        content = SampleContent.SIMPLE_TEXT
        url1, _ = fs_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        url2, meta2 = fs_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert url2 != url1
        assert not meta2.deduplicated

    def test_first_save_always_writes(self, fs_dedup):
        """First save for a (who, what) pair always writes."""
        url, meta = fs_dedup.save(
            b"hello",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert url.startswith("file://")
        assert not meta.deduplicated

    def test_different_who_what_not_compared(self, fs_dedup, temp_dir):
        """Same content under different (who, what) is saved
        independently."""
        content = SampleContent.SIMPLE_TEXT

        url1, _ = fs_dedup.save(
            content,
            "test.txt",
            "alice",
            "doc",
            content_type="text/plain",
        )
        url2, meta2 = fs_dedup.save(
            content,
            "test.txt",
            "bob",
            "doc",
            content_type="text/plain",
        )
        assert url2 != url1
        assert not meta2.deduplicated


# -- S3 deduplication tests ------------------------------------------


@pytest.mark.s3
class TestS3CompareBeforeSave:
    """Test compare-before-save on S3StorageProvider."""

    def test_dedup_skips_identical_content(self, s3_dedup):
        """Second save with same content returns existing
        metadata with deduplicated=True."""
        content = SampleContent.SIMPLE_TEXT

        url1, meta1 = s3_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert not meta1.deduplicated

        url2, meta2 = s3_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert meta2.deduplicated
        assert url2 == url1

    def test_saves_different_content(self, s3_dedup):
        """Different content is saved normally."""
        url1, meta1 = s3_dedup.save(
            b"version 1",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        url2, meta2 = s3_dedup.save(
            b"version 2",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert not meta1.deduplicated
        assert not meta2.deduplicated
        assert url2 != url1

    def test_disabled_by_default(self, s3_storage_provider):
        """Without compare_before_save, duplicate saves are
        written."""
        content = SampleContent.SIMPLE_TEXT
        url1, _ = s3_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        url2, meta2 = s3_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert url2 != url1
        assert not meta2.deduplicated

    def test_first_save_always_writes(self, s3_dedup):
        """First save for a (who, what) pair always writes."""
        url, meta = s3_dedup.save(
            b"hello",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        assert url.startswith("s3://")
        assert not meta.deduplicated

    def test_different_who_what_not_compared(self, s3_dedup):
        """Same content under different (who, what) is saved
        independently."""
        content = SampleContent.SIMPLE_TEXT

        url1, _ = s3_dedup.save(
            content,
            "test.txt",
            "alice",
            "doc",
            content_type="text/plain",
        )
        url2, meta2 = s3_dedup.save(
            content,
            "test.txt",
            "bob",
            "doc",
            content_type="text/plain",
        )
        assert url2 != url1
        assert not meta2.deduplicated


# -- _find_latest_metadata tests -------------------------------------


@pytest.mark.file
class TestFSFindLatestMetadata:
    """Test FSStorageProvider._find_latest_metadata."""

    def test_empty_directory_returns_none(self, fs_dedup):
        """No previous saves -> None."""
        result = fs_dedup._find_latest_metadata("nobody", "nothing")
        assert result is None

    def test_returns_newest(self, fs_dedup):
        """After multiple saves, returns the newest metadata."""
        fs_dedup.save(
            b"first",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        # Small delay to ensure different timestamps/UUIDs
        time.sleep(0.01)
        _, meta2 = fs_dedup.save(
            b"second",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        time.sleep(0.01)
        _, meta3 = fs_dedup.save(
            b"third",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )

        latest = fs_dedup._find_latest_metadata("user1", "doc")
        assert latest is not None
        assert latest.object_id == meta3.object_id


@pytest.mark.s3
class TestS3FindLatestMetadata:
    """Test S3StorageProvider._find_latest_metadata."""

    def test_empty_prefix_returns_none(self, s3_dedup):
        """No previous saves -> None."""
        result = s3_dedup._find_latest_metadata("nobody", "nothing")
        assert result is None

    def test_returns_newest(self, s3_dedup):
        """After multiple saves, returns the newest metadata."""
        s3_dedup.save(
            b"first",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        time.sleep(0.01)
        s3_dedup.save(
            b"second",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )
        time.sleep(0.01)
        _, meta3 = s3_dedup.save(
            b"third",
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
        )

        latest = s3_dedup._find_latest_metadata("user1", "doc")
        assert latest is not None
        assert latest.hash == meta3.hash


# -- Metadata serialization tests ------------------------------------


class TestDeduplicatedField:
    """Test the deduplicated field on StorageMetadata."""

    def test_excluded_from_model_dump(self):
        """deduplicated should not appear in model_dump()."""
        meta = StorageMetadata(
            provider="fs",
            url="file:///tmp/test",
            content_type="text/plain",
            content_length=5,
            hash="abc123",
            who="user1",
            what="doc",
            original_filename="test.txt",
            object_id="abc.txt",
            save_stamp="20240101_120000",
            schema_version=1,
            source_url="",
            deduplicated=True,
        )
        dumped = meta.model_dump()
        assert "deduplicated" not in dumped

    def test_excluded_from_json(self):
        """deduplicated should not appear in JSON output."""
        meta = StorageMetadata(
            provider="fs",
            url="file:///tmp/test",
            content_type="text/plain",
            content_length=5,
            hash="abc123",
            who="user1",
            what="doc",
            original_filename="test.txt",
            object_id="abc.txt",
            save_stamp="20240101_120000",
            schema_version=1,
            source_url="",
            deduplicated=True,
        )
        json_str = meta.model_dump_json()
        assert "deduplicated" not in json_str

    def test_default_false(self):
        """deduplicated defaults to False."""
        meta = StorageMetadata(
            provider="fs",
            url="file:///tmp/test",
            content_type="text/plain",
            content_length=5,
            hash="abc123",
            who="user1",
            what="doc",
            original_filename="test.txt",
            object_id="abc.txt",
            save_stamp="20240101_120000",
            schema_version=1,
            source_url="",
        )
        assert meta.deduplicated is False


# -- Settings and factory tests --------------------------------------


class TestCompareBeforeSaveSettings:
    """Test the compare_before_save setting."""

    def test_default_false(self):
        """Setting defaults to False."""
        settings = StorageSettings()
        assert settings.compare_before_save is False

    def test_from_env(self, monkeypatch):
        """Setting can be set via environment variable."""
        monkeypatch.setenv("STORAGE__COMPARE_BEFORE_SAVE", "true")
        settings = StorageSettings()
        assert settings.compare_before_save is True


class TestFactoryPassesSetting:
    """Test that get_storage_provider propagates the setting."""

    def test_fs_provider_receives_setting(self, temp_dir):
        """Factory passes compare_before_save to FS provider."""
        settings = StorageSettings(
            provider="fs",
            fs=FSSettings(base_path=str(temp_dir)),
            compare_before_save=True,
        )
        provider = get_storage_provider(settings)
        assert isinstance(provider, FSStorageProvider)
        assert provider.compare_before_save is True

    @mock_aws
    def test_s3_provider_receives_setting(self):
        """Factory passes compare_before_save to S3 provider."""
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket="test-bucket")
        settings = StorageSettings(
            provider="s3",
            s3=S3Settings(bucket_name="test-bucket"),
            compare_before_save=True,
        )
        provider = get_storage_provider(settings)
        assert isinstance(provider, S3StorageProvider)
        assert provider.compare_before_save is True


# -- Per-call override tests -----------------------------------------


@pytest.mark.file
class TestFSPerCallOverride:
    """Test that compare_before_save can be overridden per save() call."""

    def test_instance_false_call_true_deduplicates(self, fs_storage_provider):
        """Instance has compare_before_save=False, but passing True per call
        enables deduplication for that call."""
        content = SampleContent.SIMPLE_TEXT

        url1, meta1 = fs_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=True,
        )
        assert not meta1.deduplicated

        url2, meta2 = fs_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=True,
        )
        assert meta2.deduplicated
        assert url2 == url1

    def test_instance_true_call_false_skips_dedup(self, fs_dedup):
        """Instance has compare_before_save=True, but passing False per call
        disables deduplication for that call."""
        content = SampleContent.SIMPLE_TEXT

        url1, meta1 = fs_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=False,
        )
        assert not meta1.deduplicated

        url2, meta2 = fs_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=False,
        )
        assert not meta2.deduplicated
        assert url2 != url1

    def test_call_none_uses_instance_setting(self, fs_dedup):
        """Passing compare_before_save=None falls back to instance setting."""
        content = SampleContent.SIMPLE_TEXT

        url1, _ = fs_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=None,
        )
        _, meta2 = fs_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=None,
        )
        # Instance has compare_before_save=True, so second save deduplicates
        assert meta2.deduplicated


@pytest.mark.s3
class TestS3PerCallOverride:
    """Test that compare_before_save can be overridden per save() call."""

    def test_instance_false_call_true_deduplicates(self, s3_storage_provider):
        """Instance has compare_before_save=False, but passing True per call
        enables deduplication for that call."""
        content = SampleContent.SIMPLE_TEXT

        url1, meta1 = s3_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=True,
        )
        assert not meta1.deduplicated

        url2, meta2 = s3_storage_provider.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=True,
        )
        assert meta2.deduplicated
        assert url2 == url1

    def test_instance_true_call_false_skips_dedup(self, s3_dedup):
        """Instance has compare_before_save=True, but passing False per call
        disables deduplication for that call."""
        content = SampleContent.SIMPLE_TEXT

        url1, meta1 = s3_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=False,
        )
        assert not meta1.deduplicated

        url2, meta2 = s3_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=False,
        )
        assert not meta2.deduplicated
        assert url2 != url1

    def test_call_none_uses_instance_setting(self, s3_dedup):
        """Passing compare_before_save=None falls back to instance setting."""
        content = SampleContent.SIMPLE_TEXT

        url1, _ = s3_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=None,
        )
        _, meta2 = s3_dedup.save(
            content,
            "test.txt",
            "user1",
            "doc",
            content_type="text/plain",
            compare_before_save=None,
        )
        # Instance has compare_before_save=True, so second save deduplicates
        assert meta2.deduplicated
