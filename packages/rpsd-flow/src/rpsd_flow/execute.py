# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Flow execution helpers for rpsd-flow.

Provides ``run_flow`` (sync) and ``run_flow_async`` (async) — thin wrappers
around Prefect's ``run_deployment`` that serialise a ``TransportMessage`` as
deployment parameters, trigger a named deployment run programmatically, and
return a homogeneous :class:`FlowResponse` describing the run.

For a terminal run, the rich, flow-authored ``FlowResponse`` is recovered from
the **Markdown artifact** the Flow published (see ``artifacts.py``) — no result
persistence required, and it works for failed runs too. When no artifact is
present, the response is synthesised from a Prefect task-run query.
"""

from typing import Any
from uuid import UUID

from rpsd_flow.artifacts import _read_response_from_artifact_async
from rpsd_flow.responses import UNKNOWN_STATUS, FlowResponse, TaskResult
from rpsd_transport.models import TransportMessage

# Sentinel distinguishing "no flow result was fetched" from a flow that
# legitimately returned ``None``.
_UNSET = object()


async def _verbatim_or_synthesised(
    flow_run: Any,
    flow_name: str,
) -> tuple[Any, list[TaskResult] | None]:
    """Resolve a terminal run's outcome detail.

    Prefers the verbatim ``FlowResponse`` the Flow published as its Markdown
    artifact; falls back to a synthesised task-run query. Returns ``(result,
    task_results)`` for :func:`_to_flow_response`: ``result`` is the verbatim
    response or ``_UNSET``; ``task_results`` is the synthesised list or ``None``.
    """
    run_id = getattr(flow_run, "id", None)
    if run_id is not None:
        verbatim = await _read_response_from_artifact_async(run_id, flow_name)
        if isinstance(verbatim, FlowResponse):
            return verbatim, None
    return _UNSET, await _query_task_results(flow_run)


def _build_task_result(task_run: Any) -> TaskResult:
    """Map a Prefect ``TaskRun`` to a :class:`TaskResult`."""
    state = task_run.state
    success = bool(state is not None and state.is_completed())
    error = None
    if state is not None and not success:
        error = state.message
    duration = None
    if task_run.start_time is not None and task_run.end_time is not None:
        duration = (task_run.end_time - task_run.start_time).total_seconds()
    return TaskResult(
        task_name=task_run.name,
        success=success,
        error=error,
        duration=duration,
    )


async def _query_task_results(flow_run: Any) -> list[TaskResult]:
    """Query Prefect for the task runs of ``flow_run`` and map them.

    Used as the fallback source of per-Task detail when the Flow did not
    return a rich :class:`FlowResponse` (e.g. it left a Prefect ``Failed``
    state). Never raises: a query failure yields an empty list so the
    ``run_flow`` contract (always return a ``FlowResponse``) holds.
    """
    try:
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import (
            FlowRunFilter,
            FlowRunFilterId,
        )

        async with get_client() as client:
            task_runs = await client.read_task_runs(
                flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run.id])),
            )
    except Exception:
        return []

    # Order by start time so tasks that ran before a failure read in order;
    # task runs that never started sort last.
    task_runs.sort(
        key=lambda tr: (tr.start_time is None, tr.start_time),
    )
    return [_build_task_result(tr) for tr in task_runs]


def _to_flow_response(
    flow_run: Any,
    message: TransportMessage,
    flow_name: str,
    *,
    result: Any = _UNSET,
    task_results: list[TaskResult] | None = None,
) -> FlowResponse:
    """Build a :class:`FlowResponse` from a Prefect ``FlowRun``.

    If ``result`` is a :class:`FlowResponse` (the Flow returned its own rich
    response), it is returned verbatim. Otherwise a response is synthesised
    from the ``FlowRun`` metadata, using ``task_results`` if provided.
    """
    if isinstance(result, FlowResponse):
        return result

    if flow_run is None:
        return FlowResponse(
            incoming=message,
            flow_name=flow_name,
            status=UNKNOWN_STATUS,
            success=None,
            task_results=task_results or [],
        )

    state = getattr(flow_run, "state", None)
    if state is None:
        status = UNKNOWN_STATUS
        success: bool | None = None
    else:
        # state.type is a Prefect ``StateType`` enum; its ``.value`` is the
        # bare name ("SCHEDULED"), whereas ``str(state.type)`` would yield
        # "StateType.SCHEDULED".
        status = str(getattr(state.type, "value", state.type))
        if state.is_completed():
            success = True
        elif state.is_final():
            success = False
        else:
            success = None

    return FlowResponse(
        incoming=message,
        flow_name=flow_name,
        flow_run_id=getattr(flow_run, "id", None),
        status=status,
        success=success,
        started_at=getattr(flow_run, "start_time", None),
        finished_at=getattr(flow_run, "end_time", None),
        task_results=task_results or [],
    )


def run_flow(
    deployment_name: str,
    message: TransportMessage,
    timeout: float | None = 0,
) -> FlowResponse:
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
              returns regardless of the run's state.

    Returns:
        A :class:`FlowResponse` describing the run.

        - Fire-and-forget / still-running: ``success`` is ``None``,
          ``status`` reflects the current Prefect state (e.g.
          ``"SCHEDULED"``) and ``task_results`` is empty.
        - Terminal run whose Flow published its :class:`FlowResponse` as a
          Markdown artifact (see ``publish_flow_artifact``): that rich
          response is returned verbatim — for completed *and* failed runs.
        - Terminal run otherwise: a synthesised response with
          ``task_results`` recovered from a Prefect task-run query.

    Raises:
        prefect.exceptions.PrefectHTTPStatusError: If the deployment
            does not exist or the Prefect API is unreachable.

    Note:
        Calling this sync helper from within a running event loop is a
        Prefect sharp edge; prefer ``run_flow_async`` in async contexts.

    Example::

        from rpsd_flow import run_flow
        from rpsd_transport import TransportMessage

        message = TransportMessage(...)

        # Fire-and-forget — returns as soon as Prefect accepts the run:
        response = run_flow("ingest-flow/ingest-deployment", message)

        # Block until the flow finishes (no timeout):
        response = run_flow(
            "ingest-flow/ingest-deployment",
            message,
            timeout=None,
        )
    """
    from prefect.deployments import run_deployment
    from prefect.utilities.asyncutils import run_coro_as_sync

    flow_run = run_deployment(
        name=deployment_name,
        parameters={"message": message.model_dump()},
        timeout=timeout,
    )

    flow_name = deployment_name.split("/", 1)[0]
    result: Any = _UNSET
    task_results: list[TaskResult] | None = None
    state = getattr(flow_run, "state", None)
    if state is not None and state.is_final():
        result, task_results = run_coro_as_sync(
            _verbatim_or_synthesised(flow_run, flow_name)
        )

    return _to_flow_response(
        flow_run,
        message,
        flow_name,
        result=result,
        task_results=task_results,
    )


