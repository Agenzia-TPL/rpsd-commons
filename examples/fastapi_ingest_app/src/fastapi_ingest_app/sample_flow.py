"""
Sample Prefect Flow for the FastAPI Ingest Example.

Demonstrates a realistic three-task pipeline:

1. **validate_message** — fast task that checks metadata
   and logs message details.
2. **process_content** — slow subprocess task (via
   ``subprocess_task``) that calls an external
   script to simulate heavy processing.
3. **finalize** — fast task that runs after the subprocess
   completes, logs the outcome, and performs cleanup.

Usage::

    # Serve the flow as a Prefect deployment:
    cd examples/fastapi_ingest_app
    uv run sample-flow

    # Serve the task server (separate process):
    cd examples/fastapi_ingest_app
    uv run sample-task

    # Or run directly:
    uv run python -m fastapi_ingest_app.sample_flow
"""

import logging
from pathlib import Path
from typing import Any

from rpsd_flow import (
    SubprocessResult,
    flow,
    serve_flows,
    serve_tasks,
    subprocess_task,
    task,
)
from rpsd_transport.models import TransportMessage

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
)
logger = logging.getLogger(__name__)

# Path to the subprocess script, relative to the example
# root (examples/fastapi_ingest_app/).
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


# --- Task 1: fast validation ---


@task(name="validate-message")
def validate_message(
    message: TransportMessage,
) -> dict[str, Any]:
    """Validate and summarise the incoming message.

    Checks that required metadata is present, logs the
    details, and returns a summary dict for downstream tasks.
    """
    logger.info("Validating message...")
    logger.info("  Who: %s", message.who)
    logger.info("  What: %s", message.what)
    logger.info(
        "  Content-Type: %s",
        message.metadata.content_type,
    )
    logger.info("  Storage URL: %s", message.where)

    custom = message.metadata.custom_metadata
    if custom:
        logger.info(
            "  Custom metadata keys: %s",
            list(custom.keys()),
        )

    summary = {
        "who": message.who,
        "what": message.what,
        "where": message.where,
        "content_type": message.metadata.content_type,
        "has_content": message.content is not None,
    }
    logger.info("Validation passed.")
    return summary


# --- Task 2: slow subprocess processing ---


@subprocess_task(
    retries=1,
    retry_delay_seconds=2.0,
    timeout_seconds=30.0,
)
def process_content(message: TransportMessage) -> list[str]:
    """External script that processes the ingested content."""
    return ["python", str(_SCRIPTS_DIR / "process.py")]


# --- Task 3: fast finalisation (runs after task 2) ---


@task(name="finalize")
def finalize(
    message: TransportMessage,
    proc_result: SubprocessResult,
) -> None:
    """Log the subprocess result and finalise the flow.

    Runs after the subprocess task completes to report
    on the processing outcome.
    """
    logger.info("Finalising flow run...")
    logger.info(
        "  Subprocess exit code: %d",
        proc_result.returncode,
    )
    if proc_result.success:
        logger.info("  Processing succeeded.")
        if proc_result.stdout:
            logger.info(
                "  Subprocess output: %s",
                proc_result.stdout.strip(),
            )
    else:
        logger.error(
            "  Processing failed (exit code %d).",
            proc_result.returncode,
        )
        if proc_result.stderr:
            logger.error(
                "  Subprocess stderr: %s",
                proc_result.stderr.strip(),
            )

    logger.info(
        "Flow completed for %s/%s.",
        message.who,
        message.what,
    )


# --- Flow definition ---


@flow(name="ingest-flow", log_prints=True)
def ingest_flow(message: TransportMessage) -> None:
    """Process an ingested message through a three-task pipeline.

    1. Validate the message metadata (fast, inline).
    2. Submit an external processing script to the task worker
       (slow subprocess) and wait for its result.
    3. Finalise and log the result (fast, inline, after step 2).

    Args:
        message: TransportMessage from the ingest app.
            The ``where`` field contains the storage URL.
    """
    # Task 1 — fast validation (runs inline)
    validate_message(message)

    # Task 2 — slow subprocess submitted to the task server.
    # .submit() is non-blocking: returns a PrefectFuture.
    # .result() blocks the flow until the task server completes it.
    proc_future = process_content.submit(message)
    proc_result = proc_future.result()

    # Task 3 — fast finalisation (runs inline, after task 2)
    finalize(message, proc_result)


def serve() -> None:
    """Entry point for the ``sample-flow`` command.

    Serves the ingest flow as a Prefect deployment named
    ``ingest-flow/ingest-deployment``.
    """
    logger.info("Serving ingest-flow/ingest-deployment...")
    serve_flows(ingest_flow.to_deployment("ingest-deployment"))


def serve_task() -> None:
    """Entry point for the ``sample-task`` command.

    Starts a Prefect task server that executes ``process-content``
    tasks submitted by flow runs. Run this in a separate process
    (optionally on dedicated infrastructure sized for the task's
    compute requirements).
    """
    logger.info("Starting task server for process-content...")
    serve_tasks(process_content)


if __name__ == "__main__":
    serve()
