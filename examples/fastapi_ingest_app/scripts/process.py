#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Sample processing script invoked by the subprocess task.

Demonstrates how an external script receives message data
via RPSD_* environment variables set by
``subprocess_task``.

The script:
1. Reads RPSD_WHO, RPSD_WHAT, RPSD_WHERE, RPSD_CONTENT_TYPE
   from the environment.
2. Simulates heavy processing with a sleep whose duration is
   configurable via the ``RPSD_PROCESS_SLEEP`` environment
   variable (seconds, default 3.0). Set it higher to make the
   fire-and-forget / poll-later flow easy to observe, or lower
   (even 0) to make the demo snappy.
3. Prints a JSON summary to stdout.

This is intentionally language-agnostic in spirit — any
script (Python, shell, Go, etc.) that reads env vars and
writes to stdout would work with ``subprocess_task``.
"""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime

from rpsd_storage.providers.base import StorageProvider

# Simulated processing time (seconds), tunable via RPSD_PROCESS_SLEEP.
_DEFAULT_SLEEP = 3.0

# Chunk size for the streaming read (64 KB) — small enough to keep the
# working set bounded regardless of file size.
_CHUNK_SIZE = 64 * 1024


def _sleep_seconds() -> float:
    """Read RPSD_PROCESS_SLEEP, falling back to the default if unset/invalid."""
    try:
        return float(os.environ.get("RPSD_PROCESS_SLEEP", _DEFAULT_SLEEP))
    except ValueError:
        return _DEFAULT_SLEEP


def _stream_and_verify(where: str) -> dict:
    """Stream content from storage and verify its MD5 against the metadata.

    Reads the content at *where* in fixed-size chunks via the streaming
    ``open_content`` API, so the whole payload is never held in memory —
    exactly how a validator would read a large XML file. A running MD5 is
    computed while streaming and compared to the stored metadata hash.

    ``open_content`` is content-only (there is no streaming metadata twin), so
    the expected hash comes from a separate ``load_metadata`` call.
    """
    expected = StorageProvider.load_metadata_from_url(where).hash
    hasher = hashlib.md5()
    total = 0
    chunks = 0
    with StorageProvider.open_content_from_url(where) as stream:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            total += len(chunk)
            chunks += 1
    actual = hasher.hexdigest()
    return {
        "bytes_read": total,
        "chunks": chunks,
        "md5": actual,
        "md5_matches": actual == expected,
    }


def _append_stream_log(summary: str) -> None:
    """Append the streaming summary to the file named by ``RPSD_STREAM_LOG``.

    Opt-in side channel: application logs from a Prefect deployment subprocess
    are not forwarded to the served-flow log or the UI, so when this script
    runs as the ``process-content`` task there is no other place to observe the
    streaming read. ``demo.sh`` sets ``RPSD_STREAM_LOG`` and tails the file so
    the read is visible; outside the demo (var unset) nothing is written.
    """
    path = os.environ.get("RPSD_STREAM_LOG")
    if not path:
        return
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    try:
        with open(path, "a") as f:
            f.write(f"{stamp} {summary}\n")
    except OSError as exc:
        print(f"Could not write RPSD_STREAM_LOG: {exc}", file=sys.stderr)


def main() -> None:
    who = os.environ.get("RPSD_WHO", "<unknown>")
    what = os.environ.get("RPSD_WHAT", "<unknown>")
    where = os.environ.get("RPSD_WHERE", "")
    content_type = os.environ.get("RPSD_CONTENT_TYPE", "application/octet-stream")

    sleep_seconds = _sleep_seconds()
    print(
        f"Processing content for {who}/{what} (sleep {sleep_seconds}s)...",
        file=sys.stderr,
    )

    # For fat/heavy messages, stream the content from storage (bounded memory)
    # and verify its MD5. Best-effort: a slim/fast message (no where) or an
    # unreachable URL is logged and skipped so it never breaks the run.
    content_info: dict | None = None
    if where:
        print(f"Storage URL: {where}", file=sys.stderr)
        try:
            content_info = _stream_and_verify(where)
            ok = "md5 ok" if content_info["md5_matches"] else "MD5 MISMATCH"
            summary = (
                f"Streamed {content_info['bytes_read']} bytes in "
                f"{content_info['chunks']} chunk(s) via open_content "
                f"for {who}/{what} ({ok})."
            )
            print(summary, file=sys.stderr)
            _append_stream_log(summary)
        except Exception as exc:
            msg = f"Could not stream content from storage: {exc!r}"
            print(msg, file=sys.stderr)
            _append_stream_log(msg)
    else:
        print("No storage URL (slim/fast message); skipping read.", file=sys.stderr)

    # Simulate heavy processing
    time.sleep(sleep_seconds)

    # Emit result as JSON to stdout
    result = {
        "status": "processed",
        "who": who,
        "what": what,
        "where": where,
        "content_type": content_type,
        "content": content_info,
        "message": (f"Successfully processed {what} from {who}"),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
