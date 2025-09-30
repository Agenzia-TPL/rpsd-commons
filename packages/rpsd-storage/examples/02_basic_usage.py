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


def create_sample_file(file_type: str) -> tuple[bytes, str, str]:
    """Create sample file content for demonstration."""
    samples = {
        "text": (
            b"This is a sample article about cloud storage technology.",
            "article.txt",
            "text/plain",
        ),
        "json": (
            b'{"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}',
            "users.json",
            "application/json",
        ),
        "csv": (
            b"date,product,amount\n2024-01-01,Widget A,1500\n2024-01-02,Widget B,2300",
            "sales.csv",
            "text/csv",
        ),
        "pdf": (
            b"%PDF-1.4\nSample PDF content for demonstration",
            "document.pdf",
            "application/pdf",
        ),
        "xml": (
            b'<?xml version="1.0"?><config><host>localhost</host></config>',
            "config.xml",
            "application/xml",
        ),
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
    print(f'     Preview: "{preview}"')


class SampleContent:
    """Sample content for examples."""

    LOG_ENTRY = b"2024-01-15 10:30:00 INFO Application started successfully\n2024-01-15 10:30:01 INFO Database connection established"


def demonstrate_file_types():
    """Show how to save different types of files."""
    print("📁 Working with Different File Types")
    print("=" * 38)
    print()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)
        saved_files = []
        print("1️⃣  Text Documents (articles, reports, documentation)")
        print("-" * 55)
        content, filename, mime_type = create_sample_file("text")
        print_file_info(content, filename, mime_type)
        url, metadata = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="document_user",
            what="article",
        )
        saved_files.append(("Text Article", url))
        print(f"   ✅ Saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print()
        print("2️⃣  JSON Data (API responses, configuration, user data)")
        print("-" * 55)
        content, filename, mime_type = create_sample_file("json")
        print_file_info(content, filename, mime_type)
        url, metadata = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="api_user",
            what="user_data",
        )
        saved_files.append(("User Data JSON", url))
        print(f"   ✅ Saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print()
        print("3️⃣  CSV Data (spreadsheets, data exports, analytics)")
        print("-" * 50)
        content, filename, mime_type = create_sample_file("csv")
        print_file_info(content, filename, mime_type)
        url, metadata = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="sales_team",
            what="sales_data",
        )
        saved_files.append(("Sales Data CSV", url))
        print(f"   ✅ Saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print()
        print("4️⃣  Binary Files (images, documents, media)")
        print("-" * 44)
        content, filename, mime_type = create_sample_file("pdf")
        print_file_info(content, filename, mime_type)
        url, metadata = storage.save(
            content=content,
            filename=filename,
            content_type=mime_type,
            who="document_user",
            what="pdf_document",
        )
        saved_files.append(("PDF Document", url))
        print(f"   ✅ Saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print()
        print("🔄 Loading Files Back")
        print("=" * 20)
        print()
        for description, url in saved_files:
            content, metadata = storage.load(url)
            print(f"📄 {description}")
            print(f"   Original name: {metadata.original_filename}")
            print(f"   Content type: {metadata.content_type}")
            print(f"   Size: {len(content)} bytes")
            print(f"   Object ID: {metadata.object_id}")
            print()


def demonstrate_real_world_scenarios():
    """Show common real-world use cases."""
    print("🌍 Real-World Use Cases")
    print("=" * 24)
    print()
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)
        print("Scenario 1: Application Log Archival")
        print("-" * 38)
        print("📝 You want to archive application logs for compliance")
        log_content = SampleContent.LOG_ENTRY
        url, metadata = storage.save(
            content=log_content,
            filename="app_20240115.log",
            content_type="text/plain",
            who="log_system",
            what="application_logs",
        )
        print(f"   ✅ Log file archived with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print("   💡 Use case: Compliance, debugging, audit trails")
        print()
        print("Scenario 2: Data Pipeline Processing")
        print("-" * 36)
        print("📊 You're processing sales data in a pipeline")
        csv_content, _, _ = create_sample_file("csv")
        url, metadata = storage.save(
            content=csv_content,
            filename="daily_sales_20240115.csv",
            content_type="text/csv",
            who="data_pipeline",
            what="daily_sales",
        )
        print(f"   ✅ Sales data stored with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
        print("   💡 Use case: ETL processes, data analysis, reporting")
        print()
        print("Scenario 3: Configuration Backup")
        print("-" * 32)
        print("⚙️  You want to backup application configuration")
        xml_content, _, _ = create_sample_file("xml")
        url, metadata = storage.save(
            content=xml_content,
            filename="prod_config_backup.xml",
            content_type="application/xml",
            who="devops_team",
            what="config_backup",
        )
        print(f"   ✅ Config backup saved with URL: {url}")
        print(f"       Object ID: {metadata.object_id}")
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
    print("• save() returns URL and metadata - unpack with tuple syntax")
    print("• URLs include provider info and organized who/what structure")
    print("• Object IDs include file extensions for fast retrieval")
    print("• Each file gets metadata automatically tracked")
    print()
    print("📖 Next Steps:")
    print("• 03_metadata_and_types.py - Learn about custom metadata")
    print("• 04_advanced_features.py - Error handling and advanced features")
    print("• 05_typed_dict_benefits.py - Benefits of tuple unpacking")
    print(
        "• 06_separate_load_methods.py - Separate load methods for content and metadata"
    )
    print("• 07_metadata_comparison.py - Metadata comparison and version control")
    print("• 08_url_comparison.py - URL-based comparison for efficient workflows")


if __name__ == "__main__":
    main()
