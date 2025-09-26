#!/usr/bin/env python3
"""
Advanced Features - Production-Ready Patterns

Ready to use rpsd-storage in production? This example covers error handling,
configuration, custom storage locations, and advanced patterns.

What you'll learn:
- How to handle errors gracefully
- Different ways to configure storage providers
- Using custom storage directories
- Performance considerations
- Production deployment patterns

This is the advanced guide - make sure you've completed the earlier examples first!
"""

import os
import tempfile
from typing import Any

from rpsd_storage import FSStorageProvider, get_storage_provider


# Simple utilities for this example
def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """Create sample file content for demonstration."""
    samples = {
        "text": (
            b"Sample document for advanced features demonstration.",
            "document.txt",
            "text/plain",
        ),
        "json": (
            b'{"status": "processing", "items": 42}',
            "data.json",
            "application/json",
        ),
        "csv": (
            b"month,sales,region\nJan,1500,North\nFeb,2300,South",
            "report.csv",
            "text/csv",
        ),
    }
    return samples[file_type]


def get_metadata_preset(preset: str) -> dict[str, Any]:
    """Get predefined metadata for demonstration."""
    presets = {
        "data_export": {"who": "data_pipeline", "what": "export_data"},
        "minimal": {},
    }
    return presets[preset].copy()


def demonstrate_error_handling():
    """Show how to handle common errors gracefully."""

    print("⚠️  Error Handling")
    print("=" * 17)
    print("Production applications need robust error handling:")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Save a file first
        content, filename, mime_type = create_sample_file("json")
        url, metadata = storage.save(
            content, filename, "test_user", "test_data", content_type=mime_type
        )
        print(f"✅ Saved test file: {url}")
        print(f"   Object ID: {metadata['object_id']}")
        print()

        # Error 1: Loading non-existent file
        print("1. Handling Missing Files")
        print("-" * 26)

        try:
            storage.load("file:///non/existent/path.txt")
            print("   ❌ This shouldn't happen!")
        except FileNotFoundError as e:
            print(f"   ✅ Caught FileNotFoundError: {e}")
            print("   💡 Handle this by showing user-friendly error messages")

        print()

        # Error 2: Invalid storage path
        print("2. Handling Invalid Storage Paths")
        print("-" * 33)

        try:
            # Try to create storage in a non-existent parent directory
            invalid_path = "/definitely/does/not/exist/storage"
            _ = FSStorageProvider(base_path=invalid_path)
            print("   ✅ Path created successfully (directories auto-created)")
        except Exception as e:
            print(f"   ⚠️  Path creation failed: {e}")
            print("   💡 Always check permissions and disk space")

        print()

        # Error 3: Handling empty/None content
        print("3. Handling Invalid Content")
        print("-" * 27)

        try:
            # This will work but save empty content
            url, metadata = storage.save(
                b"", "empty.txt", "test_user", "empty_test", content_type="text/plain"
            )
            print(f"   ✅ Empty file saved: {url}")
            print(f"       Object ID: {metadata['object_id']}")
            print("   💡 Consider validating content before saving")
        except Exception as e:
            print(f"   ⚠️  Save failed: {e}")

        print()


