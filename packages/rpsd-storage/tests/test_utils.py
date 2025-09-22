"""
Test utilities for rpsd-storage tests.

This module provides test-specific utilities and imports shared utilities
from the examples module to avoid code duplication.

Test-specific utilities focus on verification and edge cases,
while shared utilities provide common data and helper functions.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

# Test-specific utilities - self-contained

class SampleContent:
    """Sample content for testing different file types."""
    SIMPLE_TEXT = b"Hello, this is a test file!"
    FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"fake PNG image data for testing"
    CONFIG_XML = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<configuration>"
        b"  <database>"
        b"    <host>localhost</host>"
        b"    <port>5432</port>"
        b"  </database>"
        b"</configuration>"
    )

    @classmethod
    def get_user_data_json(cls) -> bytes:
        return b'{"test": "data", "users": [{"name": "Test User", "id": 1}]}'


class CommonMetadata:
    """Common metadata patterns for testing."""
    MINIMAL = {}


def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """Create sample file content for testing."""
    samples = {
        "text": (SampleContent.SIMPLE_TEXT, "test.txt", "text/plain"),
        "json": (SampleContent.get_user_data_json(), "test.json", "application/json"),
        "xml": (SampleContent.CONFIG_XML, "test.xml", "application/xml"),
        "png": (SampleContent.FAKE_PNG, "test.png", "image/png"),
        "csv": (b"name,value\ntest,123\nsample,456", "test.csv", "text/csv"),
        "pdf": (b"%PDF-1.4\nTest PDF content for testing", "test.pdf", "application/pdf"),
        "log": (b"2024-01-15 10:30:00 INFO Test log entry", "test.log", "text/plain"),
    }

    if file_type not in samples:
        available = ", ".join(samples.keys())
        raise ValueError(f"Unknown file type: {file_type}. Available: {available}")

    return samples[file_type]


def get_metadata_preset(preset: str) -> dict[str, Any]:
    """Get predefined metadata for testing."""
    presets = {
        "minimal": CommonMetadata.MINIMAL,
        "basic": {"who": "test_user", "what": "test_data"},
    }

    if preset not in presets:
        raise ValueError(f"Unknown preset: {preset}")

    return presets[preset].copy()


def create_temp_storage_dir() -> tempfile.TemporaryDirectory:
    """Create temporary directory for testing."""
    return tempfile.TemporaryDirectory()


# Legacy aliases for backward compatibility with existing tests
class TestContent:
    """Legacy class for backward compatibility."""
    SIMPLE_TEXT = SampleContent.SIMPLE_TEXT
    FAKE_PNG = SampleContent.FAKE_PNG
    XML_DATA = SampleContent.CONFIG_XML

    @classmethod
    def get_json_bytes(cls) -> bytes:
        return SampleContent.get_user_data_json()

    # Additional test-specific content that's not in examples
    LOG_CONTENT = (
        b"2024-01-15 10:30:00 INFO Application started\n"
        b"2024-01-15 10:30:01 INFO User login successful"
    )

    JSON_DATA = {
        "test": "data",
        "users": [{"name": "Test User", "id": 1}]
    }


class SampleMetadata:
    """Legacy class - use CommonMetadata and get_metadata_preset() instead."""
    BASIC = {"who": "test_user", "what": "test_data"}
    FULL = {
        "who": "admin",
        "what": "configuration",
        "source_url": "https://api.example.com/config.json"
    }
    MINIMAL = {}
    USER_EXPORT = {
        "who": "data_team",
        "what": "user_export",
        "source_url": "https://api.example.com/users.csv"
    }


def create_temp_directory() -> tempfile.TemporaryDirectory:
    """
    Create a temporary directory for testing.

    Note: Consider using create_temp_storage_dir() from shared module instead.
    """
    return create_temp_storage_dir()


def create_test_file_data(content_type: str = "text") -> tuple[bytes, str, str]:
    """
    Create test file data based on content type.

    Note: This wraps create_sample_file() from shared module with additional
    test-specific content types for backward compatibility.

    Args:
        content_type: Type of content to create (text, json, xml, csv, pdf, png, log)

    Returns:
        tuple: (content_bytes, filename, mime_type)
    """
    # Try to use shared module first for common content types
    try:
        return create_sample_file(content_type)
    except ValueError:
        # Fall back to test-specific content types not in shared module
        test_specific_content = {
            "log": (TestContent.LOG_CONTENT, "application.log", "text/plain"),
        }

        if content_type in test_specific_content:
            return test_specific_content[content_type]

        # Re-raise the original error with both available types
        try:
            shared_types = ["text", "json", "csv", "xml", "pdf", "png"]
        except Exception:
            shared_types = []

        test_types = list(test_specific_content.keys())
        all_types = shared_types + test_types
        msg = f"Unknown content type: {content_type}. Available: {all_types}"
        raise ValueError(msg)


def create_test_metadata(preset: str = "basic") -> dict[str, Any]:
    """
    Create test metadata based on preset.

    Note: Consider using get_metadata_preset() from shared module instead.
    This function provides backward compatibility and test-specific presets.

    Args:
        preset: Metadata preset to use (basic, full, minimal, user_export)

    Returns:
        dict: Metadata dictionary
    """
    # Map test presets to shared presets where possible
    preset_mapping = {
        "basic": "minimal",
        "full": "document",
        "minimal": "minimal",
        "user_export": "data_export"
    }

    if preset in preset_mapping:
        try:
            return get_metadata_preset(preset_mapping[preset])
        except ValueError:
            pass

    # Fall back to legacy test-specific metadata
    preset_map = {
        "basic": SampleMetadata.BASIC,
        "full": SampleMetadata.FULL,
        "minimal": SampleMetadata.MINIMAL,
        "user_export": SampleMetadata.USER_EXPORT,
    }

    if preset not in preset_map:
        available = list(preset_map.keys())
        msg = f"Unknown preset: {preset}. Available: {available}"
        raise ValueError(msg)

    return preset_map[preset].copy()


def verify_file_content(content: bytes, expected_content_type: str) -> bool:
    """
    Verify that file content matches expected type.

    Args:
        content: File content as bytes
        expected_content_type: Expected content type

    Returns:
        bool: True if content matches expected type
    """
    if expected_content_type == "json":
        try:
            json.loads(content.decode("utf-8"))
            return True
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

    elif expected_content_type == "xml":
        return content.startswith(b"<?xml")

    elif expected_content_type == "pdf":
        return content.startswith(b"%PDF-")

    elif expected_content_type == "png":
        return content.startswith(b"\x89PNG")

    elif expected_content_type in ["text", "csv", "log"]:
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    return True  # Default: assume valid


def verify_metadata_structure(metadata: dict[str, Any]) -> bool:
    """
    Verify that metadata has the expected structure.

    Args:
        metadata: Metadata dictionary to verify

    Returns:
        bool: True if metadata structure is valid
    """
    required_fields = [
        "object_id",
        "original_filename",
        "ingestion_timestamp",
        "content_type",
    ]

    for field in required_fields:
        if field not in metadata:
            return False

    # Check optional fields exist if they should
    optional_fields = ["who", "what", "source_url"]
    for field in optional_fields:
        if field in metadata and not isinstance(metadata[field], str):
            return False

    return True


def count_files_in_directory(directory: Path, extension: str | None = None) -> int:
    """
    Count files in directory, optionally filtering by extension.

    Args:
        directory: Directory to count files in
        extension: File extension to filter by (e.g., ".txt", ".meta")

    Returns:
        int: Number of files found
    """
    if not directory.exists():
        return 0

    if extension:
        return len([f for f in directory.iterdir() if f.suffix == extension])
    else:
        return len([f for f in directory.iterdir() if f.is_file()])


# Test scenarios for comprehensive testing
TEST_SCENARIOS = [
    {
        "name": "simple_text",
        "content_type": "text",
        "metadata_preset": "basic",
        "description": "Simple text file with basic metadata",
    },
    {
        "name": "json_with_full_metadata",
        "content_type": "json",
        "metadata_preset": "full",
        "description": "JSON file with complete metadata",
    },
    {
        "name": "xml_minimal",
        "content_type": "xml",
        "metadata_preset": "minimal",
        "description": "XML file with minimal metadata",
    },
    {
        "name": "csv_export",
        "content_type": "csv",
        "metadata_preset": "user_export",
        "description": "CSV file representing a data export",
    },
    {
        "name": "binary_pdf",
        "content_type": "pdf",
        "metadata_preset": "basic",
        "description": "Binary PDF file",
    },
    {
        "name": "image_png",
        "content_type": "png",
        "metadata_preset": "minimal",
        "description": "Binary PNG image",
    },
]