async def run_flow_async(
    deployment_name: str,
    message: TransportMessage,
    timeout: float | None = 0,
) -> FlowResponse:
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
              returns regardless of the run's state.

    Returns:
        A :class:`FlowResponse` describing the run. See ``run_flow`` for
        the full description of the three return shapes (fire-and-forget,
        verbatim flow response, synthesised response).

    Raises:
        prefect.exceptions.PrefectHTTPStatusError: If the deployment
            does not exist or the Prefect API is unreachable.

    Example::

        from rpsd_flow import run_flow_async
        from rpsd_transport import TransportMessage

        message = TransportMessage(...)

        # Fire-and-forget — returns as soon as Prefect accepts the run:
        response = await run_flow_async(
            "ingest-flow/ingest-deployment", message
        )

        # Block until the flow finishes (no timeout):
        response = await run_flow_async(
            "ingest-flow/ingest-deployment",
            message,
            timeout=None,
        )
    """
    from prefect.deployments import run_deployment

    flow_run = await run_deployment.aio(
        name=deployment_name,
        parameters={"message": message.model_dump()},
        timeout=timeout,
    )

    flow_name = deployment_name.split("/", 1)[0]
    result: Any = _UNSET
    task_results: list[TaskResult] | None = None
    state = getattr(flow_run, "state", None)
    if state is not None and state.is_final():
        result, task_results = await _verbatim_or_synthesised(flow_run, flow_name)

    return _to_flow_response(
        flow_run,
        message,
        flow_name,
        result=result,
        task_results=task_results,
    )


def _incoming_from_flow_run(flow_run: Any) -> TransportMessage | None:
    """Reconstruct the input ``TransportMessage`` from a run's parameters.

    Flows triggered via ``run_flow`` / ``run_flow_async`` are called with
    ``parameters={"message": <serialised TransportMessage>}``; Prefect
    retains those parameters on the ``FlowRun``. Returns ``None`` if no usable
    ``message`` parameter is present.
    """
    params = getattr(flow_run, "parameters", None) or {}
    raw = params.get("message")
    if not isinstance(raw, dict):
        return None
    try:
        return TransportMessage.model_validate(raw)
    except Exception:
        return None


async def _resolve_flow_name(client: Any, flow_run: Any) -> str:
    """Best-effort lookup of the Flow's name for a retrieved ``FlowRun``."""
    flow_id = getattr(flow_run, "flow_id", None)
    if flow_id is not None:
        try:
            flow = await client.read_flow(flow_id)
            return flow.name
        except Exception:
            pass
    return getattr(flow_run, "name", None) or ""


