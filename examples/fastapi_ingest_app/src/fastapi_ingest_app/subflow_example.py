# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Subflow composition example for rpsd-flow.

Demonstrates a "higher-level" Flow invoking a "lower-level" Flow as a Prefect
subflow, waiting for it, then branching on the outcome — while still returning a
single **flat** ``FlowResponse`` the outer caller can consume without knowing a
subflow was involved.

Two flows:

1. ``validate-flow`` (lower level) — a validation Flow that another service
   would own. It returns a rich ``FlowResponse`` so the parent gets the child's
   ``success`` verbatim.
2. ``ingest-with-validation-flow`` (higher level) — saves the file (inline),
   then ``await run_flow_async("validate-flow/validate-deployment", message,
   timeout=None)`` to invoke the validator **and wait**, folds the child into
   its own response with ``add_subflow``, and runs a success/failure Task on the
   result.

The ``timeout`` lives at two independent layers:

- the external trigger (HTTP → ``ingest-with-validation-flow``) is
  fire-and-forget (``timeout=0``) — see ``main.py``;
- the parent → child call below is ``timeout=None`` (block until the child is
  terminal), because the parent's branching depends on the child's outcome.

Serve the two flows in **separate processes / work pools** (entry points
``serve-validate`` and ``serve-ingest``). A blocking parent holds a concurrency
slot for the child's whole duration; sharing one pool risks slot-starvation.

Usage::

    # Terminal A — validator on its own pool:
    cd examples/fastapi_ingest_app
    uv run serve-validate

    # Terminal B — parent on its own pool:
    cd examples/fastapi_ingest_app
    uv run serve-ingest
