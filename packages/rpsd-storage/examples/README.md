# rpsd-storage Examples

Welcome to the rpsd-storage examples! This directory contains a comprehensive tutorial series that will teach you everything you need to know about using rpsd-storage in your applications.

## What is rpsd-storage?

rpsd-storage is a Python library that provides a simple, consistent interface for saving and retrieving files with rich metadata. Whether you're building a document management system, data processing pipeline, or need reliable file storage with tracking, rpsd-storage makes it easy.

### Key Features

- **Simple API** - Save and load files with just a few lines of code
- **Rich Metadata** - Track who saved files, what they contain, and where they came from
- **Multiple Storage Backends** - File system, S3, and more (with consistent interface)
- **Automatic Organization** - Files are organized and named automatically
- **Production Ready** - Error handling, configuration, and monitoring support

## Learning Path

The examples are designed as a progressive tutorial. **Start with `01_getting_started.py`** and work your way through each example:

### 🚀 [01_getting_started.py](./01_getting_started.py)
**"Your first 5 minutes with rpsd-storage"**

Perfect for absolute beginners. Learn the core concepts:
- How to save your first file
- How to load it back
- What an "object_id" is and why it matters

**Time investment:** 5 minutes
**Prerequisites:** None

### 📁 [02_basic_usage.py](./02_basic_usage.py)
**"Working with different file types"**

Expand your knowledge with real-world scenarios:
- Save text, JSON, CSV, and binary files
- Understand content types and why they matter
- See common use cases (logs, data exports, documents)

**Time investment:** 10 minutes
**Prerequisites:** Complete `01_getting_started.py`

### 🏷️ [03_metadata_and_types.py](./03_metadata_and_types.py)
**"Adding context with metadata"**

Learn to add rich context to your files:
- Use `who`, `what`, and `source_url` metadata
- Organize files by purpose and origin
- Use predefined metadata patterns
- Understand why metadata matters in production

**Time investment:** 15 minutes
**Prerequisites:** Complete previous examples

### 🚀 [04_advanced_features.py](./04_advanced_features.py)
**"Production-ready patterns"**

Master advanced concepts for production use:
- Error handling and edge cases
- Configuration patterns for different environments
- Bulk operations and performance considerations
- Processing pipelines and monitoring

**Time investment:** 20 minutes
**Prerequisites:** Complete previous examples

### 🔍 [05_typed_dict_benefits.py](./05_typed_dict_benefits.py)
**"Type safety with TypedDict"**

Discover the benefits of modern Python typing:
- TypedDict for compile-time type checking
- IDE autocompletion and error detection
- Type-safe functions with LoadResult
- Best practices for typed code

**Time investment:** 15 minutes
**Prerequisites:** Understanding of Python type hints

## Quick Start

If you want to jump right in:

```python
from rpsd_storage import FSStorageProvider
from rpsd_storage.provider import LoadResult  # TypedDict for type safety

# Create a storage provider
storage = FSStorageProvider(base_path="/path/to/storage")

# Save a file
content = b"Hello, World!"
object_id = storage.save(
    content=content,
    filename="hello.txt",
    content_type="text/plain"
)

# Load it back with TypedDict type safety
loaded_file: LoadResult = storage.load(object_id)
print(loaded_file["content"])  # b"Hello, World!" (IDE knows this is bytes)
print(loaded_file["metadata"]["original_filename"])  # "hello.txt" (typed access)
```

## Running the Examples

Each example is a standalone Python script. You can run them individually:

```bash
# Make sure you're in the rpsd-storage package directory
cd packages/rpsd-storage

# Run any example
uv run python examples/01_getting_started.py
uv run python examples/02_basic_usage.py
# ... and so on
```

## Common Use Cases

rpsd-storage is perfect for:

### 📄 Document Management
- User file uploads
- Document archival and retrieval
- Version control for documents
- Compliance and audit trails

### 📊 Data Processing
- ETL pipeline intermediate storage
- Data export and backup
- Analytics data archival
- Processing result storage

### 🔧 Application Support
- Configuration backup and restore
- Log file archival
- Cache and temporary file management
- Application state snapshots

