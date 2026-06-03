# rpsd-flow

Prefect Flow and Task utilities for the Rapsodia project: settings-driven
decorators and serving helpers, a programmatic Flow-trigger API, and a
canonical, transport-aligned response model.

## Overview

`rpsd-flow` helps developers build Prefect-based pipelines that work with
`TransportMessage` from `rpsd-transport` and `StorageProvider` from
`rpsd-storage`. It provides:

- **`flow` / `task`** — decorator factories wrapping Prefect's `@flow` /
  `@task` with defaults loaded from pydantic-settings (env vars with the
  `FLOW__` / `TASK__` prefix). Explicit arguments always win.
- **`serve_flows` / `serve_tasks`** — run one or more flow deployments, or
  serve tasks as background workers, in the current process.
- **`run_flow` / `run_flow_async`** — trigger a named deployment with a
  `TransportMessage` and get back a homogeneous **`FlowResponse`**.
- **`FlowResponse` / `TaskResult`** — the output-side primitive, parallel to
  `TransportMessage` on the input side.
- **`subprocess_task` / `SubprocessResult`** — build a `@task` that runs a CLI
  command, feeding message data through env vars, stdin, args, or file I/O.

> Terminology: Prefect docs sometimes say "worker" for Tasks. This project
> keeps the parallel words **flow** and **task** everywhere, since Flows may
> also run in workers.

## Defining flows and tasks

```python
from rpsd_flow import flow, task
from rpsd_transport import TransportMessage

@flow(name="ingest-flow", retries=2, timeout_seconds=120.0)
def ingest_flow(message: TransportMessage) -> None:
    process.submit(message).result()

@task(name="process-doc", retries=3)
def process(message: TransportMessage) -> None:
    ...

if __name__ == "__main__":
    ingest_flow.serve(name="ingest-deployment")
```

Defaults come from `FlowSettings` / `TaskSettings` (e.g. `FLOW__RETRIES=2`);
explicit decorator arguments override them. Extra kwargs pass through to
Prefect.

## Flow execution and responses

`run_flow` / `run_flow_async` serialise the message (`.model_dump()`) and pass
it as `parameters={"message": <dict>}` to a named deployment. They mirror the
dual-API convention used across the project: plain = sync, `_async` = async.

```python
from rpsd_flow import run_flow, run_flow_async, FlowResponse

# Fire-and-forget (default timeout=0): returns immediately, before the run
# starts. response.success is None; response.status is e.g. "SCHEDULED".
response: FlowResponse = run_flow("netex-validate/prod", message)

# Block until the run reaches a terminal state:
response = run_flow("netex-validate/prod", message, timeout=None)
if response.success:
    ...
else:
    for tr in response.task_results:
        if not tr.success:
            print(tr.task_name, tr.error)

# Async equivalent:
response = await run_flow_async("netex-validate/prod", message, timeout=None)
```

### The `timeout` argument

| `timeout`        | Behaviour |
|------------------|-----------|
| `0` *(default)*  | Fire-and-forget: submits the run and returns immediately, before it executes. |
| `None`           | Waits indefinitely until the run reaches a terminal state. |
| positive `float` | Waits up to that many seconds, then returns regardless of state. |

### Retrieving a fire-and-forget result later

Fire-and-forget (`timeout=0`) returns before the flow runs, so the response is
"pending" (`success=None`, empty `task_results`) — only `flow_run_id` is
meaningful. To get the outcome later, store that id and look the run up with
`get_flow_response` / `get_flow_response_async`, the symmetric counterpart to
`run_flow`:

```python
from rpsd_flow import run_flow, get_flow_response

pending = run_flow("netex-validate/prod", message)  # timeout=0
run_id = pending.flow_run_id
# ... later ...
response = get_flow_response(run_id)
if response.success is None:
    ...  # still scheduled / running
else:
    ...  # terminal: response.success + response.task_results
```

