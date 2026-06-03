# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Generic Flow response models for rpsd-flow.

Parallel to ``TransportMessage`` on the input side. Always returned by
Flows invoked through ``run_flow`` / ``run_flow_async``.

Design notes
------------
- ``success`` (not ``ok``) mirrors ``SubprocessResult.success`` already in
  this package, keeping one word for "it worked" across rpsd-flow.
- ``status`` is a free-form ``str`` (the stringified Prefect state type,
  e.g. ``"COMPLETED"``) rather than an enum, so this module stays
  Prefect-free and tolerant of new Prefect states.
- The outcome fields (``success``/``started_at``/``finished_at``) are
  optional so a single type covers a run's whole lifecycle: a
  fire-and-forget (``timeout=0``) invocation returns a "submitted /
  not-yet-known" response, a completed run returns a fully populated one.

This module supersedes the placeholder in ``rpsd_validator/models.py``.
That placeholder uses required ``ok``/``started_at``/``finished_at`` and no
``status``; its migration to import from here (renaming ``ok`` -> ``success``
and adding ``status=``) is a separate downstream change.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from rpsd_transport.models import TransportMessage

#: ``status`` value used when no Prefect state is available for the run.
UNKNOWN_STATUS = "UNKNOWN"


class TaskResult(BaseModel):
    """Result of one Task within a Flow run.

    Fields are deliberately Flow-agnostic: a validation Task records
    pass/fail; a transformation Task records success/failure of producing
    its piece of output. ``task_name`` is the Prefect task name as
    registered with ``@task`` / ``@subprocess_task`` — no enum, no
    hardcoded literal, so adding a new Task requires no model change.
    """

    task_name: str
    success: bool
    error: str | None = None
    duration: float | None = Field(
        default=None,
        description="Wall-clock seconds the Task took to complete.",
    )


class FlowResponse(BaseModel):
    """Generic response of a Flow run that processed a TransportMessage.

    Parallel to ``TransportMessage`` on the input side. Always returned by
    ``run_flow`` / ``run_flow_async``.

    Composition over inheritance: validation Flows leave ``outgoing``
    unset; transformation Flows populate it with the produced message.

    For fire-and-forget (``timeout=0``) or still-running runs,
    ``success``/``started_at``/``finished_at`` are ``None`` and ``status``
    reflects the current Prefect state; ``task_results`` is empty until the
    run has produced per-Task detail.
    """

    incoming: TransportMessage
    outgoing: TransportMessage | None = None
    flow_name: str
    flow_run_id: UUID | None = None
    status: str = UNKNOWN_STATUS
    success: bool | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    task_results: list[TaskResult] = Field(default_factory=list)
