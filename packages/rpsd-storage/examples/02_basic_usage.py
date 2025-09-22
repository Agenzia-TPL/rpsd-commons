#!/usr/bin/env python3
"""
Basic Usage - Working with Different File Types

Now that you know the basics, let's explore saving different types of files
and see how rpsd-storage handles them.

What you'll learn:
- How to save text, JSON, CSV, and binary files
- Why content types matter
- How to organize multiple files
- Real-world use cases for each file type

This builds on the concepts from 01_getting_started.py
"""

import tempfile

from rpsd_storage import FSStorageProvider


# Simple utilities for this example
def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """Create sample file content for demonstration."""
    samples = {
        "text": (b"This is a sample article about cloud storage technology.",
                 "article.txt", "text/plain"),
        "json": (b'{"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}',
                 "users.json", "application/json"),
        "csv": (
            b"date,product,amount\n2024-01-01,Widget A,1500\n2024-01-02,Widget B,2300",
            "sales.csv",
            "text/csv"
        ),
        "pdf": (b"%PDF-1.4\nSample PDF content for demonstration",
                "document.pdf", "application/pdf"),
        "xml": (b'<?xml version="1.0"?><config><host>localhost</host></config>',
                "config.xml", "application/xml"),
    }
    return samples[file_type]


def print_file_info(content: bytes, filename: str, mime_type: str) -> None:
    """Print file information for demonstration."""
    size_kb = len(content) / 1024
    preview = content[:50].decode("utf-8", errors="replace")
    if len(content) > 50:
        preview += "..."
    print(f"  📄 {filename}")
    print(f"     Type: {mime_type}")
    print(f"     Size: {size_kb:.1f} KB")
    print(f"     Preview: \"{preview}\"")


class SampleContent:
    """Sample content for examples."""
    LOG_ENTRY = (
        b"2024-01-15 10:30:00 INFO Application started successfully\n"
        b"2024-01-15 10:30:01 INFO Database connection established"
    )


def demonstrate_file_types():
    """Show how to save different types of files."""

    print("📁 Working with Different File Types")
    print("=" * 38)
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # We'll save several different file types to demonstrate versatility
        saved_files = []

        # 1. Text Documents
        print("1️⃣  Text Documents (articles, reports, documentation)")
        print("-" * 55)

        content, filename, mime_type = create_sample_file("text")
        print_file_info(content, filename, mime_type)

        object_id = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )
        saved_files.append(("Text Article", object_id))
        print(f"   ✅ Saved with ID: {object_id}")
        print()

        # 2. JSON Data
        print("2️⃣  JSON Data (API responses, configuration, user data)")
        print("-" * 55)

        content, filename, mime_type = create_sample_file("json")
        print_file_info(content, filename, mime_type)

        object_id = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )
        saved_files.append(("User Data JSON", object_id))
        print(f"   ✅ Saved with ID: {object_id}")
        print()

        # 3. CSV Data
        print("3️⃣  CSV Data (spreadsheets, data exports, analytics)")
        print("-" * 50)

        content, filename, mime_type = create_sample_file("csv")
        print_file_info(content, filename, mime_type)

        object_id = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )
        saved_files.append(("Sales Data CSV", object_id))
        print(f"   ✅ Saved with ID: {object_id}")
        print()

        # 4. Binary Files
        print("4️⃣  Binary Files (images, documents, media)")
        print("-" * 44)

        content, filename, mime_type = create_sample_file("pdf")
        print_file_info(content, filename, mime_type)

        object_id = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type
        )
        saved_files.append(("PDF Document", object_id))
        print(f"   ✅ Saved with ID: {object_id}")
        print()

        # Now let's load them all back to demonstrate retrieval
        print("🔄 Loading Files Back")
        print("=" * 20)
        print()

        for description, object_id in saved_files:
            content, metadata = storage.load(object_id)

            print(f"📄 {description}")
            print(f"   Original name: {metadata['original_filename']}")
            print(f"   Content type: {metadata['content_type']}")
            print(f"   Size: {len(content)} bytes")
            print(f"   Object ID: {metadata['object_id']}")
            print()


def demonstrate_real_world_scenarios():
    """Show common real-world use cases."""

    print("🌍 Real-World Use Cases")
    print("=" * 24)
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Scenario 1: Log File Archival
        print("Scenario 1: Application Log Archival")
        print("-" * 38)
        print("📝 You want to archive application logs for compliance")

        log_content = SampleContent.LOG_ENTRY
        object_id = storage.save(
            content=log_content,
            filename="app_20240115.log",
            content_type="text/plain"
        )

        print(f"   ✅ Log file archived with ID: {object_id}")
        print("   💡 Use case: Compliance, debugging, audit trails")
        print()

        # Scenario 2: Data Pipeline
        print("Scenario 2: Data Pipeline Processing")
        print("-" * 36)
        print("📊 You're processing sales data in a pipeline")

        csv_content, _, _ = create_sample_file("csv")
        object_id = storage.save(
            content=csv_content,
            filename="daily_sales_20240115.csv",
            content_type="text/csv"
        )

        print(f"   ✅ Sales data stored with ID: {object_id}")
        print("   💡 Use case: ETL processes, data analysis, reporting")
        print()

        # Scenario 3: Configuration Backup
        print("Scenario 3: Configuration Backup")
        print("-" * 32)
        print("⚙️  You want to backup application configuration")

        xml_content, _, _ = create_sample_file("xml")
        object_id = storage.save(
            content=xml_content,
            filename="prod_config_backup.xml",
            content_type="application/xml"
        )

        print(f"   ✅ Config backup saved with ID: {object_id}")
        print("   💡 Use case: Disaster recovery, version control, rollbacks")
        print()


def main():
    """Run the basic usage demonstrations."""

    print("📚 Basic Usage Guide for rpsd-storage")
    print("=" * 38)
    print("This example shows how to work with different file types")
    print("and common real-world scenarios.")
    print()

    demonstrate_file_types()
    demonstrate_real_world_scenarios()

    print("🎯 Key Takeaways:")
    print("-" * 16)
    print("• rpsd-storage works with ANY file type (text, binary, etc.)")
    print("• Content types help identify what kind of file you saved")
    print("• Object IDs are unique - you can save many files safely")
    print("• Each file gets metadata automatically tracked")
    print()
    print("📖 Next Steps:")
    print("• 03_metadata_and_types.py - Learn about custom metadata")
    print("• 04_advanced_features.py - Error handling and advanced features")


if __name__ == "__main__":
    main()
