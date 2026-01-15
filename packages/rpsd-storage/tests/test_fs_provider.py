"""
Tests for FSStorageProvider.
"""

import json
from pathlib import Path

import pytest
from test_utils import (
    SampleMetadata,
    TestContent,
    count_files_in_directory,
    create_test_file_data,
    verify_file_content,
    verify_metadata_structure,
)

from rpsd_storage.fs import FSStorageProvider
from rpsd_storage.metadata import StorageMetadata


class TestFSStorageProviderInit:
    """Test FSStorageProvider initialization."""

    def test_init_with_valid_path(self, temp_dir):
        """Test initialization with a valid path."""
        provider = FSStorageProvider(base_path=str(temp_dir))
        assert provider.base_path == str(temp_dir)
        assert temp_dir.exists()

    def test_init_creates_directory(self):
        """Test that initialization creates the directory if it doesn't exist."""
        with pytest.raises(Exception, match="FS base path not configured"):
            FSStorageProvider(base_path="")

    def test_init_creates_nonexistent_directory(self, temp_dir):
        """Test that initialization creates the directory if it doesn't exist."""
        new_dir = temp_dir / "new_storage"
        provider = FSStorageProvider(base_path=str(new_dir))
        assert new_dir.exists()
        assert provider.base_path == str(new_dir)

    def test_init_with_none_path(self):
        """Test initialization with None path raises exception."""
        with pytest.raises(Exception, match="FS base path not configured"):
            FSStorageProvider(base_path=None)


