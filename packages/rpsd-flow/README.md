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
- **`publish_flow_artifact` / `to_terminal_state`** — record a Flow's outcome as
  a Prefect Markdown artifact and end the run green (success) or red (failure);
  the artifact is the durable carrier `run_flow` / `get_flow_response` read back.
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

It returns the same homogeneous `FlowResponse` (verbatim flow response read back
from the run's artifact, synthesised with a task-run query otherwise, pending
while not terminal). The original `incoming` message is reconstructed from the
run's stored parameters, so no caller-side state is needed; pass
`incoming=...` to override.

### `FlowResponse`

A single, homogeneous type is **always** returned, parallel to
`TransportMessage` on the input side:

| Field          | Type                      | Notes |
|----------------|---------------------------|-------|
| `incoming`     | `TransportMessage`        | The message passed to `run_flow`. Always present. |
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

`run_flow` / `get_flow_response` return one of three shapes, in priority order:

1. **The Flow's own response (verbatim).** For any **terminal** run — completed
   *or* failed — that published its `FlowResponse` as a Markdown artifact (see
   [Result artifacts](#result-artifacts)), that rich object is read back and
   returned as-is, with the Flow's curated per-Task `error` messages and any
   folded subflow rows. **No result persistence required.**
2. **A synthesised response with recovered task detail.** If a terminal run
   published no artifact, `run_flow` queries the run's Prefect task runs and
   builds one `TaskResult` per Task that ran (`success`/`duration` from each
   task's state, `error` from its state message). This is how a **partial
   failure still reports the Tasks that ran before it**.
3. **A "pending" response.** For fire-and-forget or a still-running run,
   `success`/`started_at`/`finished_at` are `None`, `status` reflects the
   current Prefect state, and `task_results` is empty.

`run_flow` never raises on a result-fetch problem — it always returns a
`FlowResponse`. Callers never touch artifacts or keys; this all happens
internally.

## Result artifacts

A Flow records its outcome by **publishing a Markdown artifact** carrying a
human ✅/❌ summary *and* a fenced `json` block with the full `FlowResponse`. The
artifact — not result persistence — is the durable, UI-visible, machine-readable
carrier: it is published on success **and** failure, so the outcome survives
regardless of run state, and a failed run still shows **red** in the Prefect UI.

Author a Flow with two helpers:

```python
from datetime import UTC, datetime
from rpsd_flow import (
    flow, FlowResponse, TaskResult, publish_flow_artifact, to_terminal_state,
)
from rpsd_transport.models import TransportMessage

@flow(name="netex-validate")
def netex_validate(message: TransportMessage) -> FlowResponse:
    started = datetime.now(UTC)
    results: list[TaskResult] = []
    # ... run tasks, appending TaskResult(...) for each ...
    response = FlowResponse(
        incoming=message,
        flow_name="netex-validate",
        status="COMPLETED",
        success=all(r.success for r in results),
        started_at=started,
        finished_at=datetime.now(UTC),
        task_results=results,
    )
    publish_flow_artifact(response)          # always, before returning
    return to_terminal_state(response)       # FlowResponse (green) | Failed (red)
```

- `publish_flow_artifact(response)` derives the artifact key from the flow name,
  so `get_flow_response` finds it again with **no caller-side key handling**.
  Call it inside the running Flow, once per run.
- `to_terminal_state(response)` returns the `response` when `success` is truthy
  (run ends *Completed* / green) or a Prefect `Failed` state otherwise (run ends
  *Failed* / red, so the UI is honest and retries can fire). The curated detail
  still reaches consumers through the artifact, so `get_flow_response` returns
  the rich `FlowResponse` even for the failed run.

`render_flow_markdown(response)` and `parse_flow_artifact_json(markdown)` are
low-level helpers for code that deliberately works with the raw artifact (e.g. a
custom UI rendering the markdown); normal flow authors and callers need neither.

## Composing Flows (subflows)

A "higher-level" Flow can invoke a "lower-level" Flow (often defined by another
service) as a **subflow** — wait for it, then branch on the outcome. There is **no
special API**: a subflow is just `run_flow_async(..., timeout=None)` called from
*inside* a running Flow. Prefect's `run_deployment` automatically links the triggered
run as a child of the current run, so the parent→child relationship shows up in the
Prefect UI for free.

### `timeout` is per-call — and the two calls live at different layers

The classic friction is "the outside HTTP POST must be fire-and-forget, but the parent
Flow needs to *wait* for the child". These never conflict, because `timeout` belongs to
each invocation independently:

| Layer | Call | `timeout` |
|-------|------|-----------|
| External entry point (HTTP → ingest) | `run_flow_async(ingest, msg, timeout=0)` | `0` — fire-and-forget; returns a `flow_run_id`, the client polls later via `get_flow_response`. |
| Parent Flow body → child deployment | `await run_flow_async(validate, msg, timeout=None)` | `None` — block *inside the parent worker* until the child is terminal, then branch. |

The "wait" happens inside the parent worker; the external caller already left with its
`flow_run_id`.

### Folding a subflow into a flat response

So the outer caller never has to know a subflow ran, the parent folds the child's
outcome into its own `FlowResponse` with `add_subflow`, keeping `task_results` a single
flat list:

```python
from rpsd_flow import (
    flow, run_flow_async, FlowResponse, publish_flow_artifact, to_terminal_state,
)
from rpsd_transport.models import TransportMessage

@flow(name="ingest-flow", log_prints=True)
async def ingest_flow(message: TransportMessage) -> FlowResponse:
    response = FlowResponse(incoming=message, flow_name="ingest-flow")
    # ... save the file, append your own TaskResult(s) ...

    # Subflow: invoke the validator deployment and WAIT (timeout=None).
    child = await run_flow_async("validate-flow/prod", message, timeout=None)
    response.add_subflow(child)              # one flat summary row
    # response.add_subflow(child, detail=True)  # or: every child row, prefixed

    if child.success:
        dispatch_success.submit(message).result()
    else:
        handle_failure.submit(message).result()

    response.status = "COMPLETED"
    response.success = all(r.success for r in response.task_results)
    publish_flow_artifact(response)
    return to_terminal_state(response)
```

`add_subflow(child)` appends a single summary `TaskResult` (`task_name` = the child's
flow name, `success` = `child.success`, `error` = the first failing child row, etc.).
`detail=True` instead appends every child `TaskResult`, each name prefixed
`"<flow-name>/<task-name>"` so names stay unique. Either way the caller sees one
uniform, flat list and branches on `success` — a prefixed name like
`validate-flow/syntax` just reads as a namespaced task name, not a subflow boundary.

**Child success vs. parent success.** `add_subflow` never touches `response.success` —
the parent owns its own success semantic. The *child's* true success is
`child.success`, carried verbatim in the folded row; computing
`success = all(r.success for r in response.task_results)` then folds the child in
truthfully alongside the parent's own steps (or set `success` from explicit logic if a
subflow is advisory and shouldn't fail the parent).

> If you ever need to deep-link a child run from the response itself (e.g. a pipeline
> UI), the minimal flat extension is an optional `flow_run_id` on `TaskResult` — not
> built today, since the full tree is already navigable in the Prefect UI.

### Serve parent and child on separate work pools

The real cost of a blocking parent is **worker-slot occupancy**: while the parent waits
on `timeout=None`, it holds a concurrency slot in its serve process for the child's
whole duration. If parent and child share one process/work pool with a fixed `limit`,
you can **deadlock** — every slot held by a parent waiting on a child that can never be
scheduled. Serve them on **separate processes / work pools** (and consider a dedicated
pool for single long-running Tasks too) so their concurrency budgets are independent.
Native same-process subflows (a direct function call) avoid this but require importing
the child's code, which is impossible across separate services.

Use `run_flow_async` (not the sync `run_flow`) inside a Flow — calling the sync helper
from within a running event loop is a documented Prefect sharp edge.

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

### Failure detail: artifact first, query fallback

The Flow is the authoritative source of curated per-Task errors, so its own
`FlowResponse` — published as a Markdown artifact — is preferred, for failed runs
too. When a terminal run published no artifact, `run_flow` falls back to a
task-run query so the Tasks that ran before the failure are still listed, at the
cost of one extra Prefect API call and Prefect's generic state messages instead
of curated ones.

### Why the artifact (not result persistence) carries the outcome

The rich `FlowResponse` is published as a Prefect **artifact** rather than
relying on Prefect *result persistence* (`persist_result`). The artifact needs
no result-storage configuration, is visible in the Prefect UI, is published on
**failure** as well as success, and is read back by `run_flow` /
`get_flow_response` with no caller-side key handling. (If you separately want
verbatim *programmatic* results from `state.result()`, Prefect's
`PREFECT_RESULTS_PERSIST_BY_DEFAULT` + a shared result-storage block remain
available, but the package no longer relies on them.)

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
