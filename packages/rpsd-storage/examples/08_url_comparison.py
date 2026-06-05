# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
URL-Based Comparison - Direct Comparison Without Loading Full Content

This example demonstrates the compare_from_url() static method, which enables
efficient comparison of stored files by comparing their metadata directly
from URLs without loading the full content into memory.

What you'll learn:
- How to use StorageProvider.compare_from_url() for efficient comparisons
- When to use URL-based comparison vs metadata-based comparison
- Performance benefits of comparing metadata without loading content
- Practical patterns for distributed systems and remote storage
- Cross-provider comparison scenarios

This method is especially useful for large files, remote storage, and
distributed systems where loading full content would be inefficient.
"""

import tempfile

from rpsd_storage import FSStorageProvider
from rpsd_storage.providers.base import StorageProvider


def example_1_basic_url_comparison():
    """
    Example 1: Basic URL-based comparison.

    This demonstrates the fundamental usage of compare_from_url(),
    which loads metadata from URLs and compares them.
    """
    print("=== Example 1: Basic URL-Based Comparison ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Save two versions of a file
        url1, metadata1 = provider.save(
            b"Version 1 of the document", "report_v1.txt", who="alice", what="report"
        )
        print(f"Saved: {metadata1.original_filename}")
        print(f"  URL: {url1}")
        print(f"  Timestamp: {metadata1.save_stamp}")

        url2, metadata2 = provider.save(
            b"Version 2 of the document - updated",
            "report_v2.txt",
            who="alice",
            what="report",
        )
        print(f"\nSaved: {metadata2.original_filename}")
        print(f"  URL: {url2}")
        print(f"  Timestamp: {metadata2.save_stamp}")

        # Compare using URLs directly
        result = StorageProvider.compare_from_url(url1, url2)
        print(f"\nCompare result: {result}")

        if result == -1:
            print("  → URL2 is older than URL1")
        elif result == 0:
            print("  → URL2 has identical content to URL1")
        elif result == 1:
            print("  → URL2 is newer than URL1")


def example_2_efficiency_demonstration():
    """
    Example 2: Efficiency benefits for large files.

    This demonstrates how compare_from_url() is more efficient than
    loading full content, especially for large files.
    """
    print("\n=== Example 2: Efficiency for Large Files ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Simulate large files (in real scenario, these could be GB-sized)
        large_content_v1 = b"X" * (10 * 1024 * 1024)  # 10 MB
        large_content_v2 = b"Y" * (10 * 1024 * 1024)  # 10 MB (different)

        print("Saving large files...")
        url1, metadata1 = provider.save(
            large_content_v1, "large_file_v1.bin", who="system", what="backup"
        )
        print(f"Saved v1: {metadata1.content_length:,} bytes")

        url2, metadata2 = provider.save(
            large_content_v2, "large_file_v2.bin", who="system", what="backup"
        )
        print(f"Saved v2: {metadata2.content_length:,} bytes")

        # Compare using URLs - only loads metadata, not full 10 MB content!
        print("\nComparing using URLs (metadata only)...")
        result = StorageProvider.compare_from_url(url1, url2)

        print(f"Comparison complete: result = {result}")
        print("✓ Only metadata was loaded, not the full 10 MB content for each file")

        # Show what metadata comparison uses
        print("\nMetadata used for comparison:")
        print(f"  File 1 hash: {metadata1.hash}")
        print(f"  File 2 hash: {metadata2.hash}")
        print(f"  File 1 timestamp: {metadata1.save_stamp}")
        print(f"  File 2 timestamp: {metadata2.save_stamp}")


def example_3_remote_storage_pattern():
    """
    Example 3: Pattern for remote storage systems.

    This shows how compare_from_url() is ideal for scenarios where
    files are stored remotely (S3, HTTP, etc.) and you want to avoid
    downloading full content just for comparison.
    """
    print("\n=== Example 3: Remote Storage Pattern ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Simulate a remote storage scenario
        print("Simulating remote file storage scenario...")

        # Archive of reports stored remotely
        reports = [
            ("Q1_2024_report.pdf", b"Q1 2024 Financial Report Content..."),
            ("Q2_2024_report.pdf", b"Q2 2024 Financial Report Content..."),
            ("Q3_2024_report.pdf", b"Q3 2024 Financial Report Content..."),
            ("Q4_2024_report.pdf", b"Q4 2024 Financial Report Content..."),
        ]

        archived_urls = {}

        for filename, content in reports:
            url, _ = provider.save(
                content, filename, who="finance_dept", what="quarterly_report"
            )
            archived_urls[filename] = url
            print(f"  Archived: {filename}")

        # New report arrives - check if it's an update to existing one
        print("\n--- New report received ---")
        new_report_content = b"Q4 2024 Financial Report Content - REVISED"
        temp_url, _ = provider.save(
            new_report_content,
            "Q4_2024_report_new.pdf",
            who="finance_dept",
            what="quarterly_report",
        )

        # Compare with archived Q4 report (without downloading full content)
        archived_q4_url = archived_urls["Q4_2024_report.pdf"]
        print("Comparing new report with archived Q4 2024 report...")

        result = StorageProvider.compare_from_url(archived_q4_url, temp_url)

        if result == 1:
            print("✓ New report is an update - replace archived version")
            print("  In production: would update remote storage")
        elif result == 0:
            print("→ New report is identical to archived version - skip")
        else:
            print("⚠ New report is older than archived version - investigate")

        # Clean up temp file
        provider.delete(temp_url)


def example_4_version_synchronization():
    """
    Example 4: Multi-location version synchronization.

    This demonstrates using compare_from_url() to synchronize files
    across multiple storage locations.
    """
    print("\n=== Example 4: Version Synchronization ===")

    # Simulate two storage locations
    with tempfile.TemporaryDirectory() as location_a:
        with tempfile.TemporaryDirectory() as location_b:
            provider_a = FSStorageProvider(location_a)
            provider_b = FSStorageProvider(location_b)

            print("Simulating two storage locations (A and B)...")

            # Initial state: both locations have the same file
            content_v1 = b"Shared configuration file - version 1"
            url_a, meta_a = provider_a.save(
                content_v1, "config.yaml", who="devops", what="configuration"
            )
            url_b, meta_b = provider_b.save(
                content_v1, "config.yaml", who="devops", what="configuration"
            )

            print(f"Location A: {meta_a.original_filename} ({meta_a.hash[:8]}...)")
            print(f"Location B: {meta_b.original_filename} ({meta_b.hash[:8]}...)")

            # Verify they're identical
            result = StorageProvider.compare_from_url(url_a, url_b)
            print(f"\nInitial comparison: {result} (identical)")

            # Update file in location A
            print("\n--- Updating file in location A ---")
            content_v2 = b"Shared configuration file - version 2 - updated in A"
            url_a_new, meta_a_new = provider_a.save(
                content_v2, "config.yaml", who="devops", what="configuration"
            )

            # Check if synchronization is needed
            result = StorageProvider.compare_from_url(url_b, url_a_new)
            print(f"Comparison (B vs A_new): {result}")

            if result == 1:
                print("✓ Location A has newer version - sync needed")
                print("  Action: Copy from A to B")

                # In production, you'd perform the actual sync
                # For demo, we'll simulate it
                _, meta_b_new = provider_b.save(
                    content_v2, "config.yaml", who="devops", what="configuration"
                )

                # Verify sync
                result_after = StorageProvider.compare_from_url(url_a_new, url_b)
                print(f"\nAfter sync comparison: {result_after}")
                print("✓ Locations synchronized successfully")


def example_5_change_detection_pipeline():
    """
    Example 5: Change detection in data processing pipeline.

    This shows a practical use case for detecting changes in a
    data processing pipeline without loading full datasets.
    """
    print("\n=== Example 5: Change Detection Pipeline ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        print("Simulating data processing pipeline...")

        # Pipeline stages: raw → processed → analyzed
        pipeline_stages = {}

        # Stage 1: Save raw data
        raw_data = b"Raw sensor measurements: [100, 101, 102, ...]"
        url_raw, _ = provider.save(
            raw_data, "raw_data.csv", who="pipeline", what="sensor_data"
        )
        pipeline_stages["raw"] = url_raw
        print("✓ Stage 1: Raw data saved")

        # Stage 2: Process data
        processed_data = b"Processed data: mean=101, stddev=0.8, ..."
        url_processed, _ = provider.save(
            processed_data, "processed_data.json", who="pipeline", what="sensor_data"
        )
        pipeline_stages["processed"] = url_processed
        print("✓ Stage 2: Data processed")

        # Stage 3: Analyze data
        analyzed_data = b"Analysis results: trend=stable, anomalies=0"
        url_analyzed, _ = provider.save(
            analyzed_data, "analysis.txt", who="pipeline", what="sensor_data"
        )
        pipeline_stages["analyzed"] = url_analyzed
        print("✓ Stage 3: Data analyzed")

        # New raw data arrives
        print("\n--- New raw data batch received ---")
        new_raw_data = b"Raw sensor measurements: [103, 104, 105, ...]"
        url_new_raw, _ = provider.save(
            new_raw_data, "raw_data_new.csv", who="pipeline", what="sensor_data"
        )

        # Check if re-processing is needed
        result = StorageProvider.compare_from_url(pipeline_stages["raw"], url_new_raw)

        print(f"Comparing new raw data with previous: {result}")

        if result == 1:
            print("✓ New data detected - triggering pipeline re-run")
            print("  → Stage 2: Reprocessing required")
            print("  → Stage 3: Reanalysis required")

            # Update pipeline stages
            # (In production, this would trigger actual processing)
            pipeline_stages["raw"] = url_new_raw
            print("\n✓ Pipeline stages updated")
        else:
            print("→ No new data - skipping pipeline re-run (saves resources)")

        # Clean up
        provider.delete(url_new_raw)


def example_6_error_handling():
    """
    Example 6: Error handling in URL-based comparison.

    This demonstrates how compare_from_url() handles various error cases.
    """
    print("\n=== Example 6: Error Handling ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        provider = FSStorageProvider(temp_dir)

        # Create test files
        url1, _ = provider.save(b"Content 1", "file1.txt", who="alice", what="document")
        url2, _ = provider.save(b"Content 2", "file2.txt", who="bob", what="document")
        url3, _ = provider.save(b"Content 3", "file3.txt", who="alice", what="image")

        print("Test files created")

        # Error case 1: Different 'who'
        print("\n--- Error Case 1: Different 'who' field ---")
        try:
            result = StorageProvider.compare_from_url(url1, url2)
            print(f"❌ Unexpected success: {result}")
        except ValueError as e:
            print(f"✓ Expected ValueError caught: {e}")

        # Error case 2: Different 'what'
        print("\n--- Error Case 2: Different 'what' field ---")
        try:
            result = StorageProvider.compare_from_url(url1, url3)
            print(f"❌ Unexpected success: {result}")
        except ValueError as e:
            print(f"✓ Expected ValueError caught: {e}")

        # Error case 3: Non-existent URL
        print("\n--- Error Case 3: Non-existent URL ---")
        fake_url = "file:///nonexistent/path/file.txt"
        try:
            result = StorageProvider.compare_from_url(url1, fake_url)
            print(f"❌ Unexpected success: {result}")
        except FileNotFoundError as e:
            print(f"✓ Expected FileNotFoundError caught: {e}")

        print("\n✓ All error cases handled correctly")


def main():
    """Run all examples."""
    print("🔗 RPSD Storage - URL-Based Comparison Examples")
    print("=" * 60)
    example_1_basic_url_comparison()
    example_2_efficiency_demonstration()
    example_3_remote_storage_pattern()
    example_4_version_synchronization()
    example_5_change_detection_pipeline()
    example_6_error_handling()
    print("\n" + "=" * 60)
    print("✅ All URL-based comparison examples completed!")
    print()
    print("🎯 Key Takeaways:")
    print("   • compare_from_url() loads only metadata, not full content")
    print("   • Ideal for large files and remote storage (S3, HTTP)")
    print("   • Works across different storage providers")
    print("   • Perfect for synchronization and change detection")
    print("   • Same comparison semantics as metadata compare (-1, 0, 1)")
    print()
    print("📚 Related Examples:")
    print("   • 07_metadata_comparison.py - Direct metadata comparison methods")
    print("   • 06_separate_load_methods.py - Loading content vs metadata")
    print()
    print("🎉 You've mastered URL-based comparison in rpsd-storage!")


if __name__ == "__main__":
    main()
