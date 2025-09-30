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
from rpsd_storage.metadata import StorageMetadata


def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """Create sample file content for demonstration."""
    samples = {
        "text": (
            b"This is a sample document for metadata demonstration.",
            "document.txt",
            "text/plain",
        ),
        "json": (
            b'{"export_type": "user_data", "count": 150}',
            "export.json",
            "application/json",
        ),
        "pdf": (b"%PDF-1.4\nSample PDF document", "report.pdf", "application/pdf"),
        "csv": (
            b"name,role,active\nAlice,developer,true\nBob,designer,true",
            "users.csv",
            "text/csv",
        ),
        "xml": (
            b'<?xml version="1.0"?><config><setting>value</setting></config>',
            "config.xml",
            "application/xml",
        ),
        "png": (
            b"\x89PNG\r\n\x1a\n" + b"Sample PNG image data",
            "image.png",
            "image/png",
        ),
        "log": (
            b"2024-01-15 10:30:00 INFO Application started",
            "app.log",
            "text/plain",
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
    print(f'     Preview: "{preview}"')


def print_metadata_info(metadata: StorageMetadata) -> None:
    """Print metadata information in a readable format."""
    print("     Metadata:")
    # Display key metadata fields
    print(f"       provider: {metadata.provider}")
    print(f"       who: {metadata.who}")
    print(f"       what: {metadata.what}")
    print(f"       original_filename: {metadata.original_filename}")
    print(f"       content_type: {metadata.content_type}")
    print(f"       content_length: {metadata.content_length}")
    print(f"       object_id: {metadata.object_id}")
    print(f"       ingestion_timestamp: {metadata.ingestion_timestamp}")
    print(f"       source_url: {metadata.source_url}")
    if metadata.custom_metadata:
        print(f"       custom_metadata: {metadata.custom_metadata}")


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
        print("Example 1: User Document Upload")
        print("-" * 32)
        content, filename, mime_type = create_sample_file("text")
        print_file_info(content, filename, mime_type)
        url, metadata = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="alice_johnson",
            what="quarterly_report",
            source_url="https://intranet.company.com/upload",
        )
        print(f"   ✅ Saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print()
        content_loaded, metadata_loaded = storage.load(url)
        print("   📋 Complete Metadata:")
        print_metadata_info(metadata_loaded)
        print()
        print("Example 2: API Data Export")
        print("-" * 25)
        content, filename, mime_type = create_sample_file("json")
        print_file_info(content, filename, mime_type)
        url, metadata = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="data_pipeline",
            what="user_export",
            source_url="https://api.company.com/users",
        )
        print(f"   ✅ Saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        content_loaded, metadata_loaded = storage.load(url)
        print("   📋 Complete Metadata:")
        print_metadata_info(metadata_loaded)
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
            metadata = get_metadata_preset(preset)
            print("   Preset metadata:")
            for key, value in metadata.items():
                print(f"       {key}: {value}")
            content, filename, mime_type = create_sample_file(file_type)
            url, save_metadata = storage.save(
                content=content, filename=filename, content_type=mime_type, **metadata
            )
            print(f"   ✅ Saved: {url}")
            print(f"       Object ID: {save_metadata.object_id}")
            print()


def demonstrate_metadata_benefits():
    """Show why metadata is valuable in real applications."""
    print("💡 Why Metadata Matters")
    print("=" * 22)
    print("Let's see how metadata helps in real scenarios:")
    print()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)
        files_data = [
            ("User upload from web app", "alice", "profile_photo", None),
            ("Automated backup", "backup_system", "database_dump", None),
            (
                "API data export",
                "data_team",
                "customer_export",
                "https://api.com/customers",
            ),
            ("Manual document scan", "bob", "invoice_scan", "scanner_station_3"),
        ]
        saved_files = []
        print("Saving files with different origins and purposes:")
        print()
        for description, who, what, source in files_data:
            file_type = "png" if "photo" in what else "json"
            content, filename, mime_type = create_sample_file(file_type)
            kwargs = {"who": who, "what": what}
            if source:
                kwargs["source_url"] = source
            url, save_metadata = storage.save(
                content=content, filename=filename, content_type=mime_type, **kwargs
            )
            saved_files.append((description, url))
            print(f"   📄 {description}")
            print(f"      URL: {url}")
            print(f"      Object ID: {save_metadata.object_id}")
            print()
        print("🔍 Finding Files by Metadata")
        print("-" * 27)
        print("With metadata, you can easily categorize and find files:")
        print()
        for description, url in saved_files:
            content, metadata = storage.load(url)
            print(f"   📁 {description}")
            print(f"      Who: {metadata.who}")
            print(f"      What: {metadata.what}")
            print(f"      When: {metadata.ingestion_timestamp}")
            print(f"      Size: {len(content)} bytes")
            print()


def demonstrate_advanced_patterns():
    """Show advanced metadata patterns."""
    print("🚀 Advanced Metadata Patterns")
    print("=" * 30)
    print()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)
        print("Pattern 1: Document Versioning")
        print("-" * 29)
        for version in ["v1", "v2", "v3"]:
            content, filename, mime_type = create_sample_file("text")
            url, metadata = storage.save(
                content=content,
                filename=f"policy_document_{version}.txt",
                content_type=mime_type,
                who="legal_team",
                what=f"policy_document_{version}",
                source_url=f"https://docs.company.com/policy/{version}",
            )
            print(f"   📄 Saved {version}: {url}")
            print(f"       Object ID: {metadata.object_id}")
        print()
        print("Pattern 2: Multi-user Data Collection")
        print("-" * 36)
        users = ["researcher_1", "researcher_2", "researcher_3"]
        for user in users:
            content, filename, mime_type = create_sample_file("csv")
            url, metadata = storage.save(
                content=content,
                filename=f"survey_data_{user}.csv",
                content_type=mime_type,
                who=user,
                what="survey_response",
                source_url="https://survey.company.com/submit",
            )
            print(f"   📊 Data from {user}: {url}")
            print(f"       Object ID: {metadata.object_id}")
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
    print("• 05_typed_dict_benefits.py - Benefits of tuple unpacking")
    print(
        "• 06_separate_load_methods.py - Separate load methods for content and metadata"
    )
    print("• 07_metadata_comparison.py - Metadata comparison and version control")
    print("• 08_url_comparison.py - URL-based comparison for efficient workflows")


if __name__ == "__main__":
    main()
