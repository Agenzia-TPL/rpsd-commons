"""
Subprocess task factory for rpsd-flow.

Provides ``create_subprocess_task`` — a factory that builds a Prefect
``@task`` which runs an arbitrary command-line script, passing data
from a ``TransportMessage`` via environment variables, stdin, and/or
extra command-line arguments.

Message data flows into the subprocess through three configurable
mechanisms:

1. **Environment variables** (default on):
   All message metadata is exposed as ``RPSD_*`` environment variables
   that the script can read regardless of its implementation language.
   ``RPSD_WHERE`` is the primary mechanism for fat/heavy messages —
   the script uses it to fetch content from the storage URL itself.

2. **stdin** (default off):
   The raw content bytes are piped to the subprocess's stdin. Only
   meaningful for slim/fast messages where content is already embedded.
   Skipped automatically when the message has no content (fat/heavy).

3. **Extra command-line arguments** (optional):
   Additional CLI arguments appended to the base command, allowing
   scripts to receive per-invocation parameters.
"""

import json
import os
import subprocess
from collections.abc import Callable
from typing import Any

import prefect
from pydantic import BaseModel

from rpsd_transport.models import TransportMessage

#: Environment variable prefix used for message metadata.
_ENV_PREFIX = "RPSD_"


class SubprocessResult(BaseModel):
    """
    Result of a subprocess task execution.

    Attributes:
        returncode: Exit code returned by the subprocess.
        stdout: Captured standard output, decoded as UTF-8. ``None``
            if stdout was not captured.
        stderr: Captured standard error, decoded as UTF-8. ``None``
            if stderr was not captured.
        success: ``True`` when ``returncode == 0``.
    """

    returncode: int
    stdout: str | None
    stderr: str | None
    success: bool


def _build_rpsd_env(message: TransportMessage) -> dict[str, str]:
    """Build the ``RPSD_*`` environment variables from a message.

    Args:
        message: Source ``TransportMessage``.

    Returns:
        Dict of environment variable names to string values.
        All values are non-empty strings; missing/None fields are
        omitted from the dict.
    """
    env: dict[str, str] = {}

    if message.who is not None:
        env[f"{_ENV_PREFIX}WHO"] = message.who
    if message.what is not None:
        env[f"{_ENV_PREFIX}WHAT"] = message.what

    if message.metadata.content_type is not None:
        env[f"{_ENV_PREFIX}CONTENT_TYPE"] = message.metadata.content_type
    if message.metadata.filename is not None:
        env[f"{_ENV_PREFIX}FILENAME"] = message.metadata.filename

    # RPSD_WHERE is the primary mechanism for fat/heavy messages.
    if message.where is not None:
        env[f"{_ENV_PREFIX}WHERE"] = message.where

    if message.metadata.custom_metadata:
        env[f"{_ENV_PREFIX}CUSTOM_METADATA"] = json.dumps(
            message.metadata.custom_metadata
        )

    return env


