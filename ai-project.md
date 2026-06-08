# AI Project analysis

## Name

Rapsodia Commons

## Overview

Library of commond code for the Rapsodia project.
Organized into packages (uv workspace project):
- rpsd-storage
- rpsd-transport
- rpsd-flow

This file is the decision log for the **core library packages** above.
Examples and other sub-projects keep their own co-located `ai-project.md`; in
particular the integration example is specified in
`examples/fastapi_ingest_app/ai-project.md`.

# Workspace root

# rpsd-storage

## Refactoring
__DONE__

Refactor the save() method of provider (and derived classes) to return a tuple (url, metadata).
The url must be the complete URL of the saved object/file, constructed like this:
- s3://bucket-name/user123/document/550e8400-e29b-41d4-a716-446655440000.xml
- file:///storage/user123/document/550e8400-e29b-41d4-a716-446655440000.xml
where "user123" must be the "who" value and "document" the "what" value.
The last part is the UUID "object_id", with an (optional) extension.
The metadata dictionary must, among other things, contain the "who", "what" and "object_id" values.
The object_id must be constructed using an inverted UUID v7 value, so that newest object/file will always have the smallest object_id value.
This is very important for S3 retrieval, where only listing object keys in ascending lexicographic order is supported.
The inverted value will have to be formatted with no separating dashes, so as not to resemble a true UUID value.

Refactor the load() method of provider (and derived classes) to accept a "url" parameter, like the one returned by the save() method.
Since it's a complete URL, the S3 or FS provider can retrieve it very fast.
Add to provider (and derived classes) a convenience load_???() method that accept separate "who", "what" and "object_id" values,
and call the load() method, after constructing the complete "url", so that callers do not need to know it.

Add to provider a static load() method that accept a "url" parameter, like the one returned by the save() method,
select the correct provider (S3, FS, others), by looking at the scheme of the provided "url" 
and calls the load() method of the selected provider.
Also add a static load_???() method that accept separate "who", "what" and "object_id" values.

Update all documentation, tests and examples accordingly.

## Implement "http" provider
__DONE__ (only load)

In addition to the existing S3 and FS providers, we must implement an "http" provider.
The load() method must use HTTP GET to retrieve the content from the specified URL.
The save() method will use HTTP POST to save the content to some API, but raise an unimplemented error for now.

## File naming
__DONE__

We must re-think the naming strategy for files in S3 and FS provider, considering the fact that S3 can filter objects having a key with a given prefix.
In the current implementation, since the "Object_id" is at the end of the key, we get a list of ALL the objects and then filter them one by one.
Also S3 object list method accept a parameter that sets the maximum number of keys to return.
Since we're always looking for a single key, we can set that limit to 1, so that:
- if 0 keys are found => it's an error
- if 1 key is found => that's the looked upon object

I don't know for FS, but for S3 this way should be much faster, shouldn't it?
Besides... putting "who" and "what" into the object/file name is only to facilitate manual identification of objects/files, by looking at their names.
From the point of view of the code, using only the "object_id" would be much better...
Should we put "who" and "what" into the path instead (or into "/" separated parts of the key for S3), like: who/what/object_id?
This way object/files would be equally easy to manually locate, but, at the same time, fast to retrieve by code.
What do you think?

## Storage identifier
__DONE__

We need to add to rpsd-storage a concept of "storage identifier", that must be a single value expressing both the type of storage (S3 or FS)
and the address (URL or path) of a specific saved content.
We must add method that, given a "storage indentifier" , will instantiate the correct provider class
and call its load() method, passing to it the content address.
For the S3 provider, both ARNs and presigned URLs must be supported as content address.
For the FS provider, both absolute/relative file path and file URLs must be supported as content address.
We may consider to expand what is currently called "object_id" to also store the provider type part, 
so that an object_id is sufficient to actually retrieve a specific save content.
Or we may leave it as an indentifier valid only for the storage provider that created it and separately manage the provider type.
We use the URL as the definitive absolute identifier, while the combination of who, what and object_id are valid aming a specified provider.

## Metadata compare method
__DONE__