"""

import logging
import time
import warnings
from datetime import UTC, datetime
from typing import Any

from prefect.client.schemas.objects import State
from prefect.runtime import flow_run as flow_run_runtime

from rpsd_flow import (
    FlowResponse,
    TaskResult,
    flow,
    publish_flow_artifact,
    run_flow_async,
    serve_flows,
    task,
    to_terminal_state,
)
from rpsd_transport.models import TransportMessage

# Cosmetic only — see the note in sample_flow.py. Filters the benign Prefect 3 +
# Pydantic 2 serializer warning emitted from Prefect's own internal schemas.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
)

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
)
logger = logging.getLogger(__name__)

# Deployment name the parent uses to invoke the validator subflow.
VALIDATE_DEPLOYMENT = "validate-flow/validate-deployment"


# --- Lower-level Flow: a validator another service would own ---


@task(name="check-metadata")
def check_metadata(message: TransportMessage) -> None:
    """Cheap structural check on the message metadata."""
    if not message.who or not message.what:
        raise ValueError("message is missing required 'who'/'what' metadata")
    logger.info("Metadata OK for %s/%s", message.who, message.what)


@flow(name="validate-flow", log_prints=True)
def validate_flow(message: TransportMessage) -> FlowResponse | State:
    """Validate an ingested message; publish its outcome as an artifact.

    Builds a ``FlowResponse``, publishes it as a Markdown artifact (so the
    parent Flow / callers can read the curated outcome back via
    ``run_flow_async`` / ``get_flow_response`` — even on failure), then returns
    it green on success or a Prefect ``Failed`` state (red run) on failure via
    ``to_terminal_state``. No result persistence needed.
    """
    started_at = datetime.now(UTC)
    task_results: list[TaskResult] = []

    t0 = time.monotonic()
    try:
        check_metadata(message)
        task_results.append(
            TaskResult(
                task_name="check-metadata",
                success=True,
                duration=time.monotonic() - t0,
            )
        )
    except Exception as exc:
        task_results.append(
            TaskResult(
                task_name="check-metadata",
                success=False,
                error=str(exc),
                duration=time.monotonic() - t0,
            )
        )

    success = all(r.success for r in task_results)
    response = FlowResponse(
        incoming=message,
        flow_name="validate-flow",
        flow_run_id=flow_run_runtime.id,
        status="COMPLETED" if success else "FAILED",
        success=success,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        task_results=task_results,
    )
    publish_flow_artifact(response)
    return to_terminal_state(response)


# --- Higher-level Flow: invokes the validator as a subflow ---


@task(name="save-file")
def save_file(message: TransportMessage) -> dict[str, Any]:
    """Pretend to persist the ingested file (inline, fast)."""
    logger.info(
        "Saving file for %s/%s (where=%s)", message.who, message.what, message.where
    )
    return {"saved": True, "where": message.where}


@task(name="dispatch-success")
def dispatch_success(message: TransportMessage) -> None:
    """Dispatch a success event after validation passes."""
    logger.info("Validation succeeded — dispatching success event.")


@task(name="handle-failure")
def handle_failure(message: TransportMessage) -> None:
    """Run compensating logic after validation fails."""
    logger.warning("Validation failed — running failure handler.")


@flow(name="ingest-with-validation-flow", log_prints=True)
async def ingest_with_validation_flow(
    message: TransportMessage,
) -> FlowResponse | State:
    """Save the file, validate it via a subflow, then branch on the result.

    Invokes ``validate-flow`` as a Prefect subflow with ``timeout=None`` (waits
    for it), folds the child's outcome into this response's flat
    ``task_results`` with ``add_subflow``, then runs ``dispatch-success`` or
    ``handle-failure`` depending on ``child.success``.

    Publishes the flat ``FlowResponse`` as a Markdown artifact (the caller reads
    it back via ``get_flow_response`` — incl. the folded ``validate-flow`` row,
    with no result persistence) and ends the run green/red via
    ``to_terminal_state``.
    """
    started_at = datetime.now(UTC)
    response = FlowResponse(
        incoming=message,
        flow_name="ingest-with-validation-flow",
        flow_run_id=flow_run_runtime.id,
        status="COMPLETED",
        started_at=started_at,
    )

    # Step 1 — save the file (inline).
    t0 = time.monotonic()
    try:
        save_file(message)
        response.task_results.append(
            TaskResult(
                task_name="save-file",
                success=True,
                duration=time.monotonic() - t0,
            )
        )
    except Exception as exc:
        response.task_results.append(
            TaskResult(
                task_name="save-file",
                success=False,
                error=str(exc),
                duration=time.monotonic() - t0,
            )
        )

    # Step 2 — invoke the validator subflow and WAIT (timeout=None).
    # run_deployment from inside a flow auto-links this as a child run, so the
    # parent → child relationship shows up in the Prefect UI.
    child = await run_flow_async(VALIDATE_DEPLOYMENT, message, timeout=None)
    response.add_subflow(child)  # one flat summary row carrying child.success

    # Step 3 — branch on the child's true success.
    if child.success:
        dispatch_success(message)
    else:
        handle_failure(message)

    # The parent owns its own success: the folded child row participates in the
    # all(...) rollup through child.success, with no re-derivation.
    response.success = all(r.success for r in response.task_results)
    response.status = "COMPLETED" if response.success else "FAILED"
    response.finished_at = datetime.now(UTC)
    logger.info(
        "Flow response: success=%s, tasks=%d",
        response.success,
        len(response.task_results),
    )
    publish_flow_artifact(response)
    return to_terminal_state(response)


# --- Serving (separate processes / work pools) ---


def serve_validate() -> None:
    """Entry point for ``serve-validate``.

    Serves the lower-level validator as ``validate-flow/validate-deployment``.
    Run this in its OWN process / work pool, separate from ``serve-ingest`` —
    a blocking parent holds a slot for the child's whole duration, so sharing a
    pool risks slot-starvation/deadlock.
    """
    logger.info("Serving %s...", VALIDATE_DEPLOYMENT)
    serve_flows(validate_flow.to_deployment("validate-deployment"))


def serve_ingest() -> None:
    """Entry point for ``serve-ingest``.

    Serves the higher-level flow as
    ``ingest-with-validation-flow/ingest-deployment``. Run this in its OWN
    process / work pool, separate from ``serve-validate``.
    """
    logger.info("Serving ingest-with-validation-flow/ingest-deployment...")
    serve_flows(ingest_with_validation_flow.to_deployment("ingest-deployment"))


if __name__ == "__main__":
    serve_ingest()
