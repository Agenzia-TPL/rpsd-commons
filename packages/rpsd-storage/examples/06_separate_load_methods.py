#!/usr/bin/env python3
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

        # Save some test files with different properties
        files_data = [
            (b"Small configuration file", "config.txt", "text/plain"),
            (b"x" * 50000, "large_data.bin", "application/octet-stream"),  # 50KB
            (b'{"users": []}', "users.json", "application/json"),
            (b"x" * 1000000, "huge_file.dat", "application/octet-stream"),  # 1MB
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

        # Efficiently check metadata first
        for url, original_filename in urls:
            metadata = provider.load_metadata(url)  # Only reads .meta file

            # Filter based on metadata
            if metadata["content_type"].startswith(
                "text/"
            ) and original_filename.endswith((".txt", ".json")):
                print(f"\nFound text file: {metadata['original_filename']}")
                print(f"  Content type: {metadata['content_type']}")
                print(f"  Who: {metadata.get('who', 'N/A')}")
                print(f"  What: {metadata.get('what', 'N/A')}")

                # Only load content for files that match our criteria
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

        # Create a bunch of files simulating a data pipeline
        datasets = ["raw_data", "processed_data", "results"]
        users = ["alice", "bob", "charlie"]

        file_urls = []

        for dataset in datasets:
            for user in users:
                for i in range(3):  # 3 files per user per dataset
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

        # Efficiently scan all metadata without loading content
        print("\nScanning metadata to generate report:")

        user_stats = {}
        dataset_stats = {}

        for url in file_urls:
            metadata = provider.load_metadata(url)  # Fast - only reads .meta

            user = metadata.get("who", "unknown")
            dataset = metadata.get("what", "unknown")

            # Count files per user
            user_stats[user] = user_stats.get(user, 0) + 1

            # Count files per dataset
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

    # Example URLs (these would be real URLs in practice)
    example_urls = [
        "https://httpbin.org/json",
        "https://httpbin.org/xml",
        "https://httpbin.org/html",
    ]

    provider = HTTPStorageProvider(timeout=10.0)

    print("Checking HTTP resources efficiently:")

    for url in example_urls:
        try:
            # Use HEAD request to get metadata without downloading content
            metadata = provider.load_metadata(url)

            print(f"\nURL: {url}")
            print(f"  Status: {metadata['status_code']}")
            print(f"  Content-Type: {metadata['content_type']}")
            print(f"  Content-Length: {metadata.get('content_length', 'Unknown')}")

            # Only load content if it's something we want
            if metadata["content_type"].startswith("application/json"):
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

    # Create some test files first
    with tempfile.TemporaryDirectory() as temp_dir:
        fs_provider = FSStorageProvider(temp_dir)

        url1, _ = fs_provider.save(
            b"File system content", "fs_test.txt", who="example", what="demo"
        )

        print(f"Created file: {url1}")

        # Use static methods - automatically detects provider type
        print("\nUsing static methods (auto-detects provider):")

        # Load only content using static method
        content = StorageProvider.load_content_from_url(url1)
        print(f"Content: {content}")

        # Load only metadata using static method
        metadata = StorageProvider.load_metadata_from_url(url1)
        print(f"Filename: {metadata['original_filename']}")
        print(f"Content type: {metadata['content_type']}")

        # Also works with parts-based methods
        who = metadata.get("who", "unknown")
        what = metadata.get("what", "unknown")
        object_id = metadata["object_id"]

        if who != "unknown" and what != "unknown":
            # Use the same provider instance to avoid path issues
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

        # Create a file with large content
        large_content = b"X" * 1_000_000  # 1MB of data
        url, _ = provider.save(large_content, "large_file.dat")

        print("Created 1MB test file")

        # Scenario 1: Only need to check if file exists and get basic info
        print("\nScenario 1: Only need metadata")
        print("  Using load_metadata() - efficient (only reads .meta file)")
        metadata = provider.load_metadata(url)
        print(f"  File exists: {metadata['original_filename']}")
        print(f"  Content type: {metadata['content_type']}")

        # Scenario 2: Only need the content
        print("\nScenario 2: Only need content")
        print("  Using load_content() - efficient (only reads content file)")
        content = provider.load_content(url)
        print(f"  Content loaded: {len(content)} bytes")

        # Scenario 3: Need both (traditional way)
        print("\nScenario 3: Need both content and metadata")
        print("  Using load() - reads both files")
        full_content, full_metadata = provider.load(url)
        print(f"  Content: {len(full_content)} bytes")
        print(f"  Metadata: {full_metadata['original_filename']}")


def example_6_delete_workflows():
    """
    Example 6: Safe deletion workflows with metadata inspection.

    This demonstrates how to use metadata inspection before deletion
    and shows different deletion patterns.
    """
    print("\n=== Example 6: Delete Workflows ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Create various files for deletion examples
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

        # Workflow 1: Safe deletion with metadata inspection
        print("\n--- Workflow 1: Safe deletion with metadata check ---")
        for url, original_metadata in created_files:
            # Check metadata before deletion
            metadata = provider.load_metadata(url)

            # Only delete temporary files
            if metadata.get("what") == "temp":
                print(f"Deleting temporary file: {metadata['original_filename']}")
                provider.delete(url)
                print("  ✓ Deleted successfully")

                # Verify deletion
                try:
                    provider.load_metadata(url)
                    print("  ❌ ERROR: File still exists!")
                except FileNotFoundError:
                    print("  ✓ Confirmed: File no longer exists")
            else:
                what_val = metadata.get('what')
                print(f"Keeping: {metadata['original_filename']} (what={what_val})")

        # Workflow 2: Bulk cleanup of old versions
        print("\n--- Workflow 2: Cleanup old document versions ---")
        remaining_files = []
        for url, original_metadata in created_files:
            try:
                metadata = provider.load_metadata(url)
                remaining_files.append((url, metadata))
            except FileNotFoundError:
                # File was already deleted in previous workflow
                continue

        # Find and delete old document versions
        doc_files = [
            (url, meta) for url, meta in remaining_files
            if meta.get("what") == "docs"
        ]

        for url, metadata in doc_files:
            filename = metadata['original_filename']
            if "v1" in filename:  # Delete old versions
                print(f"Removing old version: {filename}")
                provider.delete(url)
                print("  ✓ Old version deleted")

        # Workflow 3: Using static delete method
        print("\n--- Workflow 3: Using static delete method ---")
        log_files = [
            (url, meta) for url, meta in remaining_files
            if meta.get("what") == "logs"
        ]

        for url, metadata in log_files:
            filename = metadata['original_filename']
            print(f"Deleting log file using static method: {filename}")
            # Use static method - auto-detects provider
            StorageProvider.delete_from_url(url)
            print("  ✓ Deleted via static method")

        # Show final state
        print("\n--- Final file inventory ---")
        final_count = 0
        for url, original_metadata in created_files:
            try:
                metadata = provider.load_metadata(url)
                who_val = metadata.get('who')
                what_val = metadata.get('what')
                filename = metadata['original_filename']
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

        # Create a test file
        url, metadata = provider.save(b"Test content", "test_file.txt")
        print(f"Created test file: {metadata['original_filename']}")

        # Scenario 1: Normal deletion
        print("\n--- Scenario 1: Normal deletion ---")
        try:
            provider.delete(url)
            print("✓ File deleted successfully")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

        # Scenario 2: Delete non-existent file
        print("\n--- Scenario 2: Delete non-existent file ---")
        try:
            provider.delete(url)  # Try to delete again
            print("❌ This shouldn't happen")
        except FileNotFoundError as e:
            print(f"✓ Expected error caught: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

        # Scenario 3: Invalid URL schemes
        print("\n--- Scenario 3: Invalid URL schemes ---")
        invalid_urls = [
            "ftp://example.com/file.txt",
            "invalid://scheme/file.txt",
            "s3://wrong-bucket/file.txt",  # Wrong bucket for FS provider
        ]

        for invalid_url in invalid_urls:
            try:
                provider.delete(invalid_url)
                print(f"❌ Should have failed for: {invalid_url}")
            except ValueError as e:
                print(f"✓ Expected ValueError for {invalid_url}: {e}")
            except Exception as e:
                print(f"? Other error for {invalid_url}: {e}")

        # Scenario 4: HTTP provider deletion (not implemented)
        print("\n--- Scenario 4: HTTP provider deletion ---")
        http_provider = HTTPStorageProvider()
        try:
            http_provider.delete("https://example.com/file.txt")
            print("❌ Should have raised NotImplementedError")
        except NotImplementedError as e:
            print(f"✓ Expected NotImplementedError: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

        # Scenario 5: Static method with unsupported scheme
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
    print("\nKey Benefits:")
    print(
        "• load_content(): Only loads file content (efficient for content-only tasks)"
    )
    print("• load_metadata(): Only loads metadata (efficient for file inspection)")
    print("• delete(): Safely removes objects with proper error handling")
    print("• Static methods: Auto-detect provider type from URL")
    print("• Consistent error handling across all methods")
    print("• Better performance for targeted operations")
    print("• Safe deletion workflows with metadata validation")


if __name__ == "__main__":
    main()