Add to the StorageMetadata model a "compare" staticmethod that takes in input two instances of StorageMetadata and compares them like this:
- If who or what fields are different, it should raise a suitable Exception, because the two instances do not refer to the "same thing"
(use a bultin Exception, if possible, otherwise define a custom one).
- Otherwise, if content_length and hash are equal, return 0.
- Otherwise, if save_stamp of the first instance is after save_stamp of the second instance, return -1.
- Otherwise, return 1.
I'm going to use it to kwnow if a newly saved version of a file is newer than the last saved one.
In this respect I probably simply need a boolean result, but I think that a -1/0/1 may be more generically useful.
In my use case, a result of -1 means: "no, the newly saved file is not actually newer than the previous one".
A result of 1 means: "yes, the newly saved file is actually newer than the previous one".
A result of 0 means: "no, the newly saved file is actually equal to the previous one".
So, I expect only 0 or 1 results, in this use case.
Maybe we should not use "compare" for this method, since it probably is not the "classical" compare method?
Should we better create a boolean returning method, instead?

## Compare before save
__DONE__

Add an opt-in `compare_before_save` flag to `StorageProvider` so that `save()` checks for existing identical content before writing. Each provider's `save()` will build its candidate `StorageMetadata` as usual, then use `StorageMetadata.compare()` against the latest stored metadata for the same `(who, what)` pair. Save only proceeds when the candidate is a genuine update (compare result == 1); identical or older content is skipped, returning the existing metadata with a `deduplicated` flag.

Finding the latest object is cheap thanks to bit-flipped UUID7 object IDs (newest sorts first in ascending order): FS uses sorted `listdir`, S3 uses `list_objects_v2` with `MaxKeys=1`.

The `deduplicated` field on `StorageMetadata` uses `Field(exclude=True)` so it never leaks into `.meta` files or S3 headers. The setting is driven by `STORAGE__COMPARE_BEFORE_SAVE` env var and propagated through `get_storage_provider()`.

## S3 provider configuration
__DONE__

**Problem:** `S3StorageProvider` constructed its boto3 client with no arguments, relying solely on the standard AWS credential chain. This made it impossible to supply credentials or a custom endpoint via `.env` files for testing against real S3 or S3-compatible services (LocalStack, MinIO).