@pytest.mark.fs
class TestFSStorageProviderSave:
    """Test FSStorageProvider save functionality."""

    def test_save_simple_file(self, fs_storage_provider, temp_dir):
        """Test saving a simple file."""
        content = TestContent.SIMPLE_TEXT
        filename = "test.txt"
        url, metadata = fs_storage_provider.save(
            content, filename, "testuser", "testdata", content_type="text/plain"
        )
        assert url is not None
        assert isinstance(url, str)
        assert url.startswith("file://")
        assert metadata is not None
        assert isinstance(metadata, StorageMetadata)
        assert metadata.object_id is not None
        assert count_files_in_directory(temp_dir, ".txt") == 1
        assert count_files_in_directory(temp_dir, ".meta") == 1

    def test_save_with_who_and_what(self, fs_storage_provider, temp_dir):
        """Test saving with who and what parameters."""
        content = TestContent.JSON_DATA
        filename = "data.json"
        url, metadata = fs_storage_provider.save(
            json.dumps(content).encode(),
            filename,
            "alice",
            "test_data",
            content_type="application/json",
        )
        assert "alice" in url
        assert "test_data" in url
        assert metadata.who == "alice"
        assert metadata.what == "test_data"
        alice_dir = temp_dir / "alice" / "test_data"
        assert alice_dir.exists()
        files = [f for f in alice_dir.iterdir() if f.suffix == ".json"]
        assert len(files) == 1
        metadata_files = [f for f in alice_dir.iterdir() if f.suffix == ".meta"]
        assert len(metadata_files) == 1

    def test_save_different_content_types(self, fs_storage_provider, content_type):
        """Test saving files with different content types."""
        content, filename, mime_type = create_test_file_data(content_type)
        url, metadata = fs_storage_provider.save(
            content, filename, "testuser", "testdata", content_type=mime_type
        )
        assert url is not None
        assert metadata is not None
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert content_loaded == content
        assert metadata_loaded.content_type == mime_type

    def test_save_binary_content(self, fs_storage_provider):
        """Test saving binary content."""
        content = TestContent.FAKE_PNG
        filename = "image.png"
        url, metadata = fs_storage_provider.save(
            content, filename, "testuser", "testdata", content_type="image/png"
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert content_loaded == content
        assert verify_file_content(content_loaded, "png")

    def test_save_metadata_structure(self, fs_storage_provider, temp_dir):
        """Test that saved metadata has correct structure."""
        content = TestContent.SIMPLE_TEXT
        filename = "test.txt"
        url, metadata = fs_storage_provider.save(
            content,
            filename,
            "bob",
            "documentation",
            content_type="text/plain",
            source_url="https://example.com/test.txt",
        )
        bob_dir = temp_dir / "bob" / "documentation"
        meta_files = [f for f in bob_dir.iterdir() if f.suffix == ".meta"]
        assert len(meta_files) == 1
        with open(meta_files[0]) as f:
            metadata_from_file = json.load(f)
        assert verify_metadata_structure(metadata_from_file)
        assert metadata_from_file["object_id"] == metadata.object_id
        assert metadata_from_file["original_filename"] == filename
        assert metadata_from_file["content_type"] == "text/plain"
        assert metadata_from_file["source_url"] == "https://example.com/test.txt"
        assert metadata_from_file["who"] == "bob"
        assert metadata_from_file["what"] == "documentation"

    def test_save_without_filename(self, fs_storage_provider):
        """Test saving without providing filename."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = fs_storage_provider.save(
            content, None, "testuser", "testdata", content_type="text/plain"
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert metadata_loaded.original_filename == "unknown"

    def test_save_filename_without_extension(self, fs_storage_provider):
        """Test saving with filename that has no extension."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = fs_storage_provider.save(
            content, "testfile", "testuser", "testdata", content_type="text/plain"
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert metadata_loaded.original_filename == "testfile"
        # Should use extension from content_type (text/plain -> .txt)
        files = [f for f in Path(fs_storage_provider.base_path).rglob("*.txt")]
        assert len(files) == 1


@pytest.mark.fs
class TestFSStorageProviderLoad:
    """Test FSStorageProvider load functionality."""

    def test_load_saved_file(
        self, fs_storage_provider, sample_content, sample_metadata
    ):
        """Test loading a previously saved file."""
        url, metadata = fs_storage_provider.save(
            sample_content["content"],
            sample_content["filename"],
            "testuser",
            "testdata",
            content_type=sample_content["mime_type"],
            **sample_metadata,
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert content_loaded == sample_content["content"]
        assert verify_metadata_structure(metadata_loaded)

    def test_load_different_content_types(self, fs_storage_provider, test_scenario):
        """Test loading files with different content types."""
        url, metadata = fs_storage_provider.save(
            test_scenario["content"],
            test_scenario["filename"],
            "testuser",
            "testdata",
            content_type=test_scenario["mime_type"],
            **test_scenario["metadata"],
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert content_loaded == test_scenario["content"]
        assert metadata_loaded.content_type == test_scenario["mime_type"]
        assert verify_file_content(content_loaded, test_scenario["content_type"])

    def test_load_with_who_what_organization(self, fs_storage_provider):
        """Test loading files that are organized by who/what structure."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = fs_storage_provider.save(
            content, "test.txt", "alice", "documentation", content_type="text/plain"
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert content_loaded == content
        assert metadata_loaded.who == "alice"
        assert metadata_loaded.what == "documentation"

    def test_load_preserves_metadata(self, fs_storage_provider):
        """Test that load preserves all metadata fields."""
        content = TestContent.JSON_DATA
        metadata = SampleMetadata.FULL.copy()
        url, save_metadata = fs_storage_provider.save(
            json.dumps(content).encode(),
            "data.json",
            "testuser",
            "testdata",
            content_type="application/json",
            **metadata,
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        for key, value in metadata.items():
            assert getattr(metadata_loaded, key) == value

    @pytest.mark.error_handling
    def test_load_nonexistent_url(self, fs_storage_provider):
        """Test loading with non-existent URL raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Content file not found"):
            fs_storage_provider.load("file:///non/existent/path.txt")

    @pytest.mark.error_handling
    def test_load_with_missing_metadata_file(self, fs_storage_provider, temp_dir):
        """Test loading when metadata file is missing."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = fs_storage_provider.save(
            content, "test.txt", "testuser", "testdata", content_type="text/plain"
        )
        meta_files = [f for f in temp_dir.rglob("*.meta")]
        assert len(meta_files) == 1
        meta_files[0].unlink()
        with pytest.raises(FileNotFoundError, match="Metadata file not found"):
            fs_storage_provider.load(url)

    @pytest.mark.error_handling
    def test_load_with_corrupted_metadata_file(self, fs_storage_provider, temp_dir):
        """Test loading when metadata file is corrupted."""
        content = TestContent.SIMPLE_TEXT
        url, metadata = fs_storage_provider.save(
            content, "test.txt", "testuser", "testdata", content_type="text/plain"
        )
        meta_files = [f for f in temp_dir.rglob("*.meta")]
        assert len(meta_files) == 1
        with open(meta_files[0], "w") as f:
            f.write("invalid json content")
        with pytest.raises(Exception, match="Invalid metadata file"):
            fs_storage_provider.load(url)


@pytest.mark.fs
@pytest.mark.integration
class TestFSStorageProviderIntegration:
    """Integration tests for FSStorageProvider."""

    def test_save_load_roundtrip(self, fs_storage_provider):
        """Test complete save/load roundtrip."""
        content = TestContent.get_json_bytes()
        filename = "roundtrip.json"
        url, metadata = fs_storage_provider.save(
            content,
            filename,
            "integration_test",
            "roundtrip_data",
            content_type="application/json",
            source_url="https://api.example.com/data",
        )
        content_loaded, metadata_loaded = fs_storage_provider.load(url)
        assert content_loaded == content
        assert metadata_loaded.original_filename == filename
        assert metadata_loaded.content_type == "application/json"
        assert metadata_loaded.source_url == "https://api.example.com/data"
        assert metadata_loaded.who == "integration_test"
        assert metadata_loaded.what == "roundtrip_data"
        assert metadata_loaded.object_id == metadata.object_id

    def test_multiple_files_different_scenarios(self, fs_storage_provider):
        """Test handling multiple files with different scenarios."""
        from test_utils import (
            TEST_SCENARIOS,
            create_test_file_data,
            create_test_metadata,
        )

        saved_files = []
        for scenario in TEST_SCENARIOS[:3]:
            content, filename, mime_type = create_test_file_data(
                scenario["content_type"]
            )
            metadata = create_test_metadata(scenario["metadata_preset"])
            url, save_metadata = fs_storage_provider.save(
                content,
                filename,
                "testuser",
                "testdata",
                content_type=mime_type,
                **metadata,
            )
            saved_files.append({"url": url, "content": content, "scenario": scenario})
        assert len(saved_files) == 3
        for file_data in saved_files:
            url = file_data["url"]
            original_content = file_data["content"]
            content_loaded, metadata_loaded = fs_storage_provider.load(url)
            assert content_loaded == original_content

    def test_concurrent_saves(self, fs_storage_provider):
        """Test that concurrent saves don't interfere with each other."""
        contents = [
            (TestContent.SIMPLE_TEXT, "file1.txt", "text/plain"),
            (TestContent.get_json_bytes(), "file2.json", "application/json"),
            (TestContent.XML_DATA, "file3.xml", "application/xml"),
        ]
        urls = []
        for i, (content, filename, content_type) in enumerate(contents):
            url, metadata = fs_storage_provider.save(
                content,
                filename,
                f"user_{i}",
                f"test_data_{i}",
                content_type=content_type,
            )
            urls.append(url)
        for i, url in enumerate(urls):
            content_loaded, metadata_loaded = fs_storage_provider.load(url)
            assert content_loaded == contents[i][0]
            assert metadata_loaded.who == f"user_{i}"
            assert metadata_loaded.what == f"test_data_{i}"

    def test_directory_structure_creation(self, temp_dir):
        """Test that directory structure is properly created."""
        nested_path = temp_dir / "nested" / "storage" / "path"
        provider = FSStorageProvider(base_path=str(nested_path))
        assert nested_path.exists()
        assert nested_path.is_dir()
        url, metadata = provider.save(
            TestContent.SIMPLE_TEXT,
            "test.txt",
            "testuser",
            "testdata",
            content_type="text/plain",
        )
        content_loaded, metadata_loaded = provider.load(url)
        assert content_loaded == TestContent.SIMPLE_TEXT
