# AI Project analysis

## Name

Rapsodia Commons

## Overview

Library of commond code for the Rapsodia project.
Organized into packages (uv workspace project):
- rpsd-storage
- rpsd-transport
- rpsd-workflow

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

Initially there'll be three "transport carriers", but more may come in the future:
- HTTP
- Dapr Service invocation
- Dapr PubSub

Each carrier must implement a base interface, with the following methods:
- send_slimfast => send content as a Slim/Fast message (must support both inline and outline metadata)
- send_fatheavy => send content as a Fat/Heavy message (must support both inline and outline metadata)

Both methods share these parameters (in order):
- recipient => target identifier (URL for HTTP, app_id for Dapr, etc.)
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

For outline metadata messages, metadata values must NOT be inside the message body itself, but must be transported by carrier specific methods,
as described in the following chapters.

### HTTP carrier

This carrier is based on FastAPI and is primarly intended for the external transport scope, but it may nonetheless be used for the internal one, too.
Is intended to implement APIs that an external system may invoke (receive content from external systems)
or to invoke an external system APIs (send content to external systems).
In the latter case the external system does not have access to shared storage, hence, in case of a Fat/Heavy message, 
content must be made available through HTTP as well.
When receiving content, if the "where" value is specified, it must be an URL that the "http" carrier can call to retrieve the content itself.
When sending content, on reverse, the "http" carrier must expose an API (using FastAPI for this) that the external system can call to retrieve the content.
Upon receving content from external system, the "http" transport carrier must save it to one of the storage provided by the rpsd-storage package,
so that, from that moment on, it can be shared with other internal systems.
We may use the "config" sytem in rpsd_commons, to parametrize the type of storage to use for this (FS or S3) and their need arguments
(e.g. base_path for FS and bucket_name for S3).

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

### Dapr Service invocation

This carrier is base on the Service invocation building block of Dapr and is available for the internal transport scope only.

### Dapr PubSub

This carrier is base on the Publish & subscribe building block of Dapr and is available for the internal transport scope only.