**Proposed solution:** Add five optional fields to `S3Settings`: `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, `region_name`, `endpoint_url`. When any are set, they are forwarded to `boto3.client("s3")`; when all are `None` the behaviour is unchanged. `StorageSettings` is configured with `env_file=".env"` so values in a repo-root `.env` file are picked up automatically.

A `live_s3` pytest marker and session-scoped fixtures (`s3_live_settings`, `s3_live_bucket`, `s3_live_provider`) enable running the compare-before-save suite against a real endpoint. Tests are skipped automatically unless `STORAGE__S3__BUCKET_NAME` is present in the environment or `.env`. The target bucket must already exist; test objects are cleaned up on teardown.

**Expected outcome:** Developers can place S3 credentials in a git-ignored `.env` at the repo root and run `uv run pytest packages/rpsd-storage/ -m live_s3 -v` to verify behaviour on real infrastructure, without affecting normal CI.

# rpsd-transport

## Overview

Library code helping developers to implement receiving and sending content through one of the available trasport carriers, with focus on transporting content.

## Message modes
__DONE__

See also: packages/rpsd-transport/README.md

There are two message modes:
- Slim => content to be sent is small enough to be directly inlined into the message payload
- Fat => content to be sent is too big to go into the message payload and it will be shared by some other method

Since a Slim message will indeed be bigger than a Fat one, for content will be inside the payload, we'll add two new words:
- Fast => content to be sent is small enough to be directly inlined into the message payload
- Heavy => content to be sent is too big to go into the message payload and it will be shared by some other method

that better convoy the meaning of having little content to send, through inlined, hence bigger payload, or more content, through a smaller message.
In the end Slim/Fast and Fat/Heavy will be used interchengeably, with a good initial explanation, such as:
> "Slim messages contain small content directly (fast access, bigger payload), while Fat messages reference large external content (heavy processing, smaller message)."

In both modes, message content can be compressed with zip or gzip.

## Transport scopes
__DONE__

There are two scope for transport:
- external => content is received or sent to an "external system" (a system that can not share storage with the receving or sending system)
- internal => content is received or sent to an "internal system" (a system that can share storage with the receving or sending system)

In case of an external http transport of Fat (aka Heavy) content, the "where" value must be set to the URL that the receiving system must call
(using an HTTP GET method), to retrieve the content itself.
The sending part must make the content available at the URL specified by the "where" value without any authentication mechanism.
The rpsd-transport package must facilitate the implementation of both cases.

In case of an internal transport of Fat (aka Heavy) content, the "where" value must be set to the url where the receiving system can read the content itself,
using the "load_from_url" staticmethod of StorageProvider in rpsd-storage.

## Content and metadata
__DONE__

Messages delivered through rpsd-transport, in addition to content, also contain metadata, that can be organized "inline" or "outline".
Messages with "inline" metadata, have a body containing both content and metadata, while the body of messages with "outline" metadata,
is pure content, with metadata inside headers or other constructs, separated from the body.
In both cases, message content can be compressed with zip or gzip.

Here follows metadata definition:
- who => identifies the sender of the content or the entity to which the containt pertains (i.e. contract ID)
- what => specifies what the content is (i.e. kind of file or dataset)
- where (optional) => if present, specifies content URL in a Fat/Heavy message, if missing, mandates it's a Slim/Fast message

There's no "mode" metadata, if the "where" value is present, the message is Fat/Heavy, otherwise it's Slim/Fast.

For Slim/Fast messages with inline metadata, the body of the message must be in JSON format and the content must be in the "content" field of the body itself.
For Slim/Fast messages with outline metadata, the content can be attached to the body (MIME "multipart/form-data") or it can be the body itself.

For Slim/Fast messages with inline metadata, the body of the message must be in JSON format and metadata values must be in the "metadata" field of the body itself.
For Slim/Fast messages with outline metadata, metadata values are transported by carrier specific methods.

For Fat/Heavy messages with inline metadata, the body of the message must be in JSON format and the content must be available at the URL specified by the "where" field of the metadata.
For Fat/Heavy messages with outline metadata, the content must be available at the URL specified by the "where" field of the metadata.

For Fat/Heavy messages with inline metadata, the body of the message must be in JSON format and metadata values must be in the "metadata" field of the body itself.
For Fat/Heavy messages with outline metadata, metadata values are transported by carrier specific methods.

## Carriers
__DONE__

Initially there'll be two "transport carriers", but more may come in the future:
- HTTP
- PubSub

Each carrier must implement a base interface with methods for sending and receiving messages.

For outline metadata messages, metadata values must NOT be inside the message body itself, but must be transported by carrier specific methods,
as described in carrier specific chapters.

### Sending
__DONE__

Here follows sending methods definitions:
- send_slimfast => send content as a Slim/Fast message (must support both inline and outline metadata)
- send_fatheavy => send content as a Fat/Heavy message (must support both inline and outline metadata)

Both sending methods share these parameters (in order):
- recipient => target identifier (URL for HTTP, topic/channel for PubSub, etc.)
- who => entity identifier
- what => content type/category
- content => data bytes (required for send_slimfast, optional for send_fatheavy)
- content_type => MIME type (default: "application/octet-stream")
- filename => optional original filename
- metadata_use_inline => boolean (default True): True=inline JSON, False=outline headers/query
- metadata_use_headers => boolean (default True): True=headers, False=query params (when metadata_use_inline=False)

Additional send_slimfast parameters:
- content_use_body => boolean (default True): True=raw body, False=multipart attachment (when metadata_use_inline=False)

Additional send_fatheavy parameters:
- where => URL where content is available (required when content is None)
- expose_ttl => time-to-live for exposed URL in seconds (default 3600)

### Receiving
__DONE__

The receive method parses incoming messages and returns a TransportMessage object containing metadata and content (if fast message).
It supports all 4 combinations: (slim/fast vs fat/heavy) × (inline vs outline metadata).

Method signature:
- async receive(request: Request) -> TransportMessage

The receive method:
- Detects metadata organization (inline JSON vs outline headers/query)
- Extracts and validates metadata (who, what, where, etc.)
- Returns content for fast messages, URL reference for heavy messages
- Does NOT fetch heavy content or save to storage
- Calls received() hook for extensibility (metrics, validation, storage integration)

Hook method signature:
- received(message: TransportMessage) -> None

The received hook:
- Called automatically after successful message parsing
- Override in subclasses for custom behavior (storage, metrics, validation, etc.)
- Should have side effects only (no return value)
- Should not modify the message object itself
- CAN and SHOULD raise exceptions to reject messages (validation errors, storage failures, etc.)
- Default implementation: no-op

Storage integration:
- Caller is responsible for fetching heavy content from where URL
- Caller is responsible for saving to storage (if needed)
- Applications can override received() hook for automatic storage integration
- Utilities provided: message_to_json_response(), exception_to_json_response()

### HTTP carrier
__DONE__

This carrier is based on FastAPI and is primarly intended for the external transport scope, but it may nonetheless be used for the internal one, too.
Is intended to implement APIs that an external system may invoke (receive content from external systems)
or to invoke an external system APIs (send content to external systems).

For Fat/Heavy messages:
- When receiving: "where" is an URL that can be used to fetch the content (caller's responsibility to fetch)
- When sending: content must be made available through HTTP (expose API for external system to fetch)

The HTTP carrier does NOT directly integrate with storage - it only handles transport layer concerns.
Applications decide when/where/how to save received content by either:
- Handling storage after receive() returns
- Subclassing HTTPCarrier and overriding received() hook for automatic storage integration

In case of messages with outline metadata, each metadata value can be specified by either one HTTP header or one query parameter, but not both.
If the same metadata value is specified by both an header and a query parameter, it's a caller error.
Here follows the list of metadata value names, same as query parameter names, and their corresponding HTTP hader names:
who => X-RAPS-INGEST_WHO (legacy)
who => X-RPSD-WHO
what => X-RAPS-INGEST_WHAT (legacy)
what => X-RPSD-WHAT
where => X-RAPS-INGEST_WHERE (legacy)
where => X-RPSD-WHERE

Legacy header names are supported, but not incentivated and they may be deprecated at some time in the future.

### PubSub
__DONE__ (Kafka and RabbitMQ carriers)

This carrier is based on the Publish & Subscribe functionality of some Event Broker and is available for the internal transport scope only.

Architecture: Abstract PubSubCarrier base class (sub-ABC of BaseCarrier) + one implementing class per broker.

Key design decisions:
- Two-level hierarchy: BaseCarrier -> PubSubCarrier -> KafkaPubSubCarrier / RabbitMQPubSubCarrier. Justified because PubSub carriers share a distinct receive contract (raw bytes + headers) from HTTP (FastAPI Request).
- CarrierOptions Pydantic model pattern: CarrierOptions -> HTTPCarrierOptions / KafkaCarrierOptions / RabbitMQCarrierOptions. Each carrier specializes options with carrier-specific fields.
- Carrier manages consumer lifecycle via consume() async iterator (unlike HTTP where FastAPI handles the server).
- receive() on PubSubCarrier is sync (just parsing, no I/O). For advanced use when caller manages own consumer.
- get_carrier() factory function mirrors rpsd-storage's get_storage_provider() pattern.
- aiokafka is an optional dependency: uv add rpsd-transport[kafka].
- aio-pika is an optional dependency: uv add rpsd-transport[rabbitmq].
- TransportMessage supports ack/nack via PrivateAttr callables. For Kafka, ack commits the offset (manual commit, auto-commit disabled). For RabbitMQ, ack/nack delegate to the underlying AMQP message. No-op for carriers that don't set them.
- RabbitMQ carrier auto-declares exchanges and queues on startup/consume. Uses aio_pika.connect_robust for auto-reconnect. QoS prefetch_count is configurable via RabbitMQSettings.
- The `topic` parameter in consume() maps to queue name for RabbitMQ, topic name for Kafka. Exchange/routing configuration lives in settings and constructor, not in the consume() signature.

## Processors

### IngestProcessor
__DONE__

**Problem**: The receive → resolve → save → forward pipeline is a common pattern when integrating carriers with storage. Currently, each carrier type requires its own subclass to add storage integration (e.g., StorageHTTPCarrier), duplicating logic across carrier types.

**Proposed Solution**: Create an `IngestProcessor` class in `rpsd_transport.processors.ingest` that handles the pipeline via composition, working with any carrier type. It will:
1. Resolve content (fetch from `where` URL for fat/heavy messages)
2. Optionally save to a `StorageProvider`
3. Optionally forward to a second `BaseCarrier`

Key design decisions:
- Composition over inheritance: IngestProcessor wraps StorageProvider and optional forward BaseCarrier, not extending any carrier.
- Dual sync/async API: `process()` and `process_async()`, mirroring KafkaPubSubCarrier's pattern.
- Configurable forward mode: `"fatheavy"` (sends with where=storage_url) or `"slimfast"` (re-embeds content inline).
- Both storage and forward are optional.
- Settings-driven via `IngestSettings` nested under `TransportSettings`.

**Expected outcome**: Elimination of carrier-specific storage subclasses. Applications use plain carriers + IngestProcessor for the receive-save-forward pattern.

#### Deduplication-aware forwarding

**Problem**: When rpsd-storage's `compare_before_save` is enabled, duplicate content is detected but IngestProcessor still forwards the message unconditionally, causing downstream consumers to re-process unchanged data.

**Proposed Solution**: After saving, check `storage_metadata.deduplicated` and skip forwarding when `True`. Add a `deduplicated: bool` field (excluded from serialization) to `IngestResult` so callers can inspect the outcome without None-guarding `storage_metadata`.

**Expected outcome**: Duplicate messages are silently absorbed at the ingest layer. `IngestResult.deduplicated` and `IngestResult.forwarded` reflect the actual outcome.

# rpsd-flow

## Overview

Library code helping developers to implement Prefect Flows and Tasks, by integrating them into the Rapsodia project.
It will help defining Flows and Tasks capable of receiving and sending messages through rpsd-transport
and able to load and save content and metadata using rpsd-storage.

All decorator factories and serving functions will be settings-driven: defaults come from pydantic-settings
classes (env vars with `__` delimiter), but explicit arguments always take precedence.

Albeit Prefect documentation uses the word "worker" when referring to Tasks, this project does not use it, since Flows may also be executed in workers and always keep the parallel words "flow" and "task" everywhere.

## Flow definition
__DONE__

We'll create a `flow()` decorator factory wrapping Prefect's `@flow`, with defaults loaded from a
`FlowSettings` class (env prefix `FLOW__`). Supported settings: `name`, `description`, `retries`,
`retry_delay_seconds`, `timeout_seconds`, `log_prints`. Extra kwargs pass through to Prefect.

## Task definition
__DONE__

Same pattern as flow definition. A `task()` decorator factory wrapping Prefect's `@task`, with defaults
from `TaskSettings` (env prefix `TASK__`). Same settings as FlowSettings. Extra kwargs (e.g.
`cache_key_fn`, `tags`) pass through to Prefect.

## Flow serving
__DONE__

A `serve_flows()` function that takes one or more `RunnerDeployment` objects and runs them in a shared
Prefect runner. Defaults from `FlowServeSettings` (env prefix `FLOW_SERVE__`): `limit`,
`pause_on_shutdown`, `print_starting_message`. Logs startup/shutdown with deployment names.
For a single flow, callers can just use `flow.serve(name="...")` directly.

## Task serving (Background Tasks)
__DONE__

A `serve_tasks()` function that takes one or more Prefect Task objects and runs them as background workers
via `prefect.task_worker.serve`. Defaults from `TaskServeSettings` (env prefix `TASK_SERVE__`): `limit`,
`timeout`, `status_server_port`. When `limit` is None, we'll omit it entirely so Prefect uses its own
default (10). Logs startup/shutdown with task names.

## Flow execution
__DONE__

A `run_flow()` / `run_flow_async()` pair that triggers a named Prefect deployment with a `TransportMessage`.
Mirrors rpsd-transport's dual API convention: plain method = sync, `_async` suffix = async.
Serializes the message via `.model_dump()` and passes it as `parameters={"message": <dict>}`.
The receiving flow auto-deserializes via Pydantic. Supports optional `timeout` for blocking execution.

Key design decisions:
- Prefect's `run_deployment` uses `@async_dispatch`: calling it without `await` in a sync context works natively.
- `run_flow_async` calls `run_deployment.aio(...)` directly (the attached coroutine function) rather than `await run_deployment(...)` to avoid type-checker errors from the sync return annotation on the dispatch wrapper.

## Flow response
__DONE__

**Problem**: `rpsd-flow` has an input-side primitive (`TransportMessage`, passed to `run_flow`) but no symmetric output-side one. Each component that exposes Flow outcomes invents its own response shape, and `run_flow` / `run_flow_async` return a raw Prefect `FlowRun` typed as `Any` — leaking Prefect internals and offering no per-Task detail.

**Proposed Solution**: Add a canonical `FlowResponse` / `TaskResult` pair (new `responses.py`, re-exported from the package), parallel to `TransportMessage`. `FlowResponse` carries `incoming` (required), `flow_name`, `flow_run_id`, `status`, `success`, `started_at`, `finished_at`, and a list of `TaskResult` (`task_name`, `success`, `error`, `duration`). We'll change `run_flow` / `run_flow_async` to always return a `FlowResponse`. (An `outgoing` field was considered for transformation Flows but **dropped**: unused, and a produced message is a side-effect — a final Task publishes to a broker — or a storage URL, not carried back inline. Re-adding later is additive.)

Key design decisions:
- Homogeneous return: `run_flow` always returns a `FlowResponse`, never a raw `FlowRun`. Callers branch on `success`/`status`, not on the return type.
- The outcome fields (`success`, `started_at`, `finished_at`) are optional so one type covers a run's whole lifecycle. Fire-and-forget (`timeout=0`) yields a "submitted / not-yet-known" response (`success=None`).
- `success` (not `ok`) reuses the word already used by `SubprocessResult.success`.
- `status` is a free-form `str` (the stringified Prefect state type) so the model stays Prefect-free and tolerant of new states; no enum.
- Source of per-Task detail, in priority order: (1) the Flow's own `FlowResponse`, recovered verbatim from the **Markdown artifact** it published (see "Flow artifacts + failure UX") — for completed *and* failed runs, no result persistence; (2) a synthesised response whose `task_results` are recovered by querying the run's Prefect task runs — so a partial failure still lists the Tasks that ran before it; (3) a "pending" response for fire-and-forget / still-running runs. `run_flow` never raises on a result-fetch problem.

**Expected outcome**: A non-Python custom UI, monitoring component, or ingest pipeline can consume one typed, JSON-serialisable Flow outcome regardless of the Flow. The shape is Flow-agnostic and needs no change when Tasks are added.

## Flow response retrieval (fire-and-forget → poll later)
__DONE__

**Problem**: `run_flow` with the default `timeout=0` (fire-and-forget) returns a "pending" `FlowResponse` (`success=None`, empty `task_results`) containing only `flow_run_id`. There is no way to retrieve the outcome later without reconstructing the Prefect-client logic — `FlowResponse` synthesis, task-run query, verbatim-result fetch — that already lives inside `run_flow`.

**Proposed Solution**: Add a symmetric retrieval pair `get_flow_response(flow_run_id)` / `get_flow_response_async(flow_run_id)` to `execute.py`, re-exported from the package. Given a `flow_run_id` (UUID or str), they read the run from the Prefect client and apply the same three-tier response logic as `run_flow`: verbatim flow response read back from the run's published artifact (completed *or* failed), synthesised-with-task-run-query otherwise, pending while not terminal. `run_flow` never raises; neither do these.

Key design decisions:
- `incoming` is reconstructed from the run's stored `parameters["message"]` (Prefect retains them), so callers keep no per-run state. An explicit `incoming=` kwarg overrides. Raises `ValueError` only if neither source is available.
- Flow name is resolved via a `read_flow(flow_id)` client call (the only reliable source once we no longer have `deployment_name`); falls back to the run's `name` slug on failure.
- Both helpers share `_to_flow_response` and `_query_task_results` with `run_flow`, keeping the response logic in one place. `get_flow_response` bridges to the async implementation via `run_coro_as_sync`, matching the pattern of `run_flow`.
- `status` uses `state.type.value` (not `str(state.type)`): Prefect's `StateType` enum stringifies to `"StateType.SCHEDULED"` not `"SCHEDULED"`. Discovered via the integration demo; fixed across the synthesis path and the test fakes (which now use the real `StateType` enum so future regressions are caught).

**Expected outcome**: `from rpsd_flow import get_flow_response, get_flow_response_async`. Callers can implement the fire-and-forget → poll-later loop without touching the Prefect client directly.

## Flow composition (subflows)
__DONE__

**Problem**: the platform needs Flow *composition* — a "higher-level" Flow defined by one service (e.g. ingest) that invokes one or more "lower-level" Flows defined by other services (e.g. a validator) as Prefect subflows, waits for them, and branches on the outcome. The apparent friction is the `timeout`: the outermost trigger (HTTP → ingest) must be fire-and-forget because validation can be slow, yet the parent Flow genuinely needs to *wait* for the child before branching. We also want the outer caller to keep seeing a single, flat `FlowResponse` — it must not need to know subflows were involved.

**Proposed Solution**: no new execution API. `timeout` is per-invocation and the two calls live at different layers, so they never conflict — the external trigger uses `timeout=0` (fire-and-forget), while the parent → child call *inside* the Flow uses `timeout=None` (block until the child is terminal). `run_flow_async(..., timeout=None)` from inside a Flow is already a Prefect subflow: `run_deployment` auto-links the child run to the parent, so the tree is navigable in the Prefect UI regardless of the response shape. To keep the response flat, add one helper — `FlowResponse.add_subflow(child, *, detail=False, prefix=None)` — that folds a child `FlowResponse` into the parent's `task_results`: by default a single summary `TaskResult` (`task_name` = child flow name, `success` = `child.success`, first child error, child duration), or with `detail=True` every child row, each name prefixed `"<flow-name>/<task-name>"` for uniqueness.

Key design decisions:
- **No `run_subflow` helper.** Two near-identical names with opposite `timeout` defaults would confuse, and mixed long/fast parent/child cases need explicit per-call timeouts anyway. A subflow invocation is just `await run_flow_async(..., timeout=None)`.
- **Method on `FlowResponse`, not a free function.** Folding is pure data-to-data (build `TaskResult`s from another `FlowResponse`), with no I/O or Prefect coupling, so it keeps `responses.py` Prefect-free; a method is idiomatic Pydantic and discoverable on the type. Returns `self` for chaining.
- **Helper never touches `self.success`.** The parent owns its own success semantic; the child's true `success` is carried verbatim in the folded row, so it participates faithfully when the parent computes `success = all(r.success for r in task_results)` — no re-derivation.
- **Summary mode is the robust default.** A flow-level failure with no per-Task detail still appends a `success=False` row, so a failure cannot silently vanish; `detail=True` (granular, prefixed rows) is best when the child returns its own rich `task_results`.
- **Flat over nested.** A prefixed name like `validate-flow/syntax` just reads as a namespaced task name, so the caller branches on `success` over one uniform list and never interprets a subflow boundary. No `subflow_responses` nesting; if a UI ever needs to deep-link child runs from the response, the minimal future hook is an optional `flow_run_id` on `TaskResult` (noted, not built).
- **Topology caveat (operational, not API).** A blocking parent holds a concurrency slot for the child's whole duration; parent and child must be served on **separate processes / work pools** or risk slot-starvation/deadlock. Native same-process subflows would avoid this but require importing the child's code, impossible across services.

**Expected outcome**: services compose Flows across service boundaries with fire-and-forget at the edge and blocking-with-branch inside, while the outer caller consumes one flat `FlowResponse` and stays oblivious to the composition. Demonstrated by the `validate-flow` + `ingest-with-validation-flow` example in `examples/fastapi_ingest_app/subflow_example.py`.

## Flow artifacts + failure UX
__DONE__

**Problem**: the original `run_flow` recovered a Flow's rich `FlowResponse` via Prefect `state.result()`, which only works on a `Completed` state and only with deployment result persistence (`persist_result=True`). That forced two bad trade-offs: (1) to surface curated per-Task detail on failure we'd have to end failed business runs as `Completed` (green) — operationally misleading in the Prefect UI, not alertable, not retried; and (2) result persistence needs shared result storage and bloats it with the inline message. rpsd-validator had independently solved this better, by publishing the `FlowResponse` as a Prefect **Markdown artifact** and returning a `Failed` state on failure (red run).

**Proposed Solution**: upstream that pattern into rpsd-flow as `artifacts.py`. A Flow publishes its `FlowResponse` as a Markdown artifact (✅/❌ summary + a fenced `json` block of `model_dump_json()`) on every run via `publish_flow_artifact(response)`, then `return to_terminal_state(response)` (the response on success → green run; a Prefect `Failed` on failure → red run). The **artifact, not result persistence, is the durable carrier**: `run_flow` / `get_flow_response` recover the verbatim `FlowResponse` for any *terminal* run (completed *or* failed) by reading the artifact — `execute.py` replaces its `state.result()` branch with an internal artifact read, falling back to the synthesised task-run query when no artifact exists. Low-level `render_flow_markdown` / `parse_flow_artifact_json` are exposed for raw-artifact consumers (e.g. a custom UI).

Key design decisions:
- **No caller-facing artifact/key API.** The artifact key is derived by convention from the flow name on both the publish and read sides, so callers keep using plain `get_flow_response(flow_run_id)` and never see an artifact or key.
- **No `persist_result`, no `FLOW__PERSIST_RESULT` setting.** Adding our own setting would let developers enable it without configuring shared result storage; instead we lean on the artifact and leave Prefect's native `PREFECT_RESULTS_PERSIST_BY_DEFAULT` as an optional footnote for anyone wanting verbatim programmatic `state.result()`.
- **Failed runs carry curated detail automatically.** Because the artifact (published before the `Failed` return) is the verbatim source, `get_flow_response` returns the curated `FlowResponse(success=False, …)` for red runs too — the earlier "failed runs lose detail" gap disappears.
- **`to_terminal_state` hides `prefect.states.Failed`** so flow authors don't import Prefect state constructors.

**Expected outcome**: failed business runs are honest (red, alertable, retry-eligible) in the Prefect UI while still exposing curated per-Task detail; consumers read one homogeneous `FlowResponse` with no persistence setup; and rpsd-validator's private artifact helpers collapse into the shared rpsd-flow ones. Demonstrated by `subflow_example.py` + `demo.sh` Test 9.

## Subprocess Task
__DONE__

A `subprocess_task` decorator factory that builds a Prefect task running an arbitrary CLI command
via an async subprocess. Message data can flow to the script through four configurable channels:

1. **Environment variables** (default ON, via `pass_metadata_as_env`): `RPSD_WHO`, `RPSD_WHAT`,
   `RPSD_CONTENT_TYPE`, `RPSD_FILENAME`, `RPSD_WHERE`, `RPSD_CUSTOM_METADATA` (JSON-encoded).
2. **stdin** (opt-in via `pass_content_to_stdin`): pipes `message.content` bytes to the subprocess.
   Only for slim/fast messages; skipped for fat/heavy. Cannot combine with `stdin_source`.
3. **Extra CLI arguments** (`extra_args`): appended to the base command.
4. **File I/O redirection** (`stdin_source`, `stdout_target`, `stderr_target`): redirect to/from
   Path, BinaryIO, or DEVNULL.

Returns a `SubprocessResult` model with `returncode`, `stdout`, `stderr`, `success`, and optional
target paths. When `raise_on_failure=True` (default), non-zero exit raises `RuntimeError`.
Merges env vars with priority: current process → RPSD_* → `extra_env`.