It returns the same homogeneous `FlowResponse` (verbatim flow response when
completed and persisted, synthesised with a task-run query otherwise, pending
while not terminal). The original `incoming` message is reconstructed from the
run's stored parameters, so no caller-side state is needed; pass
`incoming=...` to override.

### `FlowResponse`

A single, homogeneous type is **always** returned, parallel to
`TransportMessage` on the input side:

| Field          | Type                      | Notes |
|----------------|---------------------------|-------|
| `incoming`     | `TransportMessage`        | The message passed to `run_flow`. Always present. |
| `outgoing`     | `TransportMessage \| None`| Set by transformation Flows that produce a new message; `None` for validation Flows. |
| `flow_name`    | `str`                     | The flow name (first segment of the deployment name, or authored by the Flow). |
| `flow_run_id`  | `UUID \| None`            | The Prefect flow-run id. |
| `status`       | `str`                     | Stringified Prefect state type: `"SCHEDULED"`, `"RUNNING"`, `"COMPLETED"`, `"FAILED"`, … (or `"UNKNOWN"`). |
| `success`      | `bool \| None`            | `True`/`False` for terminal runs; **`None` when not yet known** (fire-and-forget / still running). |
| `started_at`   | `datetime \| None`        | `None` until the run starts. |
| `finished_at`  | `datetime \| None`        | `None` until the run is terminal. |
| `task_results` | `list[TaskResult]`        | Per-Task detail (see below). |

`TaskResult` records one Task's outcome, Flow-agnostically:

| Field       | Type           | Notes |
|-------------|----------------|-------|
| `task_name` | `str`          | The Prefect task name — no enum, so adding a Task needs no model change. |
| `success`   | `bool`         | Did the Task succeed? |
| `error`     | `str \| None`  | Failure detail when `success` is `False`. |
| `duration`  | `float \| None`| Wall-clock seconds the Task took. |

### Where the response comes from

`run_flow` returns one of three shapes, in priority order:

1. **The Flow's own response (verbatim).** If the run completed and the Flow
   returned a `FlowResponse`, that rich object is returned as-is — with the
   curated per-Task `error` messages and `outgoing` the Flow set. *Requires
   the deployment to enable Prefect result persistence.*
2. **A synthesised response with recovered task detail.** If the run finished
   (or failed) but no `FlowResponse` was available, `run_flow` queries the
   run's Prefect task runs and builds one `TaskResult` per Task that ran
   (`success`/`duration` from each task's state, `error` from its state
   message). This is how a **partial failure still reports the Tasks that ran
   before it**.
3. **A "pending" response.** For fire-and-forget or a still-running run,
   `success`/`started_at`/`finished_at` are `None`, `status` reflects the
   current Prefect state, and `task_results` is empty.

`run_flow` never raises on a result-fetch problem — it always returns a
`FlowResponse`.

### Authoring a Flow that returns a `FlowResponse`

A Flow gets the richest result (shape 1) by building and returning a
`FlowResponse` itself. To make a *failure* surface its per-Task detail through
`run_flow`, return a `FlowResponse(success=False, …)` rather than a Prefect
`Failed` state:

```python
from datetime import UTC, datetime
from rpsd_flow import flow, FlowResponse, TaskResult
from rpsd_transport.models import TransportMessage

@flow(name="netex-validate")
def netex_validate(message: TransportMessage) -> FlowResponse:
    started = datetime.now(UTC)
    results: list[TaskResult] = []
    # ... run tasks, appending TaskResult(...) for each ...
    return FlowResponse(
        incoming=message,
        flow_name="netex-validate",
        status="COMPLETED",
        success=all(r.success for r in results),
        started_at=started,
        finished_at=datetime.now(UTC),
        task_results=results,
    )
```

## Subprocess tasks

`subprocess_task` builds a `@task` that runs an arbitrary CLI command via an
async subprocess, feeding message data through four configurable channels
(environment variables, stdin, extra CLI args, file I/O redirection). It
returns a `SubprocessResult` (`returncode`, `stdout`, `stderr`, `success`, and
optional target paths). See the docstrings in
`rpsd_flow/subprocess_task.py` for the full option set.

