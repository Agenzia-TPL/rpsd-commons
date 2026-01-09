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

Replace dict-based config.py with Pydantic Settings. Each package defines its own settings class (StorageSettings, TransportSettings). Create optional rpsd-settings package that composes them via RpsdSettings. Apps can use RpsdSettings or compose settings directly. Env vars use double underscore: STORAGE__PROVIDER, STORAGE__S3__BUCKET_NAME, TRANSPORT__API_KEY.

# rpsd-storage

## 001 - main refactoring

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

## 002 - implement "http" provider

In addition to the existing S3 and FS providers, we must implement an "http" provider.
The load() method must use HTTP GET to retrieve the data from the specified URL.
The save() method will use HTTP POST to save the data to some API, but raise an unimplemented error for now.

## 003 - file naming

We must re-think the naming strategy for files in S3 and FS provider, considering the fact that S3 can filter objects having a key with a given prefix.
In the current implementation, since the "Object_id" is at the end of the key, we get a list of ALL the objects and then filter them one by one.
Also S3 object list method accept a parameter that sets the maximum number of keys to return.
Since we're always looking for a single key, with can set that limit to 2.
If 0 keys are found, it's an error.
If 2 keys are found, it's an error as well, but kind of weird, because object_ids are UUIDs and, as suchm they could never be duplicated.
If 1 key is found, that's it.
I don't knnow for FS, but for S3 this way should be much faster, shouldn't it?
Besides... putting "who" and "what" into the object/file name is only to facilitate manual identification of objects/files, by looking at their names.
From the point of view of hte code, using only the "object_id" would be much better...
Should we put "who" and "what" into the path instead (or into "/" separated parts of the key for S3), like: who/what/object_id?
This way object/files would be equally easy to manually locate, but, at the same time, fast to retrieve by code.
What do you think?

## 004 - indentifier

We need to add to rpsd-storage a concept of "storage identifier", that must be a single value expressing both the type of storage (S3 or FS)
and the address (URL or path) of a specific saved data.
We must add method that, given a "storage indentifier" , will instantiate the correct provider class
and call its load() method, passing to it the data address.
For the S3 provider, both ARNs and presigned URLs must be supported as data address.
For the FS provider, both absolute/relative file path and file URLs must be supported as data address.
We may consider to expand what is currently called "object_id" to also store the provider type part, 
so that an object_id is sufficient to actually retrieve a specific save data.
Or we may leave it as an indentifier valid only for the storage provider that created it and separately manage the provider type.

## 005 - Metadata compare method

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

# rpsd-messaging

## 001 - renaming considerations

I'm thinking about renaming the rpsd-messaging package to rpsd-transport, 
because it won't actually be about sending messages, but about transporting data.
This will be possible by three "transport means" (should find a good name for this concept),
but more may come in the future, so we better plan for extensibility:
- http (through HTTP POST)
- Dapr service invocation
- Dapr PubSub
Regardless of the transport mean, I envision two types of messages:
- Slim => data to be sent is small enough to be directly inlined into the message payload
- Fat => data to be sent is too big to go into the message payload and it will be shared by some other method
Since a Slim message will indeed be bigger than a Fat one, for data will be inside the payload, we'll add two new words:
- Fast => data to be sent is small enough to be directly inlined into the message payload
- Heavy => data to be sent is too big to go into the message payload and it will be shared by some other method
that better convoy the meaning of having little data to send, through inlined, hence bigger payload, or more data, through a smaller message.
In the end Slim/Fat and Fast/Heavy will be used interchengeably, with a good initial explanation, such as:
> "Slim messages contain small data directly (fast access, bigger payload), while Fat messages reference large external data (heavy processing, smaller message)."

# rpsd-transport

## 001 - Overview
This package (renamed form rpsd-messaging), should contain "library" code helping developers to implement
receiving and sending data through one of the available trasport means (using FastAPI for receiving through HTTP)
(refer to "# rpsd-messaging ## 001 - renaming considerations" in current file).
In case of Fat (aka Heavy) data, the rpsd-storage package must be used for sharing data, and the message payload must have a "where" field,
with the URL of the data itself.

We must envision two kind data transport:
- external => data is received or sent to an "external system" (a system that can not share storage with the receving or sending system)
- internal => data is received or sent to an "internal system" (a system that can share storage with the receving or sending system)
The "http" transport mean is primarly intended for external transports, but it may nonetheless be used for internal ones, too.
The Dapr service invocation and Dapr PubSub transport means are available for internal transports only.

In case of an external http transport of Fat (aka Heavy) data, the "where" value must be set to the URL that the receiving system must call
(using an HTTP GET method), to retrieve the data itself.
The sending part must make the content available at the URL specified by the "where" value without any authentication mechanism.
The rpsd-transport package must facilitate the implementation of both cases.

In case of an internal transport of Fat (aka Heavy) data, the "where" value must be set to the url where the receiving system can read the data itself,
usng the "load_from_url" staticmethod of StorageProvider in rpsd-storage.

The "http" transport mean is intended in this context to implement APIs that an external system may invoke (receive data from external systems)
or to invoke an external system APIs (send data to external systems).
In this case the external system does not have access to shared storage, hence, in case of a Fat/Heavy message, 
data must be made available through HTTP as well.
When receiving data, if the "where" value is specified, it must be an URL that the "http" mean can call to retrieve the data itself.
When sending data, on reverse, the "http" mean must expose an API that the external system can call to retrieve the data (using FastAPI for this).
Upon receving data from external system, the "http" transport mean must save it to one of the storage provided by the rpsd-package,
so that, from that moment on, it can be shared with other internal systems.

We may use the "config" sytem in rpsd_commons, to parametrize the type of storage to use (FS or S3) and their need arguments
(e.g. base_path for FS and bucket_name for S3).