def demonstrate_configuration_patterns():
    """Show different ways to configure storage."""

    print("⚙️  Configuration Patterns")
    print("=" * 25)
    print("Different ways to configure storage for different environments:")
    print()

    # Pattern 1: Environment Variables
    print("1. Environment Variable Configuration")
    print("-" * 37)

    # Set up environment for file system storage
    os.environ["STORAGE_PROVIDER"] = "fs"
    os.environ["FS_BASE_PATH"] = "/tmp/production_storage"

    print("   Environment setup:")
    print(f"     STORAGE_PROVIDER = {os.environ['STORAGE_PROVIDER']}")
    print(f"     FS_BASE_PATH = {os.environ['FS_BASE_PATH']}")

    # Use the factory function
    storage = get_storage_provider()
    print("   ✅ Storage provider created from environment")

    # Test it
    content, filename, mime_type = create_sample_file("text")
    url, metadata = storage.save(
        content, filename, "env_test", "config_test", content_type=mime_type
    )
    print(f"   ✅ Test file saved: {url}")
    print(f"       Object ID: {metadata['object_id']}")
    print()

    # Pattern 2: Direct Configuration
    print("2. Direct Configuration")
    print("-" * 24)

    custom_storage_path = "/tmp/custom_app_storage"
    direct_storage = FSStorageProvider(base_path=custom_storage_path)
    print(f"   ✅ Direct storage created at: {custom_storage_path}")

    content, filename, mime_type = create_sample_file("json")
    url, metadata = direct_storage.save(
        content, filename, "direct_test", "direct_config", content_type=mime_type
    )
    print(f"   ✅ Test file saved: {url}")
    print(f"       Object ID: {metadata['object_id']}")
    print()

    # Pattern 3: Application-Specific Directories
    print("3. Application-Specific Organization")
    print("-" * 34)

    base_path = "/tmp/myapp_storage"
    app_directories = {
        "user_uploads": FSStorageProvider(f"{base_path}/user_uploads"),
        "system_logs": FSStorageProvider(f"{base_path}/logs"),
        "data_exports": FSStorageProvider(f"{base_path}/exports"),
        "backups": FSStorageProvider(f"{base_path}/backups"),
    }

    for purpose, storage_provider in app_directories.items():
        content, filename, mime_type = create_sample_file("text")
        url, metadata = storage_provider.save(
            content,
            f"sample_{purpose}.txt",
            "app_system",
            purpose,
            content_type=mime_type,
        )
        print(f"   📁 {purpose}: {url}")
        print(f"       Object ID: {metadata['object_id']}")

    print()

    # Clean up environment
    del os.environ["STORAGE_PROVIDER"]
    del os.environ["FS_BASE_PATH"]


def demonstrate_bulk_operations():
    """Show patterns for handling many files efficiently."""

    print("📦 Bulk Operations")
    print("=" * 16)
    print("Patterns for handling large numbers of files:")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Bulk save with consistent metadata
        print("1. Bulk Save with Batch Processing")
        print("-" * 34)

        # Simulate processing a batch of CSV files
        csv_files = [
            "sales_january.csv",
            "sales_february.csv",
            "sales_march.csv",
            "sales_april.csv",
            "sales_may.csv",
        ]

        saved_objects = []
        metadata_template = get_metadata_preset("data_export")

        print("   Processing batch of sales files:")
        for csv_file in csv_files:
            content, _, mime_type = create_sample_file("csv")

            # Customize metadata for each file
            metadata = metadata_template.copy()
            metadata["what"] = f"monthly_sales_{csv_file.split('_')[1].split('.')[0]}"

            url, save_metadata = storage.save(
                content, csv_file, metadata["who"], metadata["what"], content_type=mime_type
            )

            saved_objects.append((csv_file, url))
            print(f"     ✅ {csv_file}: {url}")
            print(f"         Object ID: {save_metadata['object_id']}")

        print(f"   📊 Batch complete: {len(saved_objects)} files saved")
        print()

        # Bulk retrieval
        print("2. Bulk Retrieval and Validation")
        print("-" * 31)

        total_size = 0
        for filename, url in saved_objects:
            try:
                content, metadata = storage.load(url)
                file_size = len(content)
                total_size += file_size

                print(f"     📄 {filename}: {file_size:,} bytes")

            except Exception as e:
                print(f"     ❌ Error loading {filename}: {e}")

        print(f"   📈 Total data processed: {total_size:,} bytes")
        print()


