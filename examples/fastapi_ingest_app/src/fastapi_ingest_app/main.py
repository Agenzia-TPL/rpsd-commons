"""
FastAPI application demonstrating HTTPCarrier with IngestProcessor.

This example shows how to:
- Use HTTPCarrier.receive() to parse incoming messages
- Use IngestProcessor to save content to storage
- Support both inline (JSON) and outline (headers/query) metadata formats
- Validate API keys
- Configure storage providers (FS or S3) via settings
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fastapi_ingest_app.auth import validate_api_key
from fastapi_ingest_app.settings import AppSettings
from rpsd_storage import get_storage_provider
from rpsd_transport.carriers.http import HTTPCarrier
from rpsd_transport.exceptions import (
    InvalidMetadataError,
    MissingMetadataError,
    TransportError,
)
from rpsd_transport.processors.ingest import IngestProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize settings and dependencies
settings = AppSettings()
storage_provider = get_storage_provider(settings.storage)
carrier = HTTPCarrier(timeout=30.0)
processor = IngestProcessor(storage=storage_provider)

# Create FastAPI app
app = FastAPI(
    title="RPSD Ingest Example",
    description=("Example FastAPI app using HTTPCarrier and IngestProcessor"),
    version="1.0.0",
)


@app.post("/ingest")
async def ingest_data(request: Request):
    """
    Receive and store data using HTTPCarrier and IngestProcessor.

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

        # Receive and parse message via carrier
        message = await carrier.receive(request)

        # Process: resolve heavy content + save to storage
        result = processor.process(message)

        # Build response with storage URL
        response_data = {
            "success": True,
            "message": "Content received and stored",
            "storage_url": result.storage_url,
            "metadata": {
                "who": message.who,
                "what": message.what,
                "content_type": message.metadata.content_type,
            },
        }

        if result.storage_metadata is not None:
            response_data["metadata"]["object_id"] = result.storage_metadata.object_id
            response_data["metadata"]["content_length"] = (
                result.storage_metadata.content_length
            )

        logger.info(
            "Successfully processed message: who=%s, what=%s, url=%s",
            message.who,
            message.what,
            result.storage_url,
        )

        return JSONResponse(status_code=201, content=response_data)

    except PermissionError as e:
        logger.warning("Authentication failed: %s", e)
        return JSONResponse(status_code=401, content={"error": str(e)})

    except (MissingMetadataError, InvalidMetadataError) as e:
        logger.warning("Invalid metadata: %s", e)
        return JSONResponse(status_code=400, content={"error": str(e)})

    except TransportError as e:
        logger.error("Transport error: %s", e)
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