async def get_flow_response_async(
    flow_run_id: UUID | str,
    incoming: TransportMessage | None = None,
) -> FlowResponse:
    """
    Build a :class:`FlowResponse` for an already-triggered Flow run.

    The symmetric, "retrieve later" counterpart to ``run_flow_async``: given
    the ``flow_run_id`` returned by a fire-and-forget invocation
    (``timeout=0``), look the run up and produce the same homogeneous
    ``FlowResponse``.

    Args:
        flow_run_id: The Prefect flow-run id (as returned in
            ``FlowResponse.flow_run_id``).
        incoming: Optional original ``TransportMessage``. If omitted, it is
            reconstructed from the run's stored ``message`` parameter.

    Returns:
        A :class:`FlowResponse` describing the run, with the same three shapes
        as ``run_flow`` (verbatim flow response recovered from the published
        artifact — for completed *and* failed runs, synthesised with a task-run
        query otherwise, or "pending" while the run is not yet terminal).

    Raises:
        ValueError: If the run has no usable ``message`` parameter and no
            ``incoming`` message was provided (so ``incoming`` cannot be set).
    """
    from prefect.client.orchestration import get_client

    run_id = flow_run_id if isinstance(flow_run_id, UUID) else UUID(str(flow_run_id))

    async with get_client() as client:
        flow_run = await client.read_flow_run(run_id)
        flow_name = await _resolve_flow_name(client, flow_run)

    result: Any = _UNSET
    task_results: list[TaskResult] | None = None
    state = getattr(flow_run, "state", None)
    if state is not None and state.is_final():
        result, task_results = await _verbatim_or_synthesised(flow_run, flow_name)

    # A verbatim artifact response already carries its own ``incoming``, so
    # return it without requiring the run's stored ``message`` parameter.
    if isinstance(result, FlowResponse):
        return result

    resolved_incoming = incoming or _incoming_from_flow_run(flow_run)
    if resolved_incoming is None:
        raise ValueError(
            f"Cannot build a FlowResponse for flow run {run_id}: no 'message' "
            "parameter found on the run and no incoming message provided."
        )

    return _to_flow_response(
        flow_run,
        resolved_incoming,
        flow_name,
        result=result,
        task_results=task_results,
    )


def get_flow_response(
    flow_run_id: UUID | str,
    incoming: TransportMessage | None = None,
) -> FlowResponse:
    """
    Sync version of ``get_flow_response_async``.

    Build a :class:`FlowResponse` for an already-triggered Flow run, given the
    ``flow_run_id`` from a fire-and-forget invocation. See
    ``get_flow_response_async`` for details.

    Note:
        Calling this sync helper from within a running event loop is a Prefect
        sharp edge; prefer ``get_flow_response_async`` in async contexts.
    """
    from prefect.utilities.asyncutils import run_coro_as_sync

    return run_coro_as_sync(get_flow_response_async(flow_run_id, incoming))