## Configuration

Settings classes (pydantic-settings, `__` delimiter):

```bash
# Flow / Task decorator defaults
FLOW__NAME=ingest-flow
FLOW__RETRIES=2
FLOW__TIMEOUT_SECONDS=120
TASK__RETRIES=3

# Serving
FLOW_SERVE__LIMIT=10
TASK_SERVE__STATUS_SERVER_PORT=4200
```

## Design decisions

### Why `run_flow` returns a single `FlowResponse` type

`run_flow` only *triggers* a deployment; the rich, per-Task `FlowResponse` is
built *inside* the Flow and is retrievable only after the run completes. The
default mode, though, is fire-and-forget (`timeout=0`), which returns before
the Flow runs. Rather than return different types per mode (a raw `FlowRun`,
`None`, or a response), we always return **one homogeneous `FlowResponse`** and
let its optional fields express the lifecycle. Callers branch on `success`
(`None` = not yet known) and `status`, never on the return type.

### Why `success`, not `ok`

`SubprocessResult` already uses `success: bool` for "it worked". Reusing the
same word across the package keeps one vocabulary for the same concept.

### Why `status` is a plain `str`

The state vocabulary lives in Prefect (`StateType`). Re-declaring it as an enum
here would duplicate it and drift as Prefect adds states; importing Prefect's
enum into the model would couple `responses.py` to Prefect. A `str` (the
stringified state type, e.g. `"COMPLETED"`) keeps the model Prefect-free and
forward-compatible.

### Why the outcome fields are optional

`success` / `started_at` / `finished_at` are `… | None` so a single type
covers a run's whole lifecycle (submitted → running → terminal). A
fire-and-forget invocation returns a meaningful "submitted / not-yet-known"
response instead of forcing fabricated values.

### Failure detail: Flow first, query fallback

The Flow is the authoritative source of curated per-Task errors, so its own
`FlowResponse` is preferred. When only a Prefect `Failed` state is available,
`run_flow` falls back to a task-run query so the Tasks that ran before the
failure are still listed — at the cost of one extra Prefect API call and
Prefect's generic state messages instead of curated ones.

### Result-persistence caveat

The "verbatim Flow response" path requires the deployment to persist results
(`persist_result=True`); without it, `run_flow` degrades to the synthesised
task-run-query response.

## Known warnings

When a worker reports run state to the Prefect server you may see a Pydantic
serializer warning like:

```
UserWarning: Pydantic serializer warnings:
  PydanticSerializationUnexpectedValue(Expected `int` - serialized value may
  not be as expected [input_value=0.0, input_type=float])
```

This is **expected and harmless**, and it is **not** produced by rpsd-flow's
models — `FlowResponse`, `TaskResult` and `TransportMessage` all round-trip
cleanly. It originates inside the **Prefect SDK's own client-side models**: a
field annotated `int` ends up holding a `float` (e.g. `0.0`) because Prefect
builds some objects with Pydantic's `model_construct()`, which skips the
validation that would otherwise coerce the value. Pydantic v2 then flags the
type mismatch at serialization time. The value is still serialized correctly —
only the declared type differs — so behaviour is unaffected.

It is a side-effect of Prefect's Pydantic v1→v2 migration (these mismatches
were silent under v1) and is being cleaned up release by release, so it should
disappear with a newer Prefect SDK. Until then you can ignore it, or filter it
where noise matters — see the cosmetic filter in
`examples/fastapi_ingest_app/.../sample_flow.py`.

## Development

```bash
uv sync
uv run pytest packages/rpsd-flow/tests/
uv run ruff format packages/rpsd-flow/
uv run ruff check packages/rpsd-flow/
```

## Related packages

- **rpsd-transport** — `TransportMessage`, the input-side primitive.
- **rpsd-storage** — content/metadata persistence for S3, filesystem, HTTP.