def create_subprocess_task(
    command: list[str],
    name: str | None = None,
    retries: int = 0,
    retry_delay_seconds: float = 0.0,
    timeout_seconds: float | None = None,
    cwd: str | None = None,
    extra_env: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
    pass_metadata_as_env: bool = True,
    pass_content_to_stdin: bool = False,
    raise_on_failure: bool = True,
    **task_kwargs: Any,
) -> Callable:
    """
    Create a Prefect ``@task`` that runs a command-line script.

    The returned task accepts a single ``TransportMessage`` argument and
    runs the given ``command``, passing message data through the
    configured mechanisms (env vars, stdin, extra args).

    Args:
        command: Base command and arguments as a list, e.g.
            ``["python", "my_script.py"]``. ``extra_args`` are appended
            after this list at call time.
        name: Prefect task name. Defaults to the first element of
            ``command``.
        retries: Number of retries on task failure (non-zero exit code
            when ``raise_on_failure=True``). Defaults to 0.
        retry_delay_seconds: Seconds to wait between retries.
        timeout_seconds: Maximum time in seconds the subprocess may run.
            ``None`` means no timeout. Note: this is enforced via
            ``subprocess.run``'s ``timeout`` parameter, which raises
            ``subprocess.TimeoutExpired`` (triggering Prefect retries
            when ``retries > 0``).
        cwd: Working directory for the subprocess. Defaults to the
            current working directory.
        extra_env: Additional environment variables merged *on top of*
            the current process environment (and the ``RPSD_*`` vars
            when ``pass_metadata_as_env=True``). These take precedence
            over ``RPSD_*`` vars if keys clash.
        extra_args: Additional command-line arguments appended to
            ``command`` for every invocation.
        pass_metadata_as_env: If ``True`` (default), set ``RPSD_*``
            environment variables from the message metadata:

            - ``RPSD_WHO`` — sender identifier
            - ``RPSD_WHAT`` — content category
            - ``RPSD_CONTENT_TYPE`` — MIME type
            - ``RPSD_FILENAME`` — original filename
            - ``RPSD_WHERE`` — storage URL (primary for fat/heavy msgs)
            - ``RPSD_CUSTOM_METADATA`` — JSON-encoded custom metadata
        pass_content_to_stdin: If ``True``, pipe the message's embedded
            content bytes to the subprocess's stdin. Only meaningful for
            slim/fast messages. Skipped silently when the message has no
            embedded content (fat/heavy messages). Defaults to ``False``.
        raise_on_failure: If ``True`` (default), raise a ``RuntimeError``
            when the subprocess exits with a non-zero return code. This
            causes Prefect to mark the task run as failed and apply
            retries. If ``False``, the task always succeeds and callers
            must inspect ``SubprocessResult.success``.
        **task_kwargs: Additional keyword arguments forwarded to
            ``prefect.task()``, e.g. ``tags``, ``cache_key_fn``.

    Returns:
        A Prefect task callable that accepts a ``TransportMessage`` and
        returns a ``SubprocessResult``.

    Example — fat/heavy message, script reads from URL::

        from rpsd_flow import create_subprocess_task

        ocr_task = create_subprocess_task(
            command=["python", "ocr_script.py"],
            name="ocr-task",
            retries=2,
            timeout_seconds=120.0,
        )

        # In a flow:
        result = ocr_task(message)  # RPSD_WHERE is set for the script

    Example — slim/fast message, pipe content to stdin::

        extract_task = create_subprocess_task(
            command=["jq", ".title"],
            name="extract-title",
            pass_content_to_stdin=True,
        )
    """
    task_name = name or command[0]

    @prefect.task(
        name=task_name,
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
        timeout_seconds=timeout_seconds,
        **task_kwargs,
    )
    def _subprocess_task(message: TransportMessage) -> SubprocessResult:
        # Build final environment: inherit current process env, then
        # add RPSD_* vars (if enabled), then apply extra_env overrides.
        env = dict(os.environ)

        if pass_metadata_as_env:
            env.update(_build_rpsd_env(message))

        if extra_env:
            env.update(extra_env)

        # Build final command (base + extra args).
        full_command = list(command)
        if extra_args:
            full_command.extend(extra_args)

        # Determine stdin payload.
        stdin_data: bytes | None = None
        if pass_content_to_stdin and message.content is not None:
            stdin_data = message.content

        proc = subprocess.run(
            full_command,
            input=stdin_data,
            env=env,
            cwd=cwd,
            capture_output=True,
            timeout=timeout_seconds,
        )

        result = SubprocessResult(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace")
            if proc.stdout
            else None,
            stderr=proc.stderr.decode("utf-8", errors="replace")
            if proc.stderr
            else None,
            success=proc.returncode == 0,
        )

        if raise_on_failure and not result.success:
            raise RuntimeError(
                f"Subprocess '{task_name}' exited with code "
                f"{result.returncode}. stderr: {result.stderr!r}"
            )

        return result

    return _subprocess_task
