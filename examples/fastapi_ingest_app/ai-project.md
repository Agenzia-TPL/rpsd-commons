# AI Project analysis — fastapi_ingest_app (integration example)

## Scope

This is the planning/decision log for the **fastapi_ingest_app integration
example**, scoped to this directory. The repo-root `ai-project.md` covers the
core library packages (rpsd-storage, rpsd-transport, rpsd-flow); this file
covers only how the example wires them together. See `README.md` for
operating instructions (commands, endpoints, env vars) — this file captures
*what* the example demonstrates and *why*, not *how* to run it.

## Overview

A runnable, end-to-end FastAPI application that exercises the whole Rapsodia
commons stack as a single pipeline:

- **rpsd-transport** — `HTTPCarrier` to receive messages; `IngestProcessor`
  to resolve/save/forward; optional Kafka or RabbitMQ forward carrier.
- **rpsd-storage** — content + metadata persistence (FS or S3).
- **rpsd-flow** — trigger a Prefect Flow deployment per ingest and surface its
  `FlowResponse`.

Entry points (`pyproject.toml [project.scripts]`): `fastapi-ingest-app` (the
API), `consumer` (broker consumer), `sample-flow` / `sample-task` (Prefect
deployment + task server). Settings are pydantic-settings driven with the
`APP__` prefix (`AppSettings`).

## Ingest pipeline (`POST /ingest`)
__DONE__

The endpoint demonstrates the receive → resolve → save → forward → invoke
chain:

1. **Receive** via `HTTPCarrier.receive()` (supports inline JSON and outline
   headers/query metadata, slim/fast and fat/heavy).
2. **Resolve dedup policy server-side** — `resolve_compare_before_save(what)`
   maps the content category to `compare_before_save`: deduplicate
   (`daily-report`, `config-snapshot`, `test-report`), always-write
   (`audit-log`, `transaction-record`), or defer to the provider default.
   Clients never control this; the mapping lives on the server.
3. **Save** via `IngestProcessor.process_async()`, with metadata enrichment
   (`pre_save_transform` adds timestamp/version/hash/size;
   `pre_forward_transform` marks pre-forward).
4. **Forward** (optional) to the configured carrier; skipped when the save was
   deduplicated.
5. **Invoke a Flow** (optional, see below).

The JSON response reports `deduplicated`, `forwarded`, `flow_invoked`, a
`flow` block, storage metadata, and message metadata.

## Flow invocation + response projection
__DONE__

When `APP__FLOW__DEPLOYMENT` is set (and the save was not deduplicated), the
app calls `run_flow_async(deployment, message, APP__FLOW__TIMEOUT)`. The
message's `where` is set to the storage URL so the Flow knows where the
content landed.

- Default `APP__FLOW__TIMEOUT=0` is **fire-and-forget**: the returned
  `FlowResponse` is "pending" (`success=null`, empty `task_results`,
  `status` reflecting the Prefect state).
- A positive timeout / `null` makes `run_flow_async` wait and return the
  Flow's own rich `FlowResponse`.

`_flow_summary()` projects the `FlowResponse` into the HTTP body (JSON-safe:
UUID→str, datetimes→ISO), shared between `POST /ingest` and the retrieval
endpoint.

## Fire-and-forget result retrieval (`GET /flow/{flow_run_id}`)
__DONE__

**Problem**: with the default fire-and-forget timeout, `POST /ingest` returns
before the Flow runs, so the caller gets only a `flow_run_id` and no outcome.

**Proposed Solution**: a `GET /flow/{flow_run_id}` endpoint backed by
rpsd-flow's `get_flow_response_async`. The client stores the id from the
ingest response and polls this endpoint until the run is terminal. The helper
reconstructs the `incoming` message from the run's stored parameters, so the
app keeps **no per-run state**.

**Expected outcome**: the full fire-and-forget → poll-later loop is
demonstrable end to end without the app tracking runs itself.

## Sample Flow (`sample_flow.py`)
__DONE__

A three-task pipeline served as `ingest-flow/ingest-deployment`:

1. `validate-message` — fast inline task checking metadata.
2. `process-content` — `subprocess_task` running `scripts/process.py` on the
   task server (submitted via `.submit().result()`).
3. `finalize` — fast inline task logging the outcome.

