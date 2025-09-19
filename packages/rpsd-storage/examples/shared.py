"""
Shared utilities for rpsd-storage examples and tests.

This module provides common data samples, utility functions, and helpers
that can be used by both examples (for demonstration) and tests (for verification).
"""

import json
import tempfile
from typing import Any


class SampleContent:
    """Sample content for demonstrating different file types and use cases."""

    # Text files - common in document processing
    SIMPLE_TEXT = b"Hello, this is a sample document!"

    ARTICLE = b"""Understanding Cloud Storage

Cloud storage has revolutionized how we handle data. This article explores
the key benefits and considerations when choosing a storage solution.

Key advantages include:
- Scalability and flexibility
- Cost-effective pricing models
- Built-in redundancy and backup
- Global accessibility

When evaluating storage providers, consider factors like security,
compliance requirements, and integration capabilities."""

    LOG_ENTRY = (
        b"2024-01-15 10:30:00 INFO Application started successfully\n"
        b"2024-01-15 10:30:01 INFO Database connection established\n"
        b"2024-01-15 10:30:02 INFO Ready to accept requests"
    )

    # Structured data - common in data processing pipelines
    USER_DATA = {
        "users": [
            {"id": 1, "name": "Alice Johnson", "role": "developer", "active": True},
            {"id": 2, "name": "Bob Smith", "role": "designer", "active": True},
            {"id": 3, "name": "Carol Davis", "role": "manager", "active": False},
        ],
        "metadata": {
            "export_date": "2024-01-15",
            "version": "1.2",
            "total_count": 3
        }
    }

    # CSV data - common in data analysis
    SALES_DATA = (
        b"date,product,amount,region\n"
        b"2024-01-01,Widget A,1500.00,North\n"
        b"2024-01-01,Widget B,2300.50,South\n"
        b"2024-01-02,Widget A,1200.75,East\n"
        b"2024-01-02,Widget C,950.25,West"
    )

    # Configuration files - common in application deployment
    CONFIG_XML = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<configuration>"
        b"  <database>"
        b"    <host>localhost</host>"
        b"    <port>5432</port>"
        b"    <name>myapp</name>"
        b"  </database>"
        b"  <cache>"
        b"    <enabled>true</enabled>"
        b"    <ttl>3600</ttl>"
        b"  </cache>"
        b"</configuration>"
    )

    # Binary files - document and media processing
    PDF_DOCUMENT = b"%PDF-1.4\nSample PDF content for demonstration"
    IMAGE_DATA = b"\x89PNG\r\n\x1a\n" + b"Sample PNG image data"
    FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"fake PNG image data for testing"

    @classmethod
    def get_user_data_json(cls) -> bytes:
        """Get user data as formatted JSON bytes."""
        return json.dumps(cls.USER_DATA, indent=2).encode("utf-8")


class CommonMetadata:
    """Common metadata patterns for different use cases."""

    # Document archival
    DOCUMENT_ARCHIVE = {
        "who": "document_processor",
        "what": "archived_document",
        "source_url": "https://intranet.company.com/docs/report.pdf"
    }

    # Data export/backup
    DATA_EXPORT = {
        "who": "data_team",
        "what": "daily_export",
        "source_url": "https://api.company.com/export/users"
    }

    # Log file storage
    LOG_STORAGE = {
        "who": "log_collector",
        "what": "application_logs"
    }

    # Configuration backup
    CONFIG_BACKUP = {
        "who": "devops_team",
        "what": "config_backup",
        "source_url": "https://config.company.com/prod/app.xml"
    }

    # Minimal metadata (for simple use cases)
    MINIMAL = {}


def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """
    Create sample file content for examples and tests.

    Args:
        file_type: Type of file to create (text, json, csv, xml, pdf, png, log)

    Returns:
        tuple: (content_bytes, suggested_filename, mime_type)

    Example:
        content, filename, mime_type = create_sample_file("json")
        # content = b'{"users": [...], "metadata": {...}}'
        # filename = "users.json"
        # mime_type = "application/json"
    """
    samples = {
        "text": (SampleContent.ARTICLE, "article.txt", "text/plain"),
        "json": (SampleContent.get_user_data_json(), "users.json", "application/json"),
        "csv": (SampleContent.SALES_DATA, "sales.csv", "text/csv"),
        "xml": (SampleContent.CONFIG_XML, "config.xml", "application/xml"),
        "pdf": (SampleContent.PDF_DOCUMENT, "document.pdf", "application/pdf"),
        "png": (SampleContent.IMAGE_DATA, "image.png", "image/png"),
        "log": (SampleContent.LOG_ENTRY, "app.log", "text/plain"),
    }

    if file_type not in samples:
        available = ", ".join(samples.keys())
        msg = f"Unknown file type: {file_type}. Available: {available}"
        raise ValueError(msg)

    return samples[file_type]


def get_metadata_preset(preset: str) -> dict[str, Any]:
    """
    Get predefined metadata for common use cases.

    Args:
        preset: Metadata preset (document, data_export, logs, config, minimal)

    Returns:
        dict: Metadata dictionary ready to use with save()

    Example:
        metadata = get_metadata_preset("data_export")
        # Returns: {"who": "data_team", "what": "daily_export", ...}
    """
    presets = {
        "document": CommonMetadata.DOCUMENT_ARCHIVE,
        "data_export": CommonMetadata.DATA_EXPORT,
        "logs": CommonMetadata.LOG_STORAGE,
        "config": CommonMetadata.CONFIG_BACKUP,
        "minimal": CommonMetadata.MINIMAL,
    }

    if preset not in presets:
        available = ", ".join(presets.keys())
        msg = f"Unknown preset: {preset}. Available: {available}"
        raise ValueError(msg)

    return presets[preset].copy()


def create_temp_storage_dir() -> tempfile.TemporaryDirectory:
    """
    Create a temporary directory for storage examples.

    Returns:
        TemporaryDirectory: Context manager for cleanup

    Example:
        with create_temp_storage_dir() as temp_dir:
            storage = FSStorageProvider(base_path=temp_dir)
            # ... use storage ...
        # Directory automatically cleaned up
    """
    return tempfile.TemporaryDirectory()


def print_file_info(content: bytes, filename: str, mime_type: str) -> None:
    """
    Print helpful information about a file for examples.

    Args:
        content: File content as bytes
        filename: Original filename
        mime_type: MIME type of the content
    """
    size_kb = len(content) / 1024
    content_preview = content[:100]

    # Try to decode for text preview
    try:
        preview_text = content_preview.decode("utf-8")
        if len(content) > 100:
            preview_text += "..."
        preview = f'"{preview_text}"'
    except UnicodeDecodeError:
        preview = f"<binary data, {len(content)} bytes>"

    print(f"  📄 {filename}")
    print(f"     Type: {mime_type}")
    print(f"     Size: {size_kb:.1f} KB")
    print(f"     Preview: {preview}")


def print_metadata_info(metadata: dict[str, Any]) -> None:
    """
    Print metadata information in a readable format.

    Args:
        metadata: Metadata dictionary to display
    """
    if not metadata:
        print("     Metadata: (none)")
        return

    print("     Metadata:")
    for key, value in metadata.items():
        print(f"       {key}: {value}")