def demonstrate_production_patterns():
    """Show production-ready patterns and best practices."""

    print("🏭 Production Patterns")
    print("=" * 20)
    print("Best practices for production deployments:")
    print()

    # Pattern 1: Organized Storage Structure
    print("1. Organized Storage Structure")
    print("-" * 30)

    base_storage = "/tmp/production_app"
    year = "2024"
    month = "01"

    # Create hierarchical storage
    storage_structure = {
        "incoming": f"{base_storage}/incoming/{year}/{month}",
        "processed": f"{base_storage}/processed/{year}/{month}",
        "archived": f"{base_storage}/archived/{year}",
        "failed": f"{base_storage}/failed/{year}/{month}",
    }

    storages = {}
    for stage, path in storage_structure.items():
        storages[stage] = FSStorageProvider(base_path=path)
        print(f"   📁 {stage}: {path}")

    print()

    # Pattern 2: Processing Pipeline
    print("2. Processing Pipeline")
    print("-" * 21)

    # Simulate a file processing pipeline
    content, filename, mime_type = create_sample_file("json")

    # Step 1: Save to incoming
    incoming_url, incoming_metadata = storages["incoming"].save(
        content,
        filename,
        "data_pipeline",
        "incoming_data",
        content_type=mime_type,
    )
    print(f"   1️⃣  Incoming: {incoming_url}")
    print(f"       Object ID: {incoming_metadata['object_id']}")

    # Step 2: Process and save to processed
    try:
        # Load from incoming
        content_loaded, metadata_loaded = storages["incoming"].load(incoming_url)

        # Simulate processing (add metadata)
        processed_metadata = get_metadata_preset("data_export")
        custom_metadata = {
            "original_url": incoming_url,
            "processing_status": "completed",
        }

        processed_url, processed_save_metadata = storages["processed"].save(
            content_loaded,
            f"processed_{filename}",
            processed_metadata["who"],
            processed_metadata["what"],
            content_type=mime_type,
            custom_metadata=custom_metadata,
        )
        print(f"   2️⃣  Processed: {processed_url}")
        print(f"       Object ID: {processed_save_metadata['object_id']}")

        # Step 3: Archive the original
        archive_metadata = get_metadata_preset("minimal")
        custom_metadata = {"original_url": incoming_url, "processed_url": processed_url}

        archive_url, archive_save_metadata = storages["archived"].save(
            content_loaded,
            f"archive_{filename}",
            "archive_system",
            "archived_data",
            content_type=mime_type,
            custom_metadata=custom_metadata,
        )
        print(f"   3️⃣  Archived: {archive_url}")
        print(f"       Object ID: {archive_save_metadata['object_id']}")

    except Exception as e:
        # Save to failed for manual review
        failed_metadata = get_metadata_preset("minimal")
        custom_metadata = {"error": str(e), "original_filename": filename}

        failed_url, failed_save_metadata = storages["failed"].save(
            content,
            f"failed_{filename}",
            "error_handler",
            "failed_processing",
            content_type=mime_type,
            custom_metadata=custom_metadata,
        )
        print(f"   ❌ Failed: {failed_url}")
        print(f"       Object ID: {failed_save_metadata['object_id']}")

    print()

    # Pattern 3: Monitoring and Metrics
    print("3. Monitoring and Metrics")
    print("-" * 24)

    # Count files in each stage
    for stage, storage in storages.items():
        try:
            # In a real application, you'd implement a list/count method
            # For demo, we'll show the pattern
            print(f"   📊 {stage}: Storage configured at {storage.base_path}")
        except Exception as e:
            print(f"   ❌ {stage}: Error - {e}")

    print()


def main():
    """Run the advanced features demonstrations."""

    print("🚀 Advanced Features Guide")
    print("=" * 25)
    print("Production-ready patterns and advanced usage")
    print()

    demonstrate_error_handling()
    demonstrate_configuration_patterns()
    demonstrate_bulk_operations()
    demonstrate_production_patterns()

    print("🎯 Production Checklist:")
    print("-" * 21)
    print("✅ Implement proper error handling")
    print("✅ Use environment variables for configuration")
    print("✅ Organize storage with logical directory structure")
    print("✅ Add monitoring and logging for storage operations")
    print("✅ Plan for backup and disaster recovery")
    print("✅ Consider performance implications for bulk operations")
    print("✅ Implement proper security and access controls")
    print()
    print("🎉 Congratulations! You've completed the rpsd-storage tutorial series.")
    print("   You're now ready to use rpsd-storage in production applications!")


if __name__ == "__main__":
    main()