The Flow times each task, records a `TaskResult`, skips downstream tasks once
one fails, and **returns a `FlowResponse`** (it does not raise / return a
Prefect `Failed` state on handled failure — it returns
`FlowResponse(success=False, ...)`), so callers get the rich, per-Task outcome
verbatim through `run_flow` / `get_flow_response`.

## Tunable processing time
__DONE__

`scripts/process.py` simulates heavy work with a sleep configurable via the
`RPSD_PROCESS_SLEEP` env var (seconds, default `3.0`; invalid → default;
`0` = instant). It is read by the subprocess directly (not an `APP__`
setting) and reaches the script because `subprocess_task` inherits the task
server's environment. Raising it makes the fire-and-forget → poll-later
transition easy to observe; lowering it keeps the demo snappy.

## Subflow composition (`subflow_example.py`)

**Problem**: the platform needs Flow *composition* — a "higher-level" Flow
(e.g. ingest) that invokes one or more "lower-level" Flows defined by other
services (e.g. a validator) as Prefect subflows, waits for them, and then
branches on the result. The friction is the `timeout`: the outermost trigger
(HTTP → ingest) must stay fire-and-forget because validation can be slow, yet
the parent Flow genuinely needs to wait for the child before branching. We also
want the outer caller to keep seeing a single, flat `FlowResponse` — it should
not need to know subflows were involved.

**Proposed Solution**: lean on the fact that `timeout` is per-invocation and
the two calls live at different layers — the external trigger uses `timeout=0`,
the parent → child call inside the Flow uses `timeout=None` (block until the
child is terminal). No new execution API: `run_flow_async(..., timeout=None)`
from inside a Flow is already a Prefect subflow (auto-linked parent→child). The
parent folds the child's outcome into its own response with the new
`FlowResponse.add_subflow(child)` helper, which appends a flat summary
`TaskResult` carrying `child.success` (or, with `detail=True`, the child's rows
prefixed by flow name). The parent owns its own `success`; the folded row makes
the child participate in `all(...)` without re-derivation. We'll add
`validate-flow` and `ingest-with-validation-flow`, served by separate
`serve-validate` / `serve-ingest` entry points so the blocking parent and its
child get independent concurrency budgets.

**Expected outcome**: a runnable two-Flow example where the outer caller gets
one flat `FlowResponse` (a `validate-flow` summary row alongside the parent's
own tasks) and never sees the subflow; the parent→child tree remains navigable
in the Prefect UI; and the separate-work-pool topology avoids slot-starvation.

## Consumer (`consumer.py`)
__DONE__

A standalone consumer (separate from the API to show separation of publish vs
consume) that reads forwarded messages from Kafka/RabbitMQ via the carrier
factory and uses `rpsd-storage` to fetch content across `file://`, `http://`,
`https://` (and `s3://`) URL schemes, handling fetch errors gracefully without
crashing.

## End-to-end demo (`demo.sh`)
__DONE__

Orchestrates the whole stack for `kafka` or `rabbitmq`: checks broker +
optional Prefect availability, writes a demo `.env`, starts task server / flow
server / API / consumer, then runs scenario tests — slim/fast, deduplication,
always-write audit log, fat/heavy across URL schemes, error handling, and
**Test 8: fire-and-forget flow retrieval** (capture `flow_run_id`, show the
pending response, then poll `GET /flow/{id}` until terminal). Restores the
original `.env` on exit. Sets `RPSD_PROCESS_SLEEP=5` so the retrieval loop is
observable.

When Prefect is available it also starts the composite-flow servers on
**separate processes / work pools** — `serve-validate`
(`validate-flow/validate-deployment`) and `serve-ingest`
(`ingest-with-validation-flow/ingest-deployment`) — and runs **Test 9: composite
flow with a subflow**: a small `run_flow` / `get_flow_response` snippet triggers
the parent fire-and-forget (`timeout=0`) and polls until terminal, printing the
single flat `FlowResponse` whose `task_results` carry the folded `validate-flow`
summary row — demonstrating that the caller never sees the subflow. Both example
flows set `persist_result=True` so the flow-authored (verbatim) response, with
that folded row, survives retrieval. Composite PIDs are tracked and killed on
cleanup; the test is skipped if the servers fail to start.
