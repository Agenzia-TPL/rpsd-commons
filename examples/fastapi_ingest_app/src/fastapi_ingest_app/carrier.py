"""
Legacy: StorageHTTPCarrier was replaced by IngestProcessor.

This module is kept as a reference for the received() hook pattern.
New code should use IngestProcessor from rpsd_transport.processors
instead of subclassing carriers for storage integration.

Example migration:
    # Before (carrier subclass approach):
    carrier = StorageHTTPCarrier(storage_provider=storage)
    message = await carrier.receive(request)
    url = carrier.last_saved_url

    # After (IngestProcessor approach):
    carrier = HTTPCarrier()
    processor = IngestProcessor(storage=storage)
    message = await carrier.receive(request)
    result = processor.process(message)
    url = result.storage_url
"""
