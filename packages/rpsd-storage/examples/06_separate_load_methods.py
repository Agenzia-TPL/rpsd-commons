# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Examples demonstrating the new load_content, load_metadata, and delete methods.

These examples show practical use cases where loading content and metadata
separately provides better performance and cleaner code, plus safe deletion
workflows.
"""

import tempfile

from rpsd_storage import FSStorageProvider, HTTPStorageProvider, StorageProvider


def example_1_metadata_inspection():
    """
    Example 1: Inspect file metadata before deciding whether to load content.

    This is useful when you want to filter files based on metadata properties
    without downloading large content files.
    """
    print("=== Example 1: Metadata Inspection ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)
        files_data = [
            (b"Small configuration file", "config.txt", "text/plain"),
            (b"x" * 50000, "large_data.bin", "application/octet-stream"),
            (b'{"users": []}', "users.json", "application/json"),
            (b"x" * 1000000, "huge_file.dat", "application/octet-stream"),
        ]
        urls = []
        for content, filename, content_type in files_data:
            url, _ = provider.save(
                content,
                filename,
                content_type=content_type,
                who="system",
                what="example_data",
            )
            urls.append((url, filename))
            print(f"Saved: {filename} ({len(content)} bytes)")
        print("\nInspecting metadata to find text files under 1KB:")
        for url, original_filename in urls:
            metadata = provider.load_metadata(url)
            if metadata.content_type.startswith("text/") and original_filename.endswith(
                (".txt", ".json")
            ):
                print(f"\nFound text file: {metadata.original_filename}")
                print(f"  Content type: {metadata.content_type}")
                print(f"  Who: {metadata.who}")
                print(f"  What: {metadata.what}")
                content = provider.load_content(url)
                print(f"  Content preview: {content[:50]}...")


def example_2_bulk_metadata_scanning():
    """
    Example 2: Efficiently scan metadata of many files.

    This shows how to process file catalogs or inventories without
    loading actual file content.
    """
    print("\n=== Example 2: Bulk Metadata Scanning ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)
        datasets = ["raw_data", "processed_data", "results"]
        users = ["alice", "bob", "charlie"]
        file_urls = []
        for dataset in datasets:
            for user in users:
                for i in range(3):
                    content = f"Data from {user} in {dataset} - file {i}".encode()
                    url, _ = provider.save(
                        content,
                        f"{user}_{dataset}_{i}.txt",
                        who=user,
                        what=dataset,
                        custom_metadata={"file_number": i, "pipeline_stage": dataset},
                    )
                    file_urls.append(url)
        print(f"Created {len(file_urls)} files")
        print("\nScanning metadata to generate report:")
        user_stats = {}
        dataset_stats = {}
        for url in file_urls:
            metadata = provider.load_metadata(url)
            user = metadata.who
            dataset = metadata.what
            user_stats[user] = user_stats.get(user, 0) + 1
            dataset_stats[dataset] = dataset_stats.get(dataset, 0) + 1
        print("\nFiles per user:")
        for user, count in sorted(user_stats.items()):
            print(f"  {user}: {count} files")
        print("\nFiles per dataset:")
        for dataset, count in sorted(dataset_stats.items()):
            print(f"  {dataset}: {count} files")


def example_3_http_efficiency():
    """
    Example 3: Efficient HTTP metadata checking.

    This demonstrates using HEAD requests to check file properties
    without downloading content.
    """
    print("\n=== Example 3: HTTP Efficiency Example ===")
    example_urls = [
        "https://httpbin.org/json",
        "https://httpbin.org/xml",
        "https://httpbin.org/html",
    ]
    provider = HTTPStorageProvider(timeout=10.0)
    print("Checking HTTP resources efficiently:")
    for url in example_urls:
        try:
            metadata = provider.load_metadata(url)
            print(f"\nURL: {url}")
            print(f"  Status: {metadata.status_code}")
            print(f"  Content-Type: {metadata.content_type}")
            print(f"  Content-Length: {getattr(metadata, 'content_length', 'Unknown')}")
            if metadata.content_type.startswith("application/json"):
                print("  ↳ Loading JSON content...")
                content = provider.load_content(url)
                print(f"  ↳ Content size: {len(content)} bytes")
            else:
                print("  ↳ Skipping content (not JSON)")
        except Exception as e:
            print(f"\nURL: {url} - Error: {e}")


def example_4_static_methods():
    """
    Example 4: Using static methods for URL-based loading.

    This shows how to use the static methods when you don't know
    the provider type in advance.
    """
    print("\n=== Example 4: Static Methods ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        fs_provider = FSStorageProvider(temp_dir)
        url1, _ = fs_provider.save(
            b"File system content", "fs_test.txt", who="example", what="demo"
        )
        print(f"Created file: {url1}")
        print("\nUsing static methods (auto-detects provider):")
        content = StorageProvider.load_content_from_url(url1)
        print(f"Content: {content}")
        metadata = StorageProvider.load_metadata_from_url(url1)
        print(f"Filename: {metadata.original_filename}")
        print(f"Content type: {metadata.content_type}")
        who = metadata.who
        what = metadata.what
        object_id = metadata.object_id
        if who != "unknown" and what != "unknown":
            content_by_parts = fs_provider.load_content_by_parts(who, what, object_id)
            metadata_by_parts = fs_provider.load_metadata_by_parts(who, what, object_id)
            print(f"By parts - Content matches: {content == content_by_parts}")
            print(f"By parts - Metadata matches: {metadata == metadata_by_parts}")
        else:
            print("By parts - Skipped (no who/what metadata)")


def example_5_performance_comparison():
    """
    Example 5: Performance comparison between methods.

    This shows the performance benefits of using separate methods.
    """
    print("\n=== Example 5: Performance Comparison ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)
        large_content = b"X" * 1000000
        url, _ = provider.save(
            large_content, "large_file.dat", who="performance_test", what="test_data"
        )
        print("Created 1MB test file")
        print("\nScenario 1: Only need metadata")
        print("  Using load_metadata() - efficient (only reads .meta file)")
        metadata = provider.load_metadata(url)
        print(f"  File exists: {metadata.original_filename}")
        print(f"  Content type: {metadata.content_type}")
        print("\nScenario 2: Only need content")
        print("  Using load_content() - efficient (only reads content file)")
        content = provider.load_content(url)
        print(f"  Content loaded: {len(content)} bytes")
        print("\nScenario 3: Need both content and metadata")
        print("  Using load() - reads both files")
        full_content, full_metadata = provider.load(url)
        print(f"  Content: {len(full_content)} bytes")
        print(f"  Metadata: {full_metadata.original_filename}")


def example_6_delete_workflows():
    """
    Example 6: Safe deletion workflows with metadata inspection.

    This demonstrates how to use metadata inspection before deletion
    and shows different deletion patterns.
    """
    print("\n=== Example 6: Delete Workflows ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)
        files_to_create = [
            (b"Important system config", "system_config.txt", "system", "config"),
            (b"Temporary processing data", "temp_data.json", "user", "temp"),
            (b"User document v1", "document_v1.pdf", "user", "docs"),
            (b"User document v2", "document_v2.pdf", "user", "docs"),
            (b"Log data from yesterday", "old_log.txt", "system", "logs"),
        ]
        created_files = []
        for content, filename, who, what in files_to_create:
            url, metadata = provider.save(content, filename, who=who, what=what)
            created_files.append((url, metadata))
            print(f"Created: {filename}")
        print(f"\nTotal files created: {len(created_files)}")
        print("\n--- Workflow 1: Safe deletion with metadata check ---")
        for url, original_metadata in created_files:
            metadata = provider.load_metadata(url)
            if metadata.what == "temp":
                print(f"Deleting temporary file: {metadata.original_filename}")
                provider.delete(url)
                print("  ✓ Deleted successfully")
                try:
                    provider.load_metadata(url)
                    print("  ❌ ERROR: File still exists!")
                except FileNotFoundError:
                    print("  ✓ Confirmed: File no longer exists")
            else:
                what_val = metadata.what
                print(f"Keeping: {metadata.original_filename} (what={what_val})")
        print("\n--- Workflow 2: Cleanup old document versions ---")
        remaining_files = []
        for url, original_metadata in created_files:
            try:
                metadata = provider.load_metadata(url)
                remaining_files.append((url, metadata))
            except FileNotFoundError:
                continue
        doc_files = [
            (url, meta) for url, meta in remaining_files if meta.what == "docs"
        ]
        for url, metadata in doc_files:
            filename = metadata.original_filename
            if "v1" in filename:
                print(f"Removing old version: {filename}")
                provider.delete(url)
                print("  ✓ Old version deleted")
        print("\n--- Workflow 3: Using static delete method ---")
        log_files = [
            (url, meta) for url, meta in remaining_files if meta.what == "logs"
        ]
        for url, metadata in log_files:
            filename = metadata.original_filename
            print(f"Deleting log file using static method: {filename}")
            StorageProvider.delete_from_url(url)
            print("  ✓ Deleted via static method")
        print("\n--- Final file inventory ---")
        final_count = 0
        for url, original_metadata in created_files:
            try:
                metadata = provider.load_metadata(url)
                who_val = metadata.who
                what_val = metadata.what
                filename = metadata.original_filename
                print(f"Remaining: {filename} ({who_val}/{what_val})")
                final_count += 1
            except FileNotFoundError:
                pass
        start_count = len(created_files)
        print(f"\nFinal count: {final_count} files remaining (started: {start_count})")


def example_7_deletion_error_handling():
    """
    Example 7: Proper error handling for deletion operations.

    This shows how to handle various deletion scenarios and errors gracefully.
    """
    print("\n=== Example 7: Deletion Error Handling ===")
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)
        url, metadata = provider.save(
            b"Test content", "test_file.txt", who="test_user", what="test_data"
        )
        print(f"Created test file: {metadata.original_filename}")
        print("\n--- Scenario 1: Normal deletion ---")
        try:
            provider.delete(url)
            print("✓ File deleted successfully")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        print("\n--- Scenario 2: Delete non-existent file ---")
        try:
            provider.delete(url)
            print("❌ This shouldn't happen")
        except FileNotFoundError as e:
            print(f"✓ Expected error caught: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        print("\n--- Scenario 3: Invalid URL schemes ---")
        invalid_urls = [
            "ftp://example.com/file.txt",
            "invalid://scheme/file.txt",
            "s3://wrong-bucket/file.txt",
        ]
        for invalid_url in invalid_urls:
            try:
                provider.delete(invalid_url)
                print(f"❌ Should have failed for: {invalid_url}")
            except ValueError as e:
                print(f"✓ Expected ValueError for {invalid_url}: {e}")
            except Exception as e:
                print(f"? Other error for {invalid_url}: {e}")
        print("\n--- Scenario 4: HTTP provider deletion ---")
        http_provider = HTTPStorageProvider()
        try:
            http_provider.delete("https://example.com/file.txt")
            print("❌ Should have raised NotImplementedError")
        except NotImplementedError as e:
            print(f"✓ Expected NotImplementedError: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        print("\n--- Scenario 5: Static method with unsupported scheme ---")
        try:
            StorageProvider.delete_from_url("unknown://scheme/file.txt")
            print("❌ Should have failed")
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


def main():
    """Run all examples."""
    print("🚀 RPSD Storage - Load/Delete Methods Examples")
    print("=" * 60)
    example_1_metadata_inspection()
    example_2_bulk_metadata_scanning()
    example_3_http_efficiency()
    example_4_static_methods()
    example_5_performance_comparison()
    example_6_delete_workflows()
    example_7_deletion_error_handling()
    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print()
    print("📚 Continue learning:")
    print("   • 07_metadata_comparison.py - Metadata comparison and version control")
    print("   • 08_url_comparison.py - URL-based comparison for efficient workflows")
    print()
    print("🎉 Congratulations! You've completed the core rpsd-storage tutorial series.")
    print("   You're now ready to use rpsd-storage in production applications!")


if __name__ == "__main__":
    main()
