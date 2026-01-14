"""
FastAPI application demonstrating HTTPCarrier and storage providers.

This example shows how to:
- Use HTTPCarrier.receive() to parse incoming messages
- Implement received() hook to save content to storage
- Support both inline (JSON) and outline (headers/query) metadata formats
- Validate API keys
- Configure storage providers (FS or S3) via settings
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fastapi_ingest_app.auth import validate_api_key
from fastapi_ingest_app.carrier import StorageHTTPCarrier
from fastapi_ingest_app.settings import AppSettings
from rpsd_storage import get_storage_provider
from rpsd_transport.exceptions import (
    InvalidMetadataError,
    MissingMetadataError,
    TransportError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize settings and dependencies
settings = AppSettings()
storage_provider = get_storage_provider(settings.storage)
carrier = StorageHTTPCarrier(storage_provider=storage_provider, timeout=30.0)

# Create FastAPI app
app = FastAPI(
    title="RPSD Ingest Example",
    description="Example FastAPI app using HTTPCarrier and storage providers",
    version="1.0.0",
)


@app.post("/ingest")
async def ingest_data(request: Request):
    """
    Receive and store data using HTTPCarrier and storage providers.

    Supports both metadata formats:
    - Inline: JSON body with metadata and content fields
    - Outline: Headers/query params with separate content

    Args:
        request: FastAPI Request object

    Returns:
        JSONResponse with success status and storage details

    Raises:
        401: If API key is invalid
        400: If metadata is missing or invalid
        500: For other errors
    """
    try:
        # Validate API key
        validate_api_key(request, settings.transport.api_key)

        # Use carrier to receive and parse message
        # Note: received() hook automatically saves content to storage
        message = await carrier.receive(request)

        # Verify that content was saved (should always be true after receive)
        if carrier.last_saved_metadata is None:
            raise TransportError("Failed to save content to storage")

        # Build response with storage URL
        response_data = {
            "success": True,
            "message": "Content received and stored",
            "storage_url": carrier.last_saved_url,
            "metadata": {
                "who": message.who,
                "what": message.what,
                "object_id": carrier.last_saved_metadata.object_id,
                "content_type": message.metadata.content_type,
                "content_length": carrier.last_saved_metadata.content_length,
            },
        }

        logger.info(
            f"Successfully processed message: who={message.who}, "
            f"what={message.what}, url={carrier.last_saved_url}"
        )

        return JSONResponse(status_code=201, content=response_data)

    except PermissionError as e:
        logger.warning(f"Authentication failed: {e}")
        return JSONResponse(status_code=401, content={"error": str(e)})

    except (MissingMetadataError, InvalidMetadataError) as e:
        logger.warning(f"Invalid metadata: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})

    except TransportError as e:
        logger.error(f"Transport error: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})

    except Exception as e:
        logger.exception("Unexpected error processing request")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(e),
            },
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "storage_provider": settings.storage.provider,
    }


def run():
    """Entry point for the fastapi-ingest-app command."""
    import uvicorn

    logger.info("Starting RPSD Ingest Example application")
    logger.info(f"Storage provider: {settings.storage.provider}")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run()
