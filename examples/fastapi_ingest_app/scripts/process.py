#!/usr/bin/env python3
"""
Sample processing script invoked by the subprocess task.

Demonstrates how an external script receives message data
via RPSD_* environment variables set by
``subprocess_task``.

The script:
1. Reads RPSD_WHO, RPSD_WHAT, RPSD_WHERE, RPSD_CONTENT_TYPE
   from the environment.
2. Simulates heavy processing with a short sleep.
3. Prints a JSON summary to stdout.

This is intentionally language-agnostic in spirit — any
script (Python, shell, Go, etc.) that reads env vars and
writes to stdout would work with ``subprocess_task``.
"""

import json
import os
import sys
import time


def main() -> None:
    who = os.environ.get("RPSD_WHO", "<unknown>")
    what = os.environ.get("RPSD_WHAT", "<unknown>")
    where = os.environ.get("RPSD_WHERE", "")
    content_type = os.environ.get("RPSD_CONTENT_TYPE", "application/octet-stream")

    print(
        f"Processing content for {who}/{what}...",
        file=sys.stderr,
    )
    if where:
        print(
            f"Storage URL: {where}",
            file=sys.stderr,
        )

    # Simulate heavy processing
    time.sleep(20)

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
