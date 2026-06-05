# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
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
  FlowServeSettings      Pydantic-settings class (FLOW_SERVE__ prefix)
  TaskServeSettings     Pydantic-settings class (TASK_SERVE__ prefix)

Serving:
  serve_flows            Serve one or more flow deployments in this process
  serve_tasks            Serve one or more tasks as a background task server

Execution:
  run_flow               Trigger a named deployment run with a TransportMessage (sync)
  run_flow_async         Async version of run_flow
  get_flow_response      Build a FlowResponse for an already-triggered run (sync)
  get_flow_response_async  Async version of get_flow_response

Responses:
  FlowResponse           Homogeneous response model returned by run_flow(_async)
  TaskResult             Per-Task result carried by a FlowResponse

Subprocess tasks:
  subprocess_task         Decorator factory that builds a @task running a CLI script
  SubprocessResult        Result model returned by subprocess tasks
"""

from rpsd_flow.execute import (
    get_flow_response,
    get_flow_response_async,
    run_flow,
    run_flow_async,
)
from rpsd_flow.flows import flow
from rpsd_flow.responses import FlowResponse, TaskResult
from rpsd_flow.serve import serve_flows, serve_tasks
from rpsd_flow.settings import (
    FlowServeSettings,
    FlowSettings,
    TaskServeSettings,
    TaskSettings,
)
from rpsd_flow.subprocess_task import SubprocessResult, subprocess_task
from rpsd_flow.tasks import task

__all__ = [
    # Decorators
    "flow",
    "task",
    # Settings
    "FlowSettings",
    "TaskSettings",
    "FlowServeSettings",
    "TaskServeSettings",
    # Serving
    "serve_flows",
    "serve_tasks",
    # Execution
    "run_flow",
    "run_flow_async",
    "get_flow_response",
    "get_flow_response_async",
    # Responses
    "FlowResponse",
    "TaskResult",
    # Subprocess tasks
    "subprocess_task",
    "SubprocessResult",
]
