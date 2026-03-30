"""
Metadata Comparison Methods - Version Control and Update Detection

This example demonstrates the metadata comparison capabilities in rpsd-storage,
showing how to detect updates, compare versions, and manage file evolution.

What you'll learn:
- How to use StorageMetadata.compare() for version comparison
- How to use the is_update_of() convenience method
- Practical patterns for update detection and version management
- Error handling for comparing different entities
- Real-world scenarios for metadata comparison

These methods enable sophisticated version control and update detection workflows.
"""

import tempfile

from rpsd_storage import FSStorageProvider
from rpsd_storage.metadata import StorageMetadata


def example_1_basic_comparison():
    """
    Example 1: Basic metadata comparison concepts.

    This demonstrates the fundamental comparison semantics:
    - -1: candidate is older than current
    - 0: candidate has identical content to current
    - 1: candidate is newer than current
    """
    print("=== Example 1: Basic Comparison Concepts ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Save initial version
        initial_content = b"Initial document content"
        url1, metadata1 = provider.save(
            initial_content, "document.txt", who="alice", what="report"
        )
        print(f"Saved initial version: {metadata1.original_filename}")
        print(f"  Timestamp: {metadata1.save_stamp}")
        print(f"  Hash: {metadata1.hash}")

        # Save updated version (different content)
        updated_content = b"Updated document content with new information"
        url2, metadata2 = provider.save(
            updated_content, "document.txt", who="alice", what="report"
        )
        print(f"\nSaved updated version: {metadata2.original_filename}")
        print(f"  Timestamp: {metadata2.save_stamp}")
        print(f"  Hash: {metadata2.hash}")

        # Compare versions
        result = StorageMetadata.compare(metadata1, metadata2)
        print(f"\nComparison result: {result}")
        if result == -1:
            print("  → Metadata2 is older than metadata1")
        elif result == 0:
            print("  → Metadata2 has identical content to metadata1")
        elif result == 1:
            print("  → Metadata2 is newer than metadata1")

        # Use convenience method
        is_update = metadata2.is_update_of(metadata1)
        print(f"\nis_update_of() result: {is_update}")
        if is_update:
            print("  → metadata2 represents an update to metadata1")
        else:
            print("  → metadata2 is not an update (same content or older)")


def example_2_identical_content_detection():
    """
    Example 2: Detecting identical content across different save times.

    This shows how comparison handles cases where the same content
    is saved multiple times.
    """
    print("\n=== Example 2: Identical Content Detection ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Save same content twice with different timestamps
        content = b"This content will be saved twice"

        url1, metadata1 = provider.save(content, "file_v1.txt", who="bob", what="data")
        print(f"First save: {metadata1.original_filename}")
        print(f"  Timestamp: {metadata1.save_stamp}")

        # Small delay to ensure different timestamp
        import time

        time.sleep(0.01)

        url2, metadata2 = provider.save(
            content,
            "file_v2.txt",
            who="bob",
            what="data",  # Same content!
        )
        print(f"\nSecond save: {metadata2.original_filename}")
        print(f"  Timestamp: {metadata2.save_stamp}")

        # Compare - should return 0 for identical content
        result = StorageMetadata.compare(metadata1, metadata2)
        print(f"\nComparison result: {result}")
        print("  → Content is identical despite different timestamps")

        # Verify hashes are the same
        print("\nHash verification:")
        print(f"  metadata1.hash: {metadata1.hash}")
        print(f"  metadata2.hash: {metadata2.hash}")
        print(f"  Hashes match: {metadata1.hash == metadata2.hash}")


def example_3_update_detection_workflow():
    """
    Example 3: Practical update detection workflow.

    This demonstrates a real-world scenario where you need to
    determine if incoming data represents an update to existing data.
    """
    print("\n=== Example 3: Update Detection Workflow ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Simulate a data pipeline scenario
        print("Simulating data pipeline with update detection...")

        # Initial content
        datasets = [
            (b"Raw sensor data from device A", "sensor_a_raw.csv"),
            (b"Raw sensor data from device B", "sensor_b_raw.csv"),
            (b"Processed aggregated results", "summary_report.json"),
        ]

        stored_metadata = {}

        for content, filename in datasets:
            url, metadata = provider.save(
                content, filename, who="data_pipeline", what="sensor_data"
            )
            stored_metadata[filename] = metadata
            print(f"  Stored: {filename}")

        print(f"\nInitial storage complete. Stored {len(stored_metadata)} files.")

        # Simulate new data arriving
        print("\n--- Processing incoming data batch ---")
        incoming_data = [
            (b"Raw sensor data from device A", "sensor_a_raw.csv"),  # Same content
            (
                b"Updated sensor data from device B - new readings",
                "sensor_b_raw.csv",
            ),  # Updated
            (b"Processed aggregated results", "summary_report.json"),  # Same content
            (b"Raw sensor data from device C", "sensor_c_raw.csv"),  # New file
        ]

        updates_processed = 0
        duplicates_skipped = 0
        new_files_added = 0

        for content, filename in incoming_data:
            if filename in stored_metadata:
                # File exists - check if it's an update
                print(f"\nProcessing existing file: {filename}")

                # Create temporary metadata for comparison
                temp_url, new_metadata = provider.save(
                    content, f"temp_{filename}", who="data_pipeline", what="sensor_data"
                )

                current_metadata = stored_metadata[filename]

                if new_metadata.is_update_of(current_metadata):
                    print("  ✓ Update detected - processing new version")
                    # In real scenario, you'd update the stored file
                    stored_metadata[filename] = new_metadata
                    updates_processed += 1
                else:
                    print("  → No update needed (same content)")
                    duplicates_skipped += 1

                # Clean up temp file
                provider.delete(temp_url)

            else:
                # New file
                print(f"\nProcessing new file: {filename}")
                url, metadata = provider.save(
                    content, filename, who="data_pipeline", what="sensor_data"
                )
                stored_metadata[filename] = metadata
                new_files_added += 1
                print("  ✓ New file added")

        print("\n--- Batch processing summary ---")
        print(f"Updates processed: {updates_processed}")
        print(f"Duplicates skipped: {duplicates_skipped}")
        print(f"New files added: {new_files_added}")
        print(f"Total files in storage: {len(stored_metadata)}")


def example_4_version_management():
    """
    Example 4: Version management and chronological ordering.

    This shows how to use comparison results to manage multiple
    versions of the same logical entity.
    """
    print("\n=== Example 4: Version Management ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Create multiple versions of a document
        versions = [
            b"Version 1: Initial draft of the proposal",
            b"Version 2: Added executive summary and budget",
            b"Version 3: Incorporated feedback from review committee",
            b"Version 4: Final version ready for approval",
        ]

        version_metadata = []

        for i, content in enumerate(versions, 1):
            # Add small delay to ensure different timestamps
            if i > 1:
                import time

                time.sleep(0.01)

            url, metadata = provider.save(
                content, f"proposal_v{i}.md", who="project_team", what="proposal"
            )
            version_metadata.append(metadata)
            print(f"Created version {i}: {metadata.original_filename}")

        print(f"\nCreated {len(version_metadata)} versions")

        # Find the latest version
        print("\n--- Finding latest version ---")
        latest_metadata = version_metadata[0]

        for metadata in version_metadata[1:]:
            if metadata.is_update_of(latest_metadata):
                latest_metadata = metadata

        print(f"Latest version: {latest_metadata.original_filename}")
        print(f"  Timestamp: {latest_metadata.save_stamp}")

        # Sort all versions chronologically
        print("\n--- Chronological ordering ---")

        # Custom sort using comparison method
        def compare_metadata(a, b):
            """Helper function for sorting."""
            result = StorageMetadata.compare(a, b)
            if result == -1:  # a's candidate (b) is older
                return 1  # a should come after b
            elif result == 1:  # a's candidate (b) is newer
                return -1  # a should come before b
            else:
                return 0  # same content

        from functools import cmp_to_key

        sorted_versions = sorted(version_metadata, key=cmp_to_key(compare_metadata))

        print("Versions in chronological order (oldest to newest):")
        for i, metadata in enumerate(sorted_versions, 1):
            print(f"  {i}. {metadata.original_filename} - {metadata.save_stamp}")


def example_5_error_handling():
    """
    Example 5: Error handling for invalid comparisons.

    This demonstrates how the comparison methods handle attempts
    to compare metadata from different entities.
    """
    print("\n=== Example 5: Error Handling ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Create files from different entities
        url1, metadata1 = provider.save(
            b"Alice's document", "doc.txt", who="alice", what="report"
        )

        url2, metadata2 = provider.save(
            b"Bob's document",
            "doc.txt",
            who="bob",
            what="report",  # Different who
        )

        url3, metadata3 = provider.save(
            b"Alice's image",
            "image.jpg",
            who="alice",
            what="photo",  # Different what
        )

        print("Created test files:")
        print(f"  1. {metadata1.who}/{metadata1.what}: {metadata1.original_filename}")
        print(f"  2. {metadata2.who}/{metadata2.what}: {metadata2.original_filename}")
        print(f"  3. {metadata3.who}/{metadata3.what}: {metadata3.original_filename}")

        # Attempt invalid comparisons
        print("\n--- Testing error cases ---")

        # Different 'who' field
        print("\nCase 1: Different 'who' field")
        try:
            result = StorageMetadata.compare(metadata1, metadata2)
            print(f"❌ Unexpected success: {result}")
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")

        # Different 'what' field
        print("\nCase 2: Different 'what' field")
        try:
            result = metadata1.is_update_of(metadata3)
            print(f"❌ Unexpected success: {result}")
        except ValueError as e:
            print(f"✓ Expected ValueError: {e}")

        # Valid comparison (same who/what)
        print("\nCase 3: Valid comparison")
        url4, metadata4 = provider.save(
            b"Alice's updated report", "doc_v2.txt", who="alice", what="report"
        )

        try:
            result = StorageMetadata.compare(metadata1, metadata4)
            print(f"✓ Valid comparison result: {result}")
            is_update = metadata4.is_update_of(metadata1)
            print(f"✓ is_update_of result: {is_update}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


def example_6_real_world_scenarios():
    """
    Example 6: Real-world scenarios and patterns.

    This demonstrates common patterns and use cases for metadata
    comparison in production applications.
    """
    print("\n=== Example 6: Real-World Scenarios ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        print("Scenario: Document management system with update tracking")

        # Simulate a document management workflow
        document_registry = {}  # filename -> latest metadata

        # Documents arriving over time
        documents = [
            ("README.md", b"# Project Documentation\nInitial setup instructions"),
            ("config.yaml", b"version: 1.0\nservice:\n  port: 8080"),
            ("api_spec.json", b'{"version": "1.0", "endpoints": []}'),
            (
                "README.md",
                b"# Project Documentation\nDetailed setup and usage guide",
            ),  # Update
            (
                "config.yaml",
                b"version: 1.1\nservice:\n  port: 8080\n  debug: true",
            ),  # Update
            ("CHANGELOG.md", b"# Changelog\n## v1.0\n- Initial release"),  # New file
            (
                "README.md",
                b"# Project Documentation\nDetailed setup and usage guide",
            ),  # Duplicate
        ]

        def process_document(filename, content):
            """Process a document with update detection."""
            print(f"\nProcessing: {filename}")

            # Save the document to get metadata
            temp_url, new_metadata = provider.save(
                content, f"incoming_{filename}", who="system", what="documentation"
            )

            if filename in document_registry:
                current_metadata = document_registry[filename]

                comparison = StorageMetadata.compare(current_metadata, new_metadata)

                if comparison == 1:  # New is newer
                    print("  ✓ Update detected - replacing existing version")
                    # In real scenario, you'd handle the actual file replacement
                    document_registry[filename] = new_metadata
                    return "updated"
                elif comparison == 0:  # Same content
                    print("  → Duplicate detected - no action needed")
                    return "duplicate"
                else:  # New is older (comparison == -1)
                    print("  ⚠ Older version received - keeping current")
                    return "older"
            else:
                print("  ✓ New document - adding to registry")
                document_registry[filename] = new_metadata
                result = "new"

            # Clean up temporary file
            provider.delete(temp_url)
            return result

        # Process all documents
        results = {"new": 0, "updated": 0, "duplicate": 0, "older": 0}

        for filename, content in documents:
            result = process_document(filename, content)
            results[result] += 1

        print("\n--- Processing Summary ---")
        print(f"New documents: {results['new']}")
        print(f"Updates processed: {results['updated']}")
        print(f"Duplicates skipped: {results['duplicate']}")
        print(f"Older versions ignored: {results['older']}")

        print("\n--- Final Document Registry ---")
        for filename, metadata in document_registry.items():
            print(f"  {filename} (timestamp: {metadata.save_stamp})")


def main():
    """Run all examples."""
    print("🔄 RPSD Storage - Metadata Comparison Examples")
    print("=" * 60)
    example_1_basic_comparison()
    example_2_identical_content_detection()
    example_3_update_detection_workflow()
    example_4_version_management()
    example_5_error_handling()
    example_6_real_world_scenarios()
    print("\n" + "=" * 60)
    print("✅ All metadata comparison examples completed!")
    print()
    print("🎯 Key Takeaways:")
    print("   • Use compare() for full comparison semantics (-1, 0, 1)")
    print("   • Use is_update_of() for simple update detection")
    print("   • Comparison only works for same logical entity (who/what must match)")
    print("   • Identical content returns 0 regardless of timestamps")
    print("   • Perfect for version control and update detection workflows")
    print()
    print("🎉 Congratulations! You've mastered rpsd-storage metadata comparison.")
    print("   You're now equipped to build sophisticated version control systems!")


if __name__ == "__main__":
    main()
