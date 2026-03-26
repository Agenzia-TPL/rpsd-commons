# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Flow execution helpers for rpsd-flow.

Provides ``run_flow`` (sync) and ``run_flow_async`` (async) — thin wrappers
around Prefect's ``run_deployment`` that serialise a ``TransportMessage`` as
deployment parameters and trigger a named deployment run programmatically.
"""

from typing import Any

from rpsd_transport.models import TransportMessage


def run_flow(
    deployment_name: str,
    message: TransportMessage,
    timeout: float | None = 0,
) -> Any:
    """
    Trigger a named Prefect flow deployment with a ``TransportMessage``.

    Serialises the message to a plain dict and passes it as the
    ``message`` parameter to the deployment. The receiving flow must
    accept a ``message`` parameter compatible with the serialised form
    (a Pydantic ``TransportMessage`` will deserialise it automatically
    when the deployment is started).

    Prefect's ``run_deployment`` uses ``@async_dispatch``, so calling
    it from a sync context (without ``await``) works correctly.

    Args:
        deployment_name: Deployment identifier in the form
            ``"flow-name/deployment-name"`` as shown in the Prefect UI.
        message: The ``TransportMessage`` to pass to the flow run.
        timeout: Controls how long to wait for the flow run to finish.

            - ``0`` *(default)* — fire-and-forget: submits the run via
              a single HTTP POST to the Prefect API and returns
              immediately, before the flow even starts executing.
            - ``None`` — waits indefinitely until the flow run reaches
              a terminal state (blocks the caller for the full flow
              duration).
            - Positive ``float`` — waits up to that many seconds, then
              returns the ``FlowRun`` regardless of its state.

    Returns:
        A Prefect ``FlowRun`` object representing the triggered run.

    Raises:
        prefect.exceptions.PrefectHTTPStatusError: If the deployment
            does not exist or the Prefect API is unreachable.

    Example::

        from rpsd_flow import run_flow
        from rpsd_transport import TransportMessage

        message = TransportMessage(who="sender", what="document", ...)

        # Fire-and-forget — returns as soon as Prefect accepts the run:
        run_flow("ingest-flow/ingest-deployment", message)

        # Wait up to 60 seconds for the flow to complete:
        flow_run = run_flow(
            "ingest-flow/ingest-deployment",
            message,
            timeout=60.0,
        )

        # Block until the flow finishes (no timeout):
        flow_run = run_flow(
            "ingest-flow/ingest-deployment",
            message,
            timeout=None,
        )
    """
    from prefect.deployments import run_deployment

    return run_deployment(
        name=deployment_name,
        parameters={"message": message.model_dump()},
        timeout=timeout,
    )


async def run_flow_async(
    deployment_name: str,
    message: TransportMessage,
    timeout: float | None = 0,
) -> Any:
    """
    Async version of ``run_flow``.

    Trigger a named Prefect flow deployment with a ``TransportMessage``.

    Serialises the message to a plain dict and passes it as the
    ``message`` parameter to the deployment. The receiving flow must
    accept a ``message`` parameter compatible with the serialised form
    (a Pydantic ``TransportMessage`` will deserialise it automatically
    when the deployment is started).

    Args:
        deployment_name: Deployment identifier in the form
            ``"flow-name/deployment-name"`` as shown in the Prefect UI.
        message: The ``TransportMessage`` to pass to the flow run.
        timeout: Controls how long to wait for the flow run to finish.

            - ``0`` *(default)* — fire-and-forget: submits the run via
              a single HTTP POST to the Prefect API and returns
              immediately, before the flow even starts executing.
            - ``None`` — waits indefinitely until the flow run reaches
              a terminal state (blocks the caller for the full flow
              duration).
            - Positive ``float`` — waits up to that many seconds, then
              returns the ``FlowRun`` regardless of its state.

    Returns:
        A Prefect ``FlowRun`` object representing the triggered run.

    Raises:
        prefect.exceptions.PrefectHTTPStatusError: If the deployment
            does not exist or the Prefect API is unreachable.

    Example::

        from rpsd_flow import run_flow_async
        from rpsd_transport import TransportMessage

        message = TransportMessage(who="sender", what="document", ...)

        # Fire-and-forget — returns as soon as Prefect accepts the run:
        await run_flow_async("ingest-flow/ingest-deployment", message)

        # Wait up to 60 seconds for the flow to complete:
        flow_run = await run_flow_async(
            "ingest-flow/ingest-deployment",
            message,
            timeout=60.0,
        )

        # Block until the flow finishes (no timeout):
        flow_run = await run_flow_async(
            "ingest-flow/ingest-deployment",
            message,
            timeout=None,
        )
    """
    from prefect.deployments import run_deployment

    return await run_deployment.aio(
        name=deployment_name,
        parameters={"message": message.model_dump()},
        timeout=timeout,
    )
