"""
Tests specifically for tuple functionality in storage providers.

These tests validate that the load method returns proper tuples with
content and metadata for better ergonomics and type safety.
"""

from typing import get_type_hints

import pytest

from rpsd_storage import FSStorageProvider
from rpsd_storage.provider import StorageProvider

from .test_utils import (
    create_sample_file,
    create_temp_storage_dir,
    demonstrate_typed_load_result,
    extract_content_with_types,
    process_multiple_load_results,
    validate_load_result_structure,
)


class TestTupleInterface:
    """Test that the tuple interface is properly defined."""

    def test_storage_provider_load_signature(self):
        """Test that the abstract load method returns proper tuple type hints."""
        # Check the type hints of the abstract load method
        type_hints = get_type_hints(StorageProvider.load)

        assert "url" in type_hints
        assert "return" in type_hints
        assert type_hints["url"] is str
        # The return type should be tuple[bytes, dict[str, Any]]
        return_type = str(type_hints["return"])
        assert "tuple" in return_type.lower()
        assert "bytes" in return_type
        assert "dict" in return_type


class TestTupleFunctionality:
    """Test tuple functionality with both storage providers."""

    def test_load_returns_proper_tuple_fs(self, fs_storage_provider):
        """Test that FS load method returns a properly structured tuple."""
        content, filename, mime_type = create_sample_file("json")

        # Save a file
        url, metadata = fs_storage_provider.save(
            content=content, filename=filename, content_type=mime_type
        )

        # Load with tuple result
        content_loaded, metadata_loaded = fs_storage_provider.load(url)

        # Test type-safe access
        assert isinstance(content_loaded, bytes)
        assert isinstance(metadata_loaded, dict)
        assert content_loaded == content

        # Validate tuple structure has the correct components
        result_dict = {"content": content_loaded, "metadata": metadata_loaded}
        assert validate_load_result_structure(result_dict)

    def test_load_returns_proper_tuple_s3(self, s3_storage_provider):
        """Test that S3 load method returns a properly structured tuple."""
        content, filename, mime_type = create_sample_file("json")

        # Save a file
        url, metadata = s3_storage_provider.save(
            content=content, filename=filename, content_type=mime_type
        )

        # Load with tuple result
        content_loaded, metadata_loaded = s3_storage_provider.load(url)

        # Test type-safe access
        assert isinstance(content_loaded, bytes)
        assert isinstance(metadata_loaded, dict)
        assert content_loaded == content

        # Validate tuple structure has the correct components
        result_dict = {"content": content_loaded, "metadata": metadata_loaded}
        assert validate_load_result_structure(result_dict)

    def test_extract_content_with_types_function_fs(self, fs_storage_provider):
        """Test utility function that extracts content with type safety."""
        content, filename, mime_type = create_sample_file("text")

        url, metadata = fs_storage_provider.save(
            content=content, filename=filename, content_type=mime_type
        )

        content_loaded, metadata_loaded = fs_storage_provider.load(url)

        # Create a LoadResult-like dict for the utility function
        result = {"content": content_loaded, "metadata": metadata_loaded}

        # Use the type-safe extraction function
        (
            extracted_content,
            extracted_filename,
            extracted_type,
        ) = extract_content_with_types(result)

        assert isinstance(extracted_content, bytes)
        assert isinstance(extracted_filename, str)
        assert isinstance(extracted_type, str)

        assert extracted_content == content
        assert extracted_filename == filename
        assert extracted_type == mime_type

    def test_demonstrate_tuple_load_result_function_fs(
        self, fs_storage_provider, capsys
    ):
        """Test the demonstration function that shows tuple benefits."""
        content, filename, mime_type = create_sample_file("pdf")

        url, metadata = fs_storage_provider.save(
            content=content, filename=filename, content_type=mime_type
        )

        # Run the demonstration function
        demonstrate_typed_load_result(fs_storage_provider, url)

        # Check that it printed the expected output
        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert filename in captured.out
        assert "Content size:" in captured.out
        assert "Content type:" in captured.out
        assert "Object ID:" in captured.out


class TestTupleValidation:
    """Test validation functions for tuple-based structures."""

    def test_validate_load_result_structure_valid(self):
        """Test validation with a valid tuple-based structure."""
        valid_result = {
            "content": b"test content",
            "metadata": {
                "object_id": "test-123",
                "original_filename": "test.txt",
                "content_type": "text/plain",
                "who": "test_user",
            },
        }

        assert validate_load_result_structure(valid_result) is True

    def test_validate_load_result_structure_invalid(self):
        """Test validation with invalid tuple-based structures."""
        # Missing content key
        invalid_result1 = {"metadata": {"object_id": "test-123"}}
        assert validate_load_result_structure(invalid_result1) is False

        # Missing metadata key
        invalid_result2 = {"content": b"test"}
        assert validate_load_result_structure(invalid_result2) is False

        # Wrong content type
        invalid_result3 = {
            "content": "should be bytes not string",
            "metadata": {"object_id": "test-123"},
        }
        assert validate_load_result_structure(invalid_result3) is False

        # Missing required metadata fields
        invalid_result4 = {
            "content": b"test",
            "metadata": {
                "object_id": "test-123"
            },  # Missing original_filename and content_type
        }
        assert validate_load_result_structure(invalid_result4) is False


@pytest.mark.integration
class TestTupleIntegration:
    """Integration tests for tuple functionality."""

    def test_end_to_end_tuple_workflow(self):
        """Test a complete workflow using tuples throughout."""
        with create_temp_storage_dir() as temp_dir:
            storage = FSStorageProvider(base_path=temp_dir)

            # Save multiple files
            saved_urls = []
            for file_type in ["text", "json", "csv"]:
                content, filename, mime_type = create_sample_file(file_type)
                url, metadata = storage.save(
                    content=content,
                    filename=f"test_{file_type}.{file_type}",
                    content_type=mime_type,
                    who="integration_test",
                    what=f"{file_type}_data",
                )
                saved_urls.append(url)

            # Load all files with tuples
            all_results = []
            for url in saved_urls:
                content_loaded, metadata_loaded = storage.load(url)
                result = {"content": content_loaded, "metadata": metadata_loaded}
                assert validate_load_result_structure(result)
                all_results.append(result)

            # Process results with type safety
            stats = process_multiple_load_results(all_results)

            # Validate the complete workflow
            assert stats["total_files"] == 3
            assert all(filename.startswith("test_") for filename in stats["filenames"])
            assert len(stats["content_type_distribution"]) == 3

            # Test individual extraction
            for result in all_results:
                content, filename, content_type = extract_content_with_types(result)
                assert isinstance(content, bytes)
                assert isinstance(filename, str)
                assert isinstance(content_type, str)
                assert len(content) > 0
