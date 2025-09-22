#!/usr/bin/env python3
"""
Metadata and Content Types - Adding Context to Your Files

Beyond just saving files, rpsd-storage lets you add rich metadata
to track important context about your data.

What you'll learn:
- How to add custom metadata (who, what, source_url)
- Why metadata matters in real applications
- How to organize files by purpose and origin
- Best practices for metadata design

This builds on concepts from 01_getting_started.py and 02_basic_usage.py
"""

import tempfile
from typing import Any

from rpsd_storage import FSStorageProvider


# Simple utilities for this example
def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """Create sample file content for demonstration."""
    samples = {
        "text": (
            b"This is a sample document for metadata demonstration.",
            "document.txt",
            "text/plain"
        ),
        "json": (
            b'{"export_type": "user_data", "count": 150}',
            "export.json",
            "application/json"
        ),
        "pdf": (b"%PDF-1.4\nSample PDF document", "report.pdf", "application/pdf"),
        "csv": (
            b"name,role,active\nAlice,developer,true\nBob,designer,true",
            "users.csv",
            "text/csv"
        ),
        "xml": (
            b'<?xml version="1.0"?><config><setting>value</setting></config>',
            "config.xml",
            "application/xml"
        ),
        "png": (
            b"\x89PNG\r\n\x1a\n" + b"Sample PNG image data",
            "image.png",
            "image/png"
        ),
        "log": (
            b"2024-01-15 10:30:00 INFO Application started",
            "app.log",
            "text/plain"
        ),
    }
    return samples[file_type]


def get_metadata_preset(preset: str) -> dict[str, Any]:
    """Get predefined metadata for demonstration."""
    presets = {
        "document": {"who": "document_processor", "what": "archived_document"},
        "data_export": {"who": "data_team", "what": "daily_export"},
        "logs": {"who": "log_collector", "what": "application_logs"},
        "config": {"who": "devops_team", "what": "config_backup"},
        "minimal": {},
    }
    return presets[preset].copy()


def print_file_info(content: bytes, filename: str, mime_type: str) -> None:
    """Print file information for demonstration."""
    size_kb = len(content) / 1024
    preview = content[:40].decode("utf-8", errors="replace")
    if len(content) > 40:
        preview += "..."
    print(f"  📄 {filename}")
    print(f"     Type: {mime_type}")
    print(f"     Size: {size_kb:.1f} KB")
    print(f"     Preview: \"{preview}\"")


def print_metadata_info(metadata: dict[str, Any]) -> None:
    """Print metadata information in a readable format."""
    if not metadata:
        print("     Metadata: (none)")
        return
    print("     Metadata:")
    for key, value in metadata.items():
        print(f"       {key}: {value}")


def demonstrate_basic_metadata():
    """Show how to add basic metadata to files."""

    print("🏷️  Adding Metadata to Your Files")
    print("=" * 33)
    print()
    print("Metadata helps you track important context:")
    print("• WHO saved the file (user, system, application)")
    print("• WHAT the file represents (purpose, content type)")
    print("• WHERE it came from (source URL, system)")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Example 1: User Document Upload
        print("Example 1: User Document Upload")
        print("-" * 32)

        content, filename, mime_type = create_sample_file("text")
        print_file_info(content, filename, mime_type)

        object_id = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="alice_johnson",              # Who uploaded this
            what="quarterly_report",          # What kind of document
            source_url="https://intranet.company.com/upload"  # Where from
        )

        print(f"   ✅ Saved with metadata: {object_id}")
        print()

        # Load it back to see the metadata
        loaded_file = storage.load(object_id)
        metadata = loaded_file["metadata"]

        print("   📋 Complete Metadata:")
        print_metadata_info(metadata)
        print()

        # Example 2: API Data Export
        print("Example 2: API Data Export")
        print("-" * 25)

        content, filename, mime_type = create_sample_file("json")
        print_file_info(content, filename, mime_type)

        object_id = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="data_pipeline",              # Automated system
            what="user_export",               # Type of export
            source_url="https://api.company.com/users"  # Source API
        )

        print(f"   ✅ Saved with metadata: {object_id}")

        loaded_file = storage.load(object_id)
        print("   📋 Complete Metadata:")
        print_metadata_info(loaded_file["metadata"])
        print()


