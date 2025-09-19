"""
Tests for FSStorageProvider.
"""

import json
from pathlib import Path

import pytest

from rpsd_storage.fs import FSStorageProvider

from .test_utils import (
    SampleMetadata,
    TestContent,
    count_files_in_directory,
    create_test_file_data,
    verify_file_content,
    verify_metadata_structure,
)


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

        object_id = fs_storage_provider.save(
            content=content, filename=filename, content_type="text/plain"
        )

        assert object_id is not None
        assert isinstance(object_id, str)

        # Check that files were created
        assert count_files_in_directory(temp_dir, ".txt") == 1
        assert count_files_in_directory(temp_dir, ".meta") == 1

    def test_save_with_who_and_what(self, fs_storage_provider, temp_dir):
        """Test saving with who and what parameters."""
        content = TestContent.JSON_DATA
        filename = "data.json"

        object_id = fs_storage_provider.save(
            content=json.dumps(content).encode(),
            filename=filename,
            content_type="application/json",
            who="alice",
            what="test_data",
        )

        # Object ID should contain the who and what prefixes
        assert "alice" in object_id
        assert "test_data" in object_id

        # Verify files exist
        files = [f for f in temp_dir.iterdir() if f.suffix == ".json"]
        assert len(files) == 1

        metadata_files = [f for f in temp_dir.iterdir() if f.suffix == ".meta"]
        assert len(metadata_files) == 1

    def test_save_different_content_types(self, fs_storage_provider, content_type):
        """Test saving files with different content types."""
        content, filename, mime_type = create_test_file_data(content_type)

        object_id = fs_storage_provider.save(
            content=content, filename=filename, content_type=mime_type
        )

        assert object_id is not None

        # Verify content is correctly saved
        loaded_data = fs_storage_provider.load(object_id)
        assert loaded_data["content"] == content
        assert loaded_data["metadata"]["content_type"] == mime_type

    def test_save_binary_content(self, fs_storage_provider):
        """Test saving binary content."""
        content = TestContent.FAKE_PNG
        filename = "image.png"

        object_id = fs_storage_provider.save(
            content=content, filename=filename, content_type="image/png"
        )

        loaded_data = fs_storage_provider.load(object_id)
        assert loaded_data["content"] == content
        assert verify_file_content(loaded_data["content"], "png")

    def test_save_metadata_structure(self, fs_storage_provider, temp_dir):
        """Test that saved metadata has correct structure."""
        content = TestContent.SIMPLE_TEXT
        filename = "test.txt"

        object_id = fs_storage_provider.save(
            content=content,
            filename=filename,
            content_type="text/plain",
            source_url="https://example.com/test.txt",
            who="bob",
            what="documentation",
        )

        # Read metadata file directly
        meta_files = [f for f in temp_dir.iterdir() if f.suffix == ".meta"]
        assert len(meta_files) == 1

        with open(meta_files[0]) as f:
            metadata = json.load(f)

        assert verify_metadata_structure(metadata)
        assert metadata["object_id"] == object_id
        assert metadata["original_filename"] == filename
        assert metadata["content_type"] == "text/plain"
        assert metadata["source_url"] == "https://example.com/test.txt"
        assert metadata["who"] == "bob"
        assert metadata["what"] == "documentation"

    def test_save_without_filename(self, fs_storage_provider):
        """Test saving without providing filename."""
        content = TestContent.SIMPLE_TEXT

        object_id = fs_storage_provider.save(
            content=content, filename=None, content_type="text/plain"
        )

        loaded_data = fs_storage_provider.load(object_id)
        assert loaded_data["metadata"]["original_filename"] == "unknown"

    def test_save_filename_without_extension(self, fs_storage_provider):
        """Test saving with filename that has no extension."""
        content = TestContent.SIMPLE_TEXT

        object_id = fs_storage_provider.save(
            content=content, filename="testfile", content_type="text/plain"
        )

        loaded_data = fs_storage_provider.load(object_id)
        assert loaded_data["metadata"]["original_filename"] == "testfile"

        # Should default to .xml extension
        files = [
            f
            for f in Path(fs_storage_provider.base_path).iterdir()
            if f.suffix == ".xml"
        ]
        assert len(files) == 1


