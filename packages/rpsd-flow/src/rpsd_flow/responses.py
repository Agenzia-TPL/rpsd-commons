# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
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

    An outcome *report*: it records what happened to ``incoming``, not a
    produced message. A Flow that emits a new message does so as a
    side-effect (e.g. a final Task publishes to a broker) or records a
    storage URL in a ``TaskResult`` — the produced artifact is not carried
    back inline here.

    For fire-and-forget (``timeout=0``) or still-running runs,
    ``success``/``started_at``/``finished_at`` are ``None`` and ``status``
    reflects the current Prefect state; ``task_results`` is empty until the
    run has produced per-Task detail.
    """

    incoming: TransportMessage
    flow_name: str
    flow_run_id: UUID | None = None
    status: str = UNKNOWN_STATUS
    success: bool | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    task_results: list[TaskResult] = Field(default_factory=list)

    def add_subflow(
        self,
        child: "FlowResponse",
        *,
        detail: bool = False,
        prefix: str | None = None,
    ) -> "FlowResponse":
        """Fold a child subflow's outcome into this response's ``task_results``.

        A parent Flow that invokes a lower-level Flow as a subflow (via
        ``run_flow_async(..., timeout=None)``) uses this to roll the child's
        outcome into its own response. The result stays **flat**: the outer
        caller sees one uniform list of :class:`TaskResult` and need not know a
        subflow was involved. Returns ``self`` for chaining.

        Does **not** modify ``self.success`` — the parent Flow owns its own
        success semantic. The child's true ``success`` is carried verbatim in
        the appended row(s), so it participates faithfully if the parent
        computes ``success = all(r.success for r in self.task_results)``.

        Precondition: ``child`` is terminal (the parent waited with
        ``timeout=None``), i.e. ``child.success`` is ``True``/``False``, not
        ``None``.

        Args:
            child: The :class:`FlowResponse` returned by the subflow.
            detail: When ``False`` (default), append a single summary row
                (``task_name = prefix or child.flow_name``,
                ``success = child.success``, ``error`` = first failing child
                row's error, ``duration`` from the child's
                ``started_at``/``finished_at``). Robust — reflects
                ``child.success`` even when the child reported no per-Task
                detail. When ``True``, append every child :class:`TaskResult`,
                each ``task_name`` prefixed
                ``"<prefix or child.flow_name>/<task_name>"`` to guarantee
                uniqueness; best when the child returns its own rich
                ``task_results``.
            prefix: Label used for the summary row name (``detail=False``) or as
                the namespace prefix (``detail=True``). Defaults to
                ``child.flow_name``. Pass an explicit value to disambiguate the
                same subflow invoked more than once.

        Returns:
            ``self``, with the folded row(s) appended to ``task_results``.
        """
        label = prefix or child.flow_name
        if detail:
            self.task_results.extend(
                TaskResult(
                    task_name=f"{label}/{tr.task_name}",
                    success=tr.success,
                    error=tr.error,
                    duration=tr.duration,
                )
                for tr in child.task_results
            )
            return self

        duration = None
        if child.started_at is not None and child.finished_at is not None:
            duration = (child.finished_at - child.started_at).total_seconds()
        error = next(
            (tr.error for tr in child.task_results if not tr.success and tr.error),
            None,
        )
        self.task_results.append(
            TaskResult(
                task_name=label,
                success=bool(child.success),
                error=error,
                duration=duration,
            )
        )
        return self
