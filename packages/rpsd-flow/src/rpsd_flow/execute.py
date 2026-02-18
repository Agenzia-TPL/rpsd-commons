"""
Flow execution helper for rpsd-flow.

Provides ``run_flow`` — a thin wrapper around Prefect's
``run_deployment`` that serialises a ``TransportMessage`` as deployment
parameters and triggers a named deployment run programmatically.
"""

from typing import Any

from rpsd_transport.models import TransportMessage


def run_flow(
    deployment_name: str,
    message: TransportMessage,
    timeout: float | None = None,
) -> Any:
    """
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
        timeout: Seconds to wait for the flow run to complete. If
            ``None``, the function returns immediately after triggering
            the run (fire-and-forget). If provided, it blocks until
            the run finishes or the timeout is reached.

    Returns:
        A Prefect ``FlowRun`` object representing the triggered run.

    Raises:
        prefect.exceptions.PrefectHTTPStatusError: If the deployment
            does not exist or the Prefect API is unreachable.

    Example::

        from rpsd_flow import run_flow
        from rpsd_transport import TransportMessage

        message = TransportMessage(who="sender", what="document", ...)

        # Fire and forget (non-blocking):
        run_flow("ingest-flow/ingest-deployment", message)

        # Wait up to 60 seconds for completion:
        flow_run = run_flow(
            "ingest-flow/ingest-deployment",
            message,
            timeout=60.0,
        )
    """
    from prefect.deployments import run_deployment

    return run_deployment(
        name=deployment_name,
        parameters={"message": message.model_dump()},
        timeout=timeout,
    )
