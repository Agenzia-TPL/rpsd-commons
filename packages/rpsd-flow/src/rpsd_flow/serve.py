"""
Serving helpers for rpsd-flow.

Provides ``serve_flows`` for running one or more flow deployments in
the current process, and ``serve_tasks`` for running one or more tasks
as background workers (via Prefect's task worker).

Both functions are thin, opinionated wrappers that keep the Prefect
APIs as the source of truth — they handle imports and offer a symmetric,
consistent interface.
"""


def serve_flows(*deployments: object) -> None:
    """
    Serve one or more Prefect flow deployments in the current process.

    Creates deployments and starts listening for scheduled or triggered
    flow runs. Blocks until the process is stopped.

    Pass ``flow.to_deployment(...)`` objects as arguments. All flows
    share a single runner process.

    Args:
        *deployments: One or more ``RunnerDeployment`` objects created
            via ``flow.to_deployment("deployment-name", ...)``.

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
            )
    """
    from prefect.runner import serve as runner_serve

    runner_serve(*deployments)


def serve_tasks(*tasks: object, limit: int | None = None) -> None:
    """
    Serve one or more Prefect tasks as background workers.

    Starts a task worker that listens for task runs submitted outside of
    a flow context (e.g. from application code). Blocks until the
    process is stopped.

    Args:
        *tasks: One or more Prefect task objects to serve.
        limit: Maximum number of concurrent task runs. If None, no limit
            is applied (Prefect default behaviour).

    Example::

        from rpsd_flow import task, serve_tasks
        from rpsd_transport import TransportMessage

        @task(name="process-doc", retries=2)
        def process_doc(message: TransportMessage) -> None:
            ...

        if __name__ == "__main__":
            serve_tasks(process_doc, limit=4)
    """
    from prefect.task_worker import serve

    if limit is not None:
        serve(*tasks, limit=limit)
    else:
        serve(*tasks)
