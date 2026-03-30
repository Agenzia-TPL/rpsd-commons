# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
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
