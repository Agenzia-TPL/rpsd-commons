#!/usr/bin/env python3
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

import json
import os
import sys
import time

# Simulated processing time (seconds), tunable via RPSD_PROCESS_SLEEP.
_DEFAULT_SLEEP = 3.0


def _sleep_seconds() -> float:
    """Read RPSD_PROCESS_SLEEP, falling back to the default if unset/invalid."""
    try:
        return float(os.environ.get("RPSD_PROCESS_SLEEP", _DEFAULT_SLEEP))
    except ValueError:
        return _DEFAULT_SLEEP


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
    if where:
        print(
            f"Storage URL: {where}",
            file=sys.stderr,
        )

    # Simulate heavy processing
    time.sleep(sleep_seconds)

    # Emit result as JSON to stdout
    result = {
        "status": "processed",
        "who": who,
        "what": what,
        "where": where,
        "content_type": content_type,
        "message": (f"Successfully processed {what} from {who}"),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
