"""
Processors for rpsd-transport.

Processors handle post-receive message orchestration (resolve,
save, forward) and work with any carrier type.
"""

from rpsd_transport.processors.ingest import IngestProcessor, IngestResult

__all__ = [
    "IngestProcessor",
    "IngestResult",
]
