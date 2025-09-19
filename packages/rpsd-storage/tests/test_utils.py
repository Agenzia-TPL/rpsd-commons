"""
Shared test utilities for rpsd-storage.

This module provides common utilities that can be used by both tests and examples
to avoid code duplication while maintaining separation of concerns.
"""

import json
import tempfile
from pathlib import Path
from typing import Any


class TestContent:
    """Container for test content with various formats."""

    # Text content samples
    SIMPLE_TEXT = b"Hello, this is a test file!"
    LOG_CONTENT = (
        b"2024-01-15 10:30:00 INFO Application started\n"
        b"2024-01-15 10:30:01 INFO User login successful"
    )
    MULTILINE_TEXT = b"""This is a multi-line document.
It contains several lines of text.
Each line serves as a test case.
End of document."""

    # Structured data samples
    JSON_DATA = {
        "users": [
            {"name": "Alice", "age": 30, "city": "New York"},
            {"name": "Bob", "age": 25, "city": "Los Angeles"},
        ],
        "metadata": {"version": "1.0", "created": "2024-01-15"},
    }

    CSV_DATA = b"name,age,city\nJohn,30,New York\nJane,25,Los Angeles\nBob,35,Chicago"

    XML_DATA = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<root><message>Hello World</message>"
        b"<timestamp>2024-01-15</timestamp></root>"
    )

    # Binary content samples
    FAKE_PDF = b"%PDF-1.4\nfake PDF content for demonstration purposes"
    FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"fake PNG image data for testing"

    @classmethod
    def get_json_bytes(cls) -> bytes:
        """Get JSON data as bytes."""
        return json.dumps(cls.JSON_DATA).encode("utf-8")


class SampleMetadata:
    """Container for sample metadata configurations."""

    BASIC = {"who": "test_user", "what": "test_data"}

    FULL = {
        "who": "admin",
        "what": "configuration",
        "source_url": "https://api.example.com/config.json",
    }

    MINIMAL = {}

    USER_EXPORT = {
        "who": "data_team",
        "what": "user_export",
        "source_url": "https://api.example.com/users.csv",
    }


def create_temp_directory() -> tempfile.TemporaryDirectory:
    """
    Create a temporary directory for testing.

    Returns:
        TemporaryDirectory: Context manager for temporary directory
    """
    return tempfile.TemporaryDirectory()


def create_test_file_data(content_type: str = "text") -> tuple[bytes, str, str]:
    """
    Create test file data based on content type.

    Args:
        content_type: Type of content to create (text, json, xml, csv, pdf, png)

    Returns:
        tuple: (content_bytes, filename, mime_type)
    """
    content_map = {
        "text": (TestContent.SIMPLE_TEXT, "test.txt", "text/plain"),
        "log": (TestContent.LOG_CONTENT, "application.log", "text/plain"),
        "multiline": (TestContent.MULTILINE_TEXT, "document.txt", "text/plain"),
        "json": (TestContent.get_json_bytes(), "data.json", "application/json"),
        "xml": (TestContent.XML_DATA, "data.xml", "application/xml"),
        "csv": (TestContent.CSV_DATA, "users.csv", "text/csv"),
        "pdf": (TestContent.FAKE_PDF, "document.pdf", "application/pdf"),
        "png": (TestContent.FAKE_PNG, "image.png", "image/png"),
    }

    if content_type not in content_map:
        available = list(content_map.keys())
        msg = f"Unknown content type: {content_type}. Available: {available}"
        raise ValueError(msg)

    return content_map[content_type]


def create_test_metadata(preset: str = "basic") -> dict[str, Any]:
    """
    Create test metadata based on preset.

    Args:
        preset: Metadata preset to use (basic, full, minimal, user_export)

    Returns:
        dict: Metadata dictionary
    """
    preset_map = {
        "basic": SampleMetadata.BASIC,
        "full": SampleMetadata.FULL,
        "minimal": SampleMetadata.MINIMAL,
        "user_export": SampleMetadata.USER_EXPORT,
    }

    if preset not in preset_map:
        raise ValueError(
            f"Unknown preset: {preset}. Available: {list(preset_map.keys())}"
        )

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