### 🏢 Enterprise Integration
- API response caching
- Inter-service data exchange
- Backup and disaster recovery
- Compliance documentation

## Storage Providers

rpsd-storage supports multiple storage backends:

### File System Storage (`FSStorageProvider`)
- **Use for:** Development, single-server deployments, local caching
- **Benefits:** Simple, fast, no external dependencies
- **Configuration:** Just specify a directory path

### S3 Storage (`S3StorageProvider`)
- **Use for:** Production, distributed systems, cloud deployments
- **Benefits:** Scalable, durable, globally accessible
- **Configuration:** Requires AWS credentials and bucket name

## Configuration

### Environment Variables
```bash
export STORAGE_PROVIDER=fs
export FS_BASE_PATH=/var/app/storage

# Or for S3
export STORAGE_PROVIDER=s3
export S3_BUCKET_NAME=my-app-storage
```

### Programmatic Configuration
```python
# Direct configuration
from rpsd_storage import FSStorageProvider
storage = FSStorageProvider(base_path="/custom/path")

# Factory pattern (uses environment variables)
from rpsd_storage import get_storage_provider
storage = get_storage_provider()
```

## TypedDict Benefits

rpsd-storage uses **TypedDict** for the `load()` method return type, providing:

### 🔍 **Type Safety**
```python
from rpsd_storage.provider import LoadResult

result: LoadResult = storage.load(object_id)
content: bytes = result["content"]      # IDE knows this is bytes
metadata: dict = result["metadata"]     # IDE knows this is dict
```

### 💡 **IDE Support**
- **Autocompletion** for dictionary keys (`"content"`, `"metadata"`)
- **Error detection** for typos in key names
- **Type checking** with mypy or similar tools
- **Better refactoring** support

### 📝 **Clear Documentation**
The `LoadResult` TypedDict clearly documents what the `load()` method returns:
```python
class LoadResult(TypedDict):
    content: bytes              # The file content
    metadata: dict[str, Any]    # File metadata and information
```

### 🔧 **Type-Safe Functions**
Write functions that work with LoadResult:
```python
def analyze_file(result: LoadResult) -> dict:
    content: bytes = result["content"]
    metadata: dict = result["metadata"]
    return {"size": len(content), "type": metadata["content_type"]}
```

## Best Practices

### Metadata Design
- Use consistent `who` values (service names, user IDs)
- Use descriptive `what` values (document_upload, data_export, etc.)
- Include `source_url` for traceability
- Design metadata for your specific use case

### Error Handling
```python
try:
    loaded_file = storage.load(object_id)
except FileNotFoundError:
    # Handle missing files gracefully
    print("File not found - may have been deleted")
except Exception as e:
    # Handle other storage errors
    print(f"Storage error: {e}")
```

### Organization
- Use separate storage providers for different purposes
- Organize by date hierarchies for time-series data
- Consider storage limits and cleanup policies
- Plan for backup and disaster recovery

### Performance
- Batch operations when processing many files
- Consider file size limits for your storage backend
- Monitor storage usage and performance
- Use appropriate content types for better organization

## Getting Help

- **Examples not working?** Make sure you've installed dependencies with `uv sync`
- **API questions?** Check the source code in `src/rpsd_storage/`
- **Production issues?** Review the advanced examples and error handling patterns

## Next Steps

After completing the examples:

1. **Integrate with your application** - Start with file system storage for simplicity
2. **Add error handling** - Use the patterns from `04_advanced_features.py`
3. **Use TypedDict** - Import `LoadResult` for type safety in your code
4. **Plan your metadata** - Design consistent metadata for your use case
5. **Enable type checking** - Use mypy or similar tools to catch errors early
6. **Consider S3** - For production deployments requiring scale and durability
7. **Monitor and maintain** - Add logging and monitoring for storage operations

## Contributing

Found an issue with the examples or want to suggest improvements?

- The examples use shared utilities in `shared.py`
- Tests use similar utilities in `../tests/test_utils.py`
- Follow the existing patterns for consistency

---

**Happy coding with rpsd-storage!** 🎉

*These examples demonstrate rpsd-storage's file system provider. The same patterns work with all storage providers - just change the provider class.*