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

from shared import SampleContent, create_temp_storage_dir

from rpsd_storage import FSStorageProvider


def main():
    """A simple introduction to rpsd-storage."""

    print("🚀 Getting Started with rpsd-storage")
    print("=" * 40)
    print()

    # Step 1: Create a storage provider
    print("Step 1: Setting up storage")
    print("-" * 25)

    with create_temp_storage_dir() as temp_dir:
        # For this example, we'll store files in a temporary directory
        storage = FSStorageProvider(base_path=temp_dir)
        print(f"✅ Created file storage in: {temp_dir}")
        print()

        # Step 2: Save your first file
        print("Step 2: Saving a file")
        print("-" * 20)

        # Let's save a simple text document
        document_content = SampleContent.SIMPLE_TEXT

        # The save() method returns an "object_id" - think of it as a receipt
        # You'll use this ID later to retrieve your file
        object_id = storage.save(
            content=document_content,           # The actual file data
            filename="my_document.txt",        # Original filename (for reference)
            content_type="text/plain"          # What type of file this is
        )

        print(f"✅ File saved! Your object ID is: {object_id}")
        print("   Original filename: my_document.txt")
        print(f"   Content: {document_content.decode('utf-8')}")
        print()

        # Step 3: Load your file back
        print("Step 3: Loading the file back")
        print("-" * 28)

        # Use the object_id to get your file back
        loaded_file = storage.load(object_id)

        # loaded_file contains both the content and metadata
        content = loaded_file["content"]           # The original file data
        metadata = loaded_file["metadata"]        # Information about the file

        print("✅ File loaded successfully!")
        print(f"   Content: {content.decode('utf-8')}")
        print(f"   Original filename: {metadata['original_filename']}")
        print(f"   File type: {metadata['content_type']}")
        print()

        # Step 4: Understanding what happened
        print("🎉 Success! Here's what happened:")
        print("-" * 35)
        print("1. You saved a file and got an object_id")
        print("2. rpsd-storage stored both your file AND metadata about it")
        print("3. You used the object_id to retrieve everything back")
        print()
        print("💡 Key concepts:")
        print("   • object_id = unique identifier for your saved file")
        print("   • content = your actual file data (as bytes)")
        print("   • metadata = information about the file (name, type, etc.)")
        print()
        print("📚 Ready for more? Try the other examples:")
        print("   • 02_basic_usage.py - Save different types of files")
        print("   • 03_metadata_and_types.py - Add custom metadata")
        print("   • 04_advanced_features.py - Error handling and advanced features")


if __name__ == "__main__":
    main()
