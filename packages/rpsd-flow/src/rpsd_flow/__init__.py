"""
rpsd-flow: Prefect Flow and Task utilities for the Rapsodia project.

Provides helper decorators, settings classes, and utility functions for
building Prefect-based data pipelines that work with ``TransportMessage``
from ``rpsd-transport`` and ``StorageProvider`` from ``rpsd-storage``.

Quick start::

    from rpsd_flow import flow, task
    from rpsd_transport import TransportMessage

    @flow(name="ingest-flow", retries=2, timeout_seconds=120.0)
    def ingest_flow(message: TransportMessage) -> None:
        result = process.submit(message)
        result.wait()

    @task(name="process-doc", retries=3)
    def process(message: TransportMessage) -> None:
        ...

    if __name__ == "__main__":
        ingest_flow.serve(name="ingest-deployment")

Public API
----------
Decorators:
  flow                   Drop-in-like @flow with env-var defaults (FlowSettings)
  task                   Drop-in-like @task with env-var defaults (TaskSettings)

Settings:
  FlowSettings           Pydantic-settings class (FLOW__ prefix)
  TaskSettings           Pydantic-settings class (TASK__ prefix)

Serving:
  serve_flows            Serve one or more flow deployments in this process
  serve_tasks            Serve one or more tasks as background workers

Execution:
  run_flow               Trigger a named deployment run with a TransportMessage

Subprocess tasks:
  create_subprocess_task  Build a @task that runs a CLI script
  SubprocessResult        Result model returned by subprocess tasks
"""

from rpsd_flow.execute import run_flow
from rpsd_flow.flows import flow
from rpsd_flow.serve import serve_flows, serve_tasks
from rpsd_flow.settings import FlowSettings, TaskSettings
from rpsd_flow.subprocess_task import SubprocessResult, create_subprocess_task
from rpsd_flow.tasks import task

__all__ = [
    # Decorators
    "flow",
    "task",
    # Settings
    "FlowSettings",
    "TaskSettings",
    # Serving
    "serve_flows",
    "serve_tasks",
    # Execution
    "run_flow",
    # Subprocess tasks
    "create_subprocess_task",
    "SubprocessResult",
]
