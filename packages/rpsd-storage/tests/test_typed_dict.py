"""
Tests specifically for TypedDict functionality in storage providers.

These tests validate that the LoadResult TypedDict provides proper type safety
and structure validation for the load method return values.
"""

from typing import get_type_hints

import pytest

from rpsd_storage import FSStorageProvider
from rpsd_storage.provider import LoadResult, StorageProvider

from .test_utils import (
    create_sample_file,
    create_temp_storage_dir,
    demonstrate_typed_load_result,
    extract_content_with_types,
    process_multiple_load_results,
    validate_load_result_structure,
)


class TestTypedDictInterface:
    """Test that the TypedDict interface is properly defined."""

    def test_load_result_type_definition(self):
        """Test that LoadResult TypedDict has the correct structure."""
        # Check that LoadResult is properly defined with required keys
        type_hints = get_type_hints(LoadResult)

        assert "content" in type_hints
        assert "metadata" in type_hints
        assert type_hints["content"] is bytes
        assert str(type_hints["metadata"]).startswith("dict")

    def test_storage_provider_load_signature(self):
        """Test that the abstract load method has proper type hints."""
        # Check the type hints of the abstract load method
        type_hints = get_type_hints(StorageProvider.load)

        assert "object_id" in type_hints
        assert "return" in type_hints
        assert type_hints["object_id"] is str
        # The return type should be LoadResult (TypedDict)
        assert type_hints["return"] == LoadResult


class TestTypedDictFunctionality:
    """Test TypedDict functionality with both storage providers."""

    def test_load_returns_proper_typed_dict_fs(self, fs_storage_provider):
        """Test that FS load method returns a properly structured LoadResult."""
        content, filename, mime_type = create_sample_file("json")

        # Save a file
        object_id = fs_storage_provider.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )

        # Load with TypedDict result
        result: LoadResult = fs_storage_provider.load(object_id)

        # Validate the TypedDict structure
        assert validate_load_result_structure(result)

        # Test type-safe access
        content_from_result: bytes = result["content"]
        metadata_from_result: dict = result["metadata"]

        assert isinstance(content_from_result, bytes)
        assert isinstance(metadata_from_result, dict)
        assert content_from_result == content

    def test_load_returns_proper_typed_dict_s3(self, s3_storage_provider):
        """Test that S3 load method returns a properly structured LoadResult."""
        content, filename, mime_type = create_sample_file("json")

        # Save a file
        object_id = s3_storage_provider.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )

        # Load with TypedDict result
        result: LoadResult = s3_storage_provider.load(object_id)

        # Validate the TypedDict structure
        assert validate_load_result_structure(result)

        # Test type-safe access
        content_from_result: bytes = result["content"]
        metadata_from_result: dict = result["metadata"]

        assert isinstance(content_from_result, bytes)
        assert isinstance(metadata_from_result, dict)
        assert content_from_result == content

    def test_extract_content_with_types_function_fs(self, fs_storage_provider):
        """Test the utility function that extracts content with type safety."""
        content, filename, mime_type = create_sample_file("text")

        object_id = fs_storage_provider.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )

        result: LoadResult = fs_storage_provider.load(object_id)

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

    def test_demonstrate_typed_load_result_function_fs(
        self, fs_storage_provider, capsys
    ):
        """Test the demonstration function that shows TypedDict benefits."""
        content, filename, mime_type = create_sample_file("pdf")

        object_id = fs_storage_provider.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )

        # Run the demonstration function
        demonstrate_typed_load_result(fs_storage_provider, object_id)

        # Check that it printed the expected output
        captured = capsys.readouterr()
        assert "✅ TypedDict validation passed" in captured.out
        assert filename in captured.out
        assert "Content size:" in captured.out
        assert "Content type:" in captured.out
        assert "Object ID:" in captured.out


class TestTypedDictValidation:
    """Test validation functions for TypedDict structures."""

    def test_validate_load_result_structure_valid(self):
        """Test validation with a valid LoadResult structure."""
        valid_result: LoadResult = {
            "content": b"test content",
            "metadata": {
                "object_id": "test-123",
                "original_filename": "test.txt",
                "content_type": "text/plain",
                "who": "test_user"
            }
        }

        assert validate_load_result_structure(valid_result) is True

    def test_validate_load_result_structure_invalid(self):
        """Test validation with invalid LoadResult structures."""
        # Missing content key
        invalid_result1 = {
            "metadata": {"object_id": "test-123"}
        }
        assert validate_load_result_structure(invalid_result1) is False

        # Missing metadata key
        invalid_result2 = {
            "content": b"test"
        }
        assert validate_load_result_structure(invalid_result2) is False

        # Wrong content type
        invalid_result3 = {
            "content": "should be bytes not string",
            "metadata": {"object_id": "test-123"}
        }
        assert validate_load_result_structure(invalid_result3) is False

        # Missing required metadata fields
        invalid_result4 = {
            "content": b"test",
            "metadata": {
                "object_id": "test-123"
            }  # Missing original_filename and content_type
        }
        assert validate_load_result_structure(invalid_result4) is False


@pytest.mark.integration
class TestTypedDictIntegration:
    """Integration tests for TypedDict functionality."""

    def test_end_to_end_typed_workflow(self):
        """Test a complete workflow using TypedDict throughout."""
        with create_temp_storage_dir() as temp_dir:
            storage = FSStorageProvider(base_path=temp_dir)

            # Save multiple files
            saved_ids = []
            for file_type in ["text", "json", "csv"]:
                content, filename, mime_type = create_sample_file(file_type)
                object_id = storage.save(
                    content=content,
                    filename=f"test_{file_type}.{file_type}",
                    content_type=mime_type,
                    who="integration_test",
                    what=f"{file_type}_data"
                )
                saved_ids.append(object_id)

            # Load all files with TypedDict
            all_results: list[LoadResult] = []
            for object_id in saved_ids:
                result: LoadResult = storage.load(object_id)
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
