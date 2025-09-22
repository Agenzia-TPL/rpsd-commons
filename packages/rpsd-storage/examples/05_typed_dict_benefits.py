#!/usr/bin/env python3
"""
TypedDict Benefits - Type Safety in Action

This example demonstrates the type safety benefits of using TypedDict
for the load method return values in rpsd-storage.

What you'll learn:
- How TypedDict provides compile-time type checking
- IDE autocompletion and error detection
- Type-safe functions that work with LoadResult
- Best practices for typed code

This is an advanced example showing modern Python typing features.
"""

import tempfile
from typing import Any

from rpsd_storage import FSStorageProvider
from rpsd_storage.provider import LoadResult


def analyze_file_content(result: LoadResult) -> dict[str, Any]:
    """
    Analyze file content with full type safety.

    Args:
        result: TypedDict LoadResult from storage.load()

    Returns:
        dict: Analysis results with type-safe access
    """
    # TypedDict ensures we know exactly what we're getting
    content: bytes = result["content"]              # IDE knows this is bytes
    metadata: dict[str, Any] = result["metadata"]  # IDE knows this is dict

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
    Process multiple files with type safety throughout.

    Args:
        storage: Storage provider instance
        object_ids: List of object IDs to process

    Returns:
        list: Analysis results for each file
    """
    results: list[dict[str, Any]] = []

    for object_id in object_ids:
        try:
            # Load with TypedDict - IDE knows the structure
            load_result: LoadResult = storage.load(object_id)

            # Type-safe analysis
            analysis = analyze_file_content(load_result)
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


def extract_metadata_safely(result: LoadResult, field: str, default: Any = None) -> Any:
    """
    Safely extract metadata field with type checking.

    Args:
        result: TypedDict LoadResult
        field: Metadata field name
        default: Default value if field missing

    Returns:
        The field value or default
    """
    # TypedDict ensures metadata is properly typed
    metadata: dict[str, Any] = result["metadata"]
    return metadata.get(field, default)


def validate_file_integrity(result: LoadResult) -> bool:
    """
    Validate file integrity using TypedDict structure.

    Args:
        result: LoadResult to validate

    Returns:
        bool: True if file appears valid
    """
    # Type-safe structure validation
    content: bytes = result["content"]
    metadata: dict[str, Any] = result["metadata"]

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


def demonstrate_type_safety_benefits():
    """Demonstrate the benefits of TypedDict in practice."""

    print("🔍 TypedDict Benefits Demonstration")
    print("=" * 38)
    print("This example shows how TypedDict provides type safety")
    print("for rpsd-storage load operations.")
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

        # Demonstrate type-safe loading
        print("🔒 Type-Safe File Loading")
        print("-" * 26)

        for i, object_id in enumerate(object_ids):
            # Load with TypedDict type annotation
            result: LoadResult = storage.load(object_id)

            # Type-safe access - IDE knows these types!
            content: bytes = result["content"]
            metadata: dict[str, Any] = result["metadata"]
            filename: str = metadata["original_filename"]

            print(f"   📄 File {i+1}: {filename}")
            print(f"      Content type: {type(content).__name__}")
            print(f"      Metadata type: {type(metadata).__name__}")
            print(f"      Size: {len(content)} bytes")

            # Validate with type safety
            is_valid = validate_file_integrity(result)
            print(f"      Valid: {'✅' if is_valid else '❌'}")
            print()

        # Demonstrate batch processing
        print("📊 Batch Processing with Type Safety")
        print("-" * 36)

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

        # Demonstrate type-safe metadata extraction
        print("🏷️  Type-Safe Metadata Extraction")
        print("-" * 33)

        first_result: LoadResult = storage.load(object_ids[0])

        # Safe extraction with type checking
        who = extract_metadata_safely(first_result, "who", "unknown")
        what = extract_metadata_safely(first_result, "what", "unknown")
        timestamp = extract_metadata_safely(first_result, "ingestion_timestamp")

        print(f"   Who: {who} (type: {type(who).__name__})")
        print(f"   What: {what} (type: {type(what).__name__})")
        print(f"   When: {timestamp} (type: {type(timestamp).__name__})")
        print()

        # Show the benefits
        print("🎯 Benefits Summary")
        print("-" * 17)
        print("✅ IDE autocompletion for dictionary keys")
        print("✅ Static type checking catches errors early")
        print("✅ Clear documentation of function contracts")
        print("✅ Better refactoring support")
        print("✅ Improved code maintainability")
        print("✅ Runtime type validation possible")
        print()

        print("💡 TypedDict Best Practices:")
        print("• Always annotate LoadResult variables")
        print("• Use type hints in function signatures")
        print("• Validate structure when needed")
        print("• Extract metadata safely with defaults")
        print("• Leverage IDE features for better development")


def main():
    """Run the TypedDict benefits demonstration."""
    demonstrate_type_safety_benefits()

    print("🎉 TypedDict demonstration complete!")
    print("   Your IDE and type checker now have full knowledge")
    print("   of the rpsd-storage load method return structure.")
    print()
    print("📚 Continue learning:")
    print("   • Use mypy or similar tools for static type checking")
    print("   • Enable type hints in your IDE for better development")
    print("   • Write type-safe functions that work with LoadResult")


if __name__ == "__main__":
    main()
