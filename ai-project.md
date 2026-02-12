# AI Project analysis

## Name

Rapsodia Commons

## Overview

Library of commond code for the Rapsodia project.
Organized into packages (uv workspace project):
- rpsd-storage
- rpsd-transport

# Workspace root

## Composable settings
__DONE__

Replace dict-based config.py with Pydantic Settings. 
Each package defines its own settings class (StorageSettings, TransportSettings). 
Create optional rpsd-settings package that composes them via RpsdSettings. 
Apps can use RpsdSettings or compose settings directly. 
Env vars use double underscore: STORAGE__PROVIDER, STORAGE__S3__BUCKET_NAME, TRANSPORT__API_KEY.

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

In addition to the existing S3 and FS providers, we must implement an "http" provider.
The load() method must use HTTP GET to retrieve the content from the specified URL.
The save() method will use HTTP POST to save the content to some API, but raise an unimplemented error for now.

## File naming
__DONE__

We must re-think the naming strategy for files in S3 and FS provider, considering the fact that S3 can filter objects having a key with a given prefix.
In the current implementation, since the "Object_id" is at the end of the key, we get a list of ALL the objects and then filter them one by one.
Also S3 object list method accept a parameter that sets the maximum number of keys to return.
Since we're always looking for a single key, we can set that limit to 2, so that:
- if 0 keys are found => it's an error
- if 2 keys are found => it's an error as well (kind of weird, because object_ids are UUIDs and, as such they could never be duplicated)
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

# rpsd-transport

## Overview

Library code helping developers to implement receiving and sending content through one of the available trasport carriers, with focus on transporting content.

## Message modes
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

Initially there'll be two "transport carriers", but more may come in the future:
- HTTP
- PubSub

Each carrier must implement a base interface with methods for sending and receiving messages.

For outline metadata messages, metadata values must NOT be inside the message body itself, but must be transported by carrier specific methods,
as described in carrier specific chapters.

### Sending

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
