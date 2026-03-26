# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Serving helpers for rpsd-flow.

Provides ``serve_flows`` for running one or more flow deployments in
the current process, and ``serve_tasks`` for running one or more tasks
as background workers (via Prefect's task worker).

Both functions:
- Expose all parameters of the underlying Prefect calls
- Load defaults from settings classes (env vars)
- Log startup and shutdown messages
- Handle errors cleanly
"""

import logging

from prefect.deployments.runner import RunnerDeployment
from prefect.tasks import Task

from rpsd_flow.settings import FlowServeSettings, TaskServeSettings

logger = logging.getLogger(__name__)


def serve_flows(
    *deployments: RunnerDeployment,
    limit: int | None = None,
    pause_on_shutdown: bool | None = None,
    print_starting_message: bool | None = None,
    settings: FlowServeSettings | None = None,
) -> None:
    """
    Serve one or more Prefect flow deployments in the current process.

    Creates deployments and starts listening for scheduled or triggered
    flow runs. Blocks until the process is stopped.

    .. note::
        For a **single flow**, prefer ``flow.serve(name="...")`` directly —
        it is simpler and equivalent. ``serve_flows`` exists for the case
        where you want to host **multiple flows in one process** (shared
        runner), which ``flow.serve()`` cannot do.

    Defaults for all keyword arguments are loaded from ``FlowServeSettings``
    (env vars with ``FLOW_SERVE__`` prefix). Explicit arguments always
    override the settings.

    Args:
        *deployments: One or more ``RunnerDeployment`` objects created
            via ``flow.to_deployment("deployment-name", ...)``.
        limit: Maximum number of concurrent flow runs. ``None`` means no
            limit. Overrides ``FLOW_SERVE__LIMIT``.
        pause_on_shutdown: Whether to pause deployment schedules when the
            process receives a shutdown signal. Overrides
            ``FLOW_SERVE__PAUSE_ON_SHUTDOWN`` (default: ``True``).
        print_starting_message: Whether to print Prefect's startup banner.
            Overrides ``FLOW_SERVE__PRINT_STARTING_MESSAGE`` (default:
            ``True``).
        settings: Optional ``FlowServeSettings`` instance. If ``None``,
            one is created automatically from environment variables.

    Example::

        from rpsd_flow import flow, serve_flows
        from rpsd_transport import TransportMessage

        @flow(name="ingest-flow")
        def ingest_flow(message: TransportMessage) -> None:
            ...

        @flow(name="export-flow")
        def export_flow(message: TransportMessage) -> None:
            ...

        if __name__ == "__main__":
            serve_flows(
                ingest_flow.to_deployment("ingest-deployment"),
                export_flow.to_deployment("export-deployment"),
                limit=4,
            )
    """
    resolved = settings or FlowServeSettings()

    resolved_limit = limit if limit is not None else resolved.limit
    resolved_pause = (
        pause_on_shutdown
        if pause_on_shutdown is not None
        else resolved.pause_on_shutdown
    )
    resolved_print = (
        print_starting_message
        if print_starting_message is not None
        else resolved.print_starting_message
    )

    names = ", ".join(d.name for d in deployments)
    logger.info(
        "Starting flow server for %d deployment(s): %s",
        len(deployments),
        names,
    )

    try:
        from prefect import serve as prefect_serve

        prefect_serve(
            *deployments,
            limit=resolved_limit,
            pause_on_shutdown=resolved_pause,
            print_starting_message=resolved_print,
        )
    except KeyboardInterrupt:
        logger.info("Flow server stopped.")
    except Exception:
        logger.exception("Flow server encountered an unexpected error.")
        raise


def serve_tasks[**P, R](
    *tasks: Task[P, R],
    limit: int | None = None,
    timeout: float | None = None,
    status_server_port: int | None = None,
    settings: TaskServeSettings | None = None,
) -> None:
    """
    Serve one or more Prefect tasks as a background task server.

    Starts a task server that listens for task runs submitted outside of
    a flow context (e.g. from application code). Blocks until the
    process is stopped.

    Defaults for all keyword arguments are loaded from
    ``TaskServeSettings`` (env vars with ``TASK_SERVE__`` prefix).
    Explicit arguments always override the settings.

    Args:
        *tasks: One or more Prefect task objects to serve.
        limit: Maximum number of concurrent task runs. If ``None``
            (the default), Prefect's own default (10) is used. Pass an
            explicit integer to override it. Overrides
            ``TASK_SERVE__LIMIT``.
        timeout: Seconds after which the task server shuts down. ``None``
            means run indefinitely. Overrides ``TASK_SERVE__TIMEOUT``.
        status_server_port: Port on which to start an HTTP server
            exposing task server status. ``None`` disables it. Overrides
            ``TASK_SERVE__STATUS_SERVER_PORT``.
        settings: Optional ``TaskServeSettings`` instance. If ``None``,
            one is created automatically from environment variables.

    Example::

        from rpsd_flow import task, serve_tasks
        from rpsd_transport import TransportMessage

        @task(name="process-doc", retries=2)
        def process_doc(message: TransportMessage) -> None:
            ...

        if __name__ == "__main__":
            serve_tasks(process_doc, limit=4)
    """
    resolved = settings or TaskServeSettings()

    resolved_limit = limit if limit is not None else resolved.limit
    resolved_timeout = timeout if timeout is not None else resolved.timeout
    resolved_port = (
        status_server_port
        if status_server_port is not None
        else resolved.status_server_port
    )

    names = ", ".join(t.name for t in tasks)
    logger.info(
        "Starting task server for %d task(s): %s",
        len(tasks),
        names,
    )

    try:
        from prefect.task_worker import serve

        # When resolved_limit is None we omit the kwarg entirely so that
        # Prefect applies its own default (10). Passing limit=None would
        # instead remove the limit, which is a different behaviour.
        if resolved_limit is not None:
            serve(
                *tasks,
                limit=resolved_limit,
                timeout=resolved_timeout,
                status_server_port=resolved_port,
            )
        else:
            serve(
                *tasks,
                timeout=resolved_timeout,
                status_server_port=resolved_port,
            )
    except KeyboardInterrupt:
        logger.info("Task server stopped.")
    except Exception:
        logger.exception("Task worker encountered an unexpected error.")
        raise