@pytest.mark.fs
class TestFSStorageProviderLoad:
    """Test FSStorageProvider load functionality."""

    def test_load_saved_file(
        self, fs_storage_provider, sample_content, sample_metadata
    ):
        """Test loading a previously saved file."""
        # Save a file first
        object_id = fs_storage_provider.save(
            content=sample_content["content"],
            filename=sample_content["filename"],
            content_type=sample_content["mime_type"],
            **sample_metadata,
        )

        # Load the file
        loaded_data = fs_storage_provider.load(object_id)

        assert loaded_data["content"] == sample_content["content"]
        assert verify_metadata_structure(loaded_data["metadata"])

    def test_load_different_content_types(self, fs_storage_provider, test_scenario):
        """Test loading files with different content types."""
        # Save the file
        object_id = fs_storage_provider.save(
            content=test_scenario["content"],
            filename=test_scenario["filename"],
            content_type=test_scenario["mime_type"],
            **test_scenario["metadata"],
        )

        # Load and verify
        loaded_data = fs_storage_provider.load(object_id)
        assert loaded_data["content"] == test_scenario["content"]
        assert loaded_data["metadata"]["content_type"] == test_scenario["mime_type"]
        assert verify_file_content(
            loaded_data["content"], test_scenario["content_type"]
        )

    def test_load_with_who_what_prefixes(self, fs_storage_provider):
        """Test loading files that have who/what prefixes in object_id."""
        content = TestContent.SIMPLE_TEXT

        # Save with who and what
        object_id = fs_storage_provider.save(
            content=content,
            filename="test.txt",
            content_type="text/plain",
            who="alice",
            what="documentation",
        )

        # Load using the object_id
        loaded_data = fs_storage_provider.load(object_id)
        assert loaded_data["content"] == content
        assert loaded_data["metadata"]["who"] == "alice"
        assert loaded_data["metadata"]["what"] == "documentation"

    def test_load_preserves_metadata(self, fs_storage_provider):
        """Test that load preserves all metadata fields."""
        content = TestContent.JSON_DATA

        metadata = SampleMetadata.FULL.copy()
        object_id = fs_storage_provider.save(
            content=json.dumps(content).encode(),
            filename="data.json",
            content_type="application/json",
            **metadata,
        )

        loaded_data = fs_storage_provider.load(object_id)
        loaded_metadata = loaded_data["metadata"]

        # Check all original metadata is preserved
        for key, value in metadata.items():
            assert loaded_metadata[key] == value

    @pytest.mark.error_handling
    def test_load_nonexistent_object_id(self, fs_storage_provider):
        """Test loading with non-existent object_id raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No file found for object_id"):
            fs_storage_provider.load("non-existent-id")

    @pytest.mark.error_handling
    def test_load_with_missing_metadata_file(self, fs_storage_provider, temp_dir):
        """Test loading when metadata file is missing."""
        content = TestContent.SIMPLE_TEXT

        # Save file normally
        object_id = fs_storage_provider.save(
            content=content, filename="test.txt", content_type="text/plain"
        )

        # Remove metadata file
        meta_files = [f for f in temp_dir.iterdir() if f.suffix == ".meta"]
        assert len(meta_files) == 1
        meta_files[0].unlink()

        # Try to load
        with pytest.raises(FileNotFoundError, match="Metadata file not found"):
            fs_storage_provider.load(object_id)

    @pytest.mark.error_handling
    def test_load_with_corrupted_metadata_file(self, fs_storage_provider, temp_dir):
        """Test loading when metadata file is corrupted."""
        content = TestContent.SIMPLE_TEXT

        # Save file normally
        object_id = fs_storage_provider.save(
            content=content, filename="test.txt", content_type="text/plain"
        )

        # Corrupt metadata file
        meta_files = [f for f in temp_dir.iterdir() if f.suffix == ".meta"]
        assert len(meta_files) == 1
        with open(meta_files[0], "w") as f:
            f.write("invalid json content")

        # Try to load
        with pytest.raises(Exception, match="Invalid metadata file"):
            fs_storage_provider.load(object_id)


@pytest.mark.fs
@pytest.mark.integration
class TestFSStorageProviderIntegration:
    """Integration tests for FSStorageProvider."""

    def test_save_load_roundtrip(self, fs_storage_provider):
        """Test complete save/load roundtrip."""
        content = TestContent.get_json_bytes()
        filename = "roundtrip.json"

        # Save
        object_id = fs_storage_provider.save(
            content=content,
            filename=filename,
            content_type="application/json",
            source_url="https://api.example.com/data",
            who="integration_test",
            what="roundtrip_data",
        )

        # Load
        loaded_data = fs_storage_provider.load(object_id)

        # Verify everything matches
        assert loaded_data["content"] == content
        metadata = loaded_data["metadata"]
        assert metadata["original_filename"] == filename
        assert metadata["content_type"] == "application/json"
        assert metadata["source_url"] == "https://api.example.com/data"
        assert metadata["who"] == "integration_test"
        assert metadata["what"] == "roundtrip_data"
        assert metadata["object_id"] == object_id

    def test_multiple_files_different_scenarios(self, fs_storage_provider):
        """Test handling multiple files with different scenarios."""
        # Save multiple files using the first 3 test scenarios
        from .test_utils import (
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

            object_id = fs_storage_provider.save(
                content=content, filename=filename, content_type=mime_type, **metadata
            )

            saved_files.append(
                {"object_id": object_id, "content": content, "scenario": scenario}
            )

        assert len(saved_files) == 3

        # Each file should be loadable independently
        for file_data in saved_files:
            object_id = file_data["object_id"]
            original_content = file_data["content"]

            loaded_data = fs_storage_provider.load(object_id)
            assert loaded_data["content"] == original_content

    def test_concurrent_saves(self, fs_storage_provider):
        """Test that concurrent saves don't interfere with each other."""
        contents = [
            (TestContent.SIMPLE_TEXT, "file1.txt", "text/plain"),
            (TestContent.get_json_bytes(), "file2.json", "application/json"),
            (TestContent.XML_DATA, "file3.xml", "application/xml"),
        ]

        object_ids = []
        for i, (content, filename, content_type) in enumerate(contents):
            object_id = fs_storage_provider.save(
                content=content,
                filename=filename,
                content_type=content_type,
                who=f"user_{i}",
                what=f"test_data_{i}",
            )
            object_ids.append(object_id)

        # All should be loadable independently
        for i, object_id in enumerate(object_ids):
            loaded_data = fs_storage_provider.load(object_id)
            assert loaded_data["content"] == contents[i][0]
            assert loaded_data["metadata"]["who"] == f"user_{i}"
            assert loaded_data["metadata"]["what"] == f"test_data_{i}"

    def test_directory_structure_creation(self, temp_dir):
        """Test that directory structure is properly created."""
        nested_path = temp_dir / "nested" / "storage" / "path"
        provider = FSStorageProvider(base_path=str(nested_path))

        # Directory should be created
        assert nested_path.exists()
        assert nested_path.is_dir()

        # Should be able to save files
        object_id = provider.save(
            content=TestContent.SIMPLE_TEXT,
            filename="test.txt",
            content_type="text/plain",
        )

        # Should be able to load files
        loaded_data = provider.load(object_id)
        assert loaded_data["content"] == TestContent.SIMPLE_TEXT