def demonstrate_metadata_presets():
    """Show how to use predefined metadata patterns."""

    print("🎯 Using Metadata Presets")
    print("=" * 26)
    print("For common scenarios, use predefined metadata patterns:")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        scenarios = [
            ("Document Archive", "document", "pdf"),
            ("Data Export", "data_export", "json"),
            ("Log Storage", "logs", "log"),
            ("Config Backup", "config", "xml"),
        ]

        for scenario_name, preset, file_type in scenarios:
            print(f"📁 {scenario_name}")
            print("-" * (len(scenario_name) + 3))

            # Get the predefined metadata
            metadata = get_metadata_preset(preset)
            print("   Preset metadata:")
            print_metadata_info(metadata)

            # Create and save the file
            content, filename, mime_type = create_sample_file(file_type)

            object_id = storage.save(
                content=content,
                filename=filename,
                content_type=mime_type,
                **metadata  # Unpack the preset metadata
            )

            print(f"   ✅ Saved: {object_id}")
            print()


def demonstrate_metadata_benefits():
    """Show why metadata is valuable in real applications."""

    print("💡 Why Metadata Matters")
    print("=" * 22)
    print("Let's see how metadata helps in real scenarios:")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Save multiple files with different metadata
        files_data = [
            ("User upload from web app", "alice", "profile_photo", None),
            ("Automated backup", "backup_system", "database_dump", None),
            ("API data export", "data_team", "customer_export", "https://api.com/customers"),
            ("Manual document scan", "bob", "invoice_scan", "scanner_station_3"),
        ]

        saved_files = []

        print("Saving files with different origins and purposes:")
        print()

        for description, who, what, source in files_data:
            # Use appropriate file type for each scenario
            file_type = "png" if "photo" in what else "json"
            content, filename, mime_type = create_sample_file(file_type)

            # Build metadata
            metadata = {"who": who, "what": what}
            if source:
                metadata["source_url"] = source

            object_id = storage.save(
                content=content,
                filename=filename,
                content_type=mime_type,
                **metadata
            )

            saved_files.append((description, object_id))
            print(f"   📄 {description}")
            print(f"      ID: {object_id}")
            print()

        # Now demonstrate how metadata helps with organization
        print("🔍 Finding Files by Metadata")
        print("-" * 27)
        print("With metadata, you can easily categorize and find files:")
        print()

        for description, object_id in saved_files:
            loaded_file = storage.load(object_id)
            metadata = loaded_file["metadata"]

            print(f"   📁 {description}")
            print(f"      Who: {metadata.get('who', 'Unknown')}")
            print(f"      What: {metadata.get('what', 'Unknown')}")
            print(f"      When: {metadata['ingestion_timestamp']}")
            print(f"      Size: {len(loaded_file['content'])} bytes")
            print()


def demonstrate_advanced_patterns():
    """Show advanced metadata patterns."""

    print("🚀 Advanced Metadata Patterns")
    print("=" * 30)
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Pattern 1: Versioned Documents
        print("Pattern 1: Document Versioning")
        print("-" * 29)

        for version in ["v1", "v2", "v3"]:
            content, filename, mime_type = create_sample_file("text")

            object_id = storage.save(
                content=content,
                filename=f"policy_document_{version}.txt",
                content_type=mime_type,
                who="legal_team",
                what=f"policy_document_{version}",
                source_url=f"https://docs.company.com/policy/{version}"
            )

            print(f"   📄 Saved {version}: {object_id}")

        print()

        # Pattern 2: Multi-user Collaboration
        print("Pattern 2: Multi-user Data Collection")
        print("-" * 36)

        users = ["researcher_1", "researcher_2", "researcher_3"]
        for user in users:
            content, filename, mime_type = create_sample_file("csv")

            object_id = storage.save(
                content=content,
                filename=f"survey_data_{user}.csv",
                content_type=mime_type,
                who=user,
                what="survey_response",
                source_url="https://survey.company.com/submit"
            )

            print(f"   📊 Data from {user}: {object_id}")

        print()


def main():
    """Run the metadata and types demonstrations."""

    print("🏷️  Metadata and Content Types Guide")
    print("=" * 36)
    print("Learn how to add rich context to your saved files")
    print()

    demonstrate_basic_metadata()
    demonstrate_metadata_presets()
    demonstrate_metadata_benefits()
    demonstrate_advanced_patterns()

    print("🎯 Key Takeaways:")
    print("-" * 16)
    print("• Metadata adds valuable context to your files")
    print("• Use 'who', 'what', and 'source_url' for tracking origin and purpose")
    print("• Presets help standardize metadata across your application")
    print("• Good metadata makes files easier to find and organize later")
    print()
    print("📖 Next Steps:")
    print("• 04_advanced_features.py - Error handling and advanced features")


if __name__ == "__main__":
    main()
