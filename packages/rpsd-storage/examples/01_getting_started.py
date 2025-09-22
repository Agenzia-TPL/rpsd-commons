#!/usr/bin/env python3
"""
Getting Started with rpsd-storage

This example shows the absolute basics of saving and loading files
with rpsd-storage. Perfect for first-time users!

What you'll learn:
- How to save a file
- How to load a file back
- What an "object_id" is and why it matters

This is a 5-minute introduction to get you up and running.
"""

import tempfile
from typing import Any

from rpsd_storage import FSStorageProvider

# LoadResult removed - now using tuples directly


def demonstrate_type_safety(content: bytes, metadata: dict[str, Any]) -> None:
    """
    Demonstrate the ergonomic benefits of tuple unpacking.

    With tuple unpacking, you get direct access to content and metadata!
    """
    print("🔍 Tuple Unpacking Demonstration")
    print("-" * 33)

    # Tuple unpacking gives us direct access to both values

    # Access metadata with type safety
    filename: str = metadata["original_filename"]  # IDE knows this is str
    file_type: str = metadata["content_type"]  # IDE knows this is str
    object_id: str = metadata["object_id"]  # IDE knows this is str

    print("✅ Type-safe access to all fields:")
    print(f"   • Content: {type(content).__name__} ({len(content)} bytes)")
    print(f"   • Filename: {type(filename).__name__} ('{filename}')")
    print(f"   • File type: {type(file_type).__name__} ('{file_type}')")
    print(f"   • Object ID: {type(object_id).__name__} ('{object_id}')")
    print()

    # With TypedDict, you get IDE autocompletion and type checking!
    print("💡 Benefits of Tuple Unpacking:")
    print("   • Direct access to content and metadata")
    print("   • Ergonomic - no dictionary key access needed")
    print("   • Aligns with save() creating two things")
    print("   • Clean, Pythonic unpacking syntax")
    print()


def main():
    """A simple introduction to rpsd-storage."""

    print("🚀 Getting Started with rpsd-storage")
    print("=" * 40)
    print()

    # Step 1: Create a storage provider
    print("Step 1: Setting up storage")
    print("-" * 25)

    with tempfile.TemporaryDirectory() as temp_dir:
        # For this example, we'll store files in a temporary directory
        storage = FSStorageProvider(base_path=temp_dir)
        print(f"✅ Created file storage in: {temp_dir}")
        print()

        # Step 2: Save your first file
        print("Step 2: Saving a file")
        print("-" * 20)

        # Let's save a simple text document
        document_content = b"Hello, World! This is my first file with rpsd-storage."

        # The save() method now returns a URL and metadata
        # The URL is a complete identifier for your file
        url, metadata = storage.save(
            content=document_content,  # The actual file data
            filename="my_document.txt",  # Original filename (for reference)
            content_type="text/plain",  # What type of file this is
            who="user123",  # Who saved this file
            what="document",  # What type of data this is
        )

        print(f"✅ File saved! Your URL is: {url}")
        print("   Original filename: my_document.txt")
        print(f"   Object ID: {metadata['object_id']}")
        print(f"   Content: {document_content.decode('utf-8')}")
        print()

        # Step 3: Load your file back
        print("Step 3: Loading the file back")
        print("-" * 28)

        # Use the URL to get your file back - now with tuple unpacking!
        content, metadata = storage.load(url)

        # Direct access to both content and metadata

        print("✅ File loaded successfully!")
        print(f"   Content: {content.decode('utf-8')}")
        print(f"   Original filename: {metadata['original_filename']}")
        print(f"   File type: {metadata['content_type']}")
        print()

        # Step 4: Understanding what happened
        print("🎉 Success! Here's what happened:")
        print("-" * 35)
        print("1. You saved a file and got a URL and metadata")
        print("2. rpsd-storage stored both your file AND metadata about it")
        print("3. You used the URL to retrieve everything back")
        print()
        print("💡 Key concepts:")
        print("   • URL = complete identifier for your saved file (with provider info)")
        print("   • object_id = unique UUID for the file")
        print("   • content = your actual file data (as bytes)")
        print("   • metadata = information about the file (name, type, etc.)")
        print()

        # Demonstrate the new convenience methods
        print("🔧 New convenience methods:")
        print("-" * 27)
        print("You can also load using separate who/what/object_id:")

        # Use the convenience method
        content2, metadata2 = storage.load_by_parts(
            "user123", "document", metadata["object_id"]
        )
        assert content == content2
        print("✅ Loaded using load_by_parts() method!")
        print()

        # Show static methods
        print("📦 Static methods (work with any provider):")
        print("-" * 44)
        from rpsd_storage import load_from_url, load_from_parts

        content3, metadata3 = load_from_url(url)
        assert content == content3
        print("✅ Loaded using static load_from_url() method!")

        # Note: load_from_parts() uses the default configured provider
        # For this demo, we'll skip it since we're using a temporary directory
        print("📝 Note: load_from_parts() would use the configured default provider")
        print()

        # Demonstrate tuple unpacking benefits
        demonstrate_type_safety(content, metadata)

        print("📚 Ready for more? Try the other examples:")
        print("   • 02_basic_usage.py - Save different types of files")
        print("   • 03_metadata_and_types.py - Add custom metadata")
        print("   • 04_advanced_features.py - Error handling and advanced features")


if __name__ == "__main__":
    main()
