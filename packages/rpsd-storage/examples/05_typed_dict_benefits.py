#!/usr/bin/env python3
"""
Tuple Unpacking Benefits - Ergonomic Data Access

This example demonstrates the ergonomic benefits of using tuple unpacking
for the load method return values in rpsd-storage.

What you'll learn:
- How tuple unpacking provides direct access to content and metadata
- Clean, Pythonic syntax for handling load results
- Functions that work efficiently with unpacked data
- Best practices for tuple-based APIs

This example shows how tuples align with the save/load conceptual model.
"""

import tempfile
from typing import Any

from rpsd_storage import FSStorageProvider

# LoadResult removed - now using tuples directly


def analyze_file_content(content: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze file content with direct tuple access.

    Args:
        content: File content as bytes
        metadata: File metadata dictionary

    Returns:
        dict: Analysis results with direct access
    """
    # Direct access to unpacked values

    # Type-safe metadata access
    filename: str = metadata["original_filename"]
    content_type: str = metadata["content_type"]
    object_id: str = metadata["object_id"]

    # Analyze content based on type
    analysis = {
        "filename": filename,
        "content_type": content_type,
        "object_id": object_id,
        "size_bytes": len(content),
        "size_mb": round(len(content) / (1024 * 1024), 3),
        "is_text": content_type.startswith("text/"),
        "is_binary": not content_type.startswith("text/"),
    }

    # Type-safe content analysis
    if content_type.startswith("text/"):
        try:
            text_content: str = content.decode("utf-8")
            analysis.update({
                "line_count": len(text_content.splitlines()),
                "char_count": len(text_content),
                "word_count": len(text_content.split()),
            })
        except UnicodeDecodeError:
            analysis["encoding_error"] = True

    return analysis


def batch_process_files(
    storage: FSStorageProvider, object_ids: list[str]
) -> list[dict[str, Any]]:
    """
    Process multiple files with tuple unpacking throughout.

    Args:
        storage: Storage provider instance
        object_ids: List of object IDs to process

    Returns:
        list: Analysis results for each file
    """
    results: list[dict[str, Any]] = []

    for object_id in object_ids:
        try:
            # Load with tuple unpacking - direct access to values
            content, metadata = storage.load(object_id)

            # Direct analysis with unpacked values
            analysis = analyze_file_content(content, metadata)
            analysis["status"] = "success"

            results.append(analysis)

        except Exception as e:
            # Error handling with type safety
            error_result = {
                "object_id": object_id,
                "status": "error",
                "error_message": str(e),
                "error_type": type(e).__name__
            }
            results.append(error_result)

    return results


def extract_metadata_safely(
    metadata: dict[str, Any], field: str, default: Any = None
) -> Any:
    """
    Safely extract metadata field with type checking.

    Args:
        metadata: Metadata dictionary from unpacked tuple
        field: Metadata field name
        default: Default value if field missing

    Returns:
        The field value or default
    """
    # Direct access to metadata from unpacked tuple
    return metadata.get(field, default)


def validate_file_integrity(content: bytes, metadata: dict[str, Any]) -> bool:
    """
    Validate file integrity using unpacked tuple values.

    Args:
        content: File content from unpacked tuple
        metadata: Metadata from unpacked tuple

    Returns:
        bool: True if file appears valid
    """
    # Direct validation with unpacked values

    # Check required fields exist
    required_fields = ["object_id", "original_filename", "content_type"]
    for field in required_fields:
        if field not in metadata:
            return False

    # Check content exists
    if not content or len(content) == 0:
        return False

    # Check metadata types
    if not isinstance(metadata["object_id"], str):
        return False
    if not isinstance(metadata["original_filename"], str):
        return False
    if not isinstance(metadata["content_type"], str):
        return False

    return True


def demonstrate_tuple_unpacking_benefits():
    """Demonstrate the benefits of tuple unpacking in practice."""

    print("🔍 Tuple Unpacking Benefits Demonstration")
    print("=" * 44)
    print("This example shows how tuple unpacking provides ergonomic")
    print("and clean access to rpsd-storage load results.")
    print()

    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FSStorageProvider(base_path=temp_dir)

        # Create test files
        test_files = [
            (b"Hello, TypedDict world!", "greeting.txt", "text/plain"),
            (
                b'{"name": "TypedDict", "awesome": true}',
                "data.json",
                "application/json"
            ),
            (
                b"name,value\nTypedDict,excellent\nType Safety,important",
                "report.csv",
                "text/csv"
            ),
        ]

        print("📁 Creating Test Files")
        print("-" * 22)

        object_ids = []
        for content, filename, content_type in test_files:
            object_id = storage.save(
                content=content,
                filename=filename,
                content_type=content_type,
                who="typed_demo",
                what="type_safety_example"
            )
            object_ids.append(object_id)
            print(f"   ✅ Created: {filename} ({object_id})")

        print()

        # Demonstrate tuple unpacking loading
        print("🔒 Tuple Unpacking File Loading")
        print("-" * 32)

        for i, object_id in enumerate(object_ids):
            # Load with tuple unpacking - direct access!
            content, metadata = storage.load(object_id)

            # Direct access to unpacked values
            filename: str = metadata["original_filename"]

            print(f"   📄 File {i+1}: {filename}")
            print(f"      Content type: {type(content).__name__}")
            print(f"      Metadata type: {type(metadata).__name__}")
            print(f"      Size: {len(content)} bytes")

            # Validate with unpacked values
            is_valid = validate_file_integrity(content, metadata)
            print(f"      Valid: {'✅' if is_valid else '❌'}")
            print()

        # Demonstrate batch processing
        print("📊 Batch Processing with Tuple Unpacking")
        print("-" * 42)

        analysis_results = batch_process_files(storage, object_ids)

        for result in analysis_results:
            if result["status"] == "success":
                print(f"   📈 {result['filename']}")
                print(f"      Type: {result['content_type']}")
                print(f"      Size: {result['size_bytes']:,} bytes")
                if result.get("line_count"):
                    print(f"      Lines: {result['line_count']}")
                    print(f"      Words: {result['word_count']}")
                print()

        # Demonstrate tuple-based metadata extraction
        print("🏷️  Tuple-Based Metadata Extraction")
        print("-" * 37)

        content, metadata = storage.load(object_ids[0])

        # Safe extraction with unpacked metadata
        who = extract_metadata_safely(metadata, "who", "unknown")
        what = extract_metadata_safely(metadata, "what", "unknown")
        timestamp = extract_metadata_safely(metadata, "ingestion_timestamp")

        print(f"   Who: {who} (type: {type(who).__name__})")
        print(f"   What: {what} (type: {type(what).__name__})")
        print(f"   When: {timestamp} (type: {type(timestamp).__name__})")
        print()

        # Show the benefits
        print("🎯 Benefits Summary")
        print("-" * 17)
        print("✅ Direct access to content and metadata")
        print("✅ Ergonomic - no dictionary access needed")
        print("✅ Aligns with save() creating two things")
        print("✅ Clean, Pythonic unpacking syntax")
        print("✅ Reduced cognitive overhead")
        print("✅ More intuitive API design")
        print()

        print("💡 Tuple Unpacking Best Practices:")
        print("• Always unpack immediately after load()")
        print("• Use descriptive variable names")
        print("• Pass unpacked values to functions directly")
        print("• Leverage tuple unpacking in function arguments")
        print("• Keep the conceptual model of save/load simple")


def main():
    """Run the tuple unpacking benefits demonstration."""
    demonstrate_tuple_unpacking_benefits()

    print("🎉 Tuple unpacking demonstration complete!")
    print("   You now have direct, ergonomic access to")
    print("   rpsd-storage content and metadata.")
    print()
    print("📚 Continue learning:")
    print("   • Use tuple unpacking consistently in your code")
    print("   • Pass unpacked values directly to functions")
    print("   • Embrace the conceptual alignment of save/load")


if __name__ == "__main__":
    main()
