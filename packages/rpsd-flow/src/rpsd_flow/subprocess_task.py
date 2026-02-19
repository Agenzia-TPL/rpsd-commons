"""
Subprocess task factory for rpsd-flow.

Provides ``create_subprocess_task`` — a factory that builds a Prefect
``@task`` which runs an arbitrary command-line script, passing data
from a ``TransportMessage`` via environment variables, stdin, and/or
extra command-line arguments.

Message data flows into the subprocess through four configurable
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

4. **File redirection** (optional):
   stdin, stdout, and/or stderr can be redirected to/from files or
   file-like objects (e.g. ``io.BytesIO``, ``open(...)``), avoiding
   in-memory buffering for large data.  When stdout or stderr is
   redirected, the corresponding ``SubprocessResult`` field is
   ``None``.
"""

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import BaseModel

from rpsd_flow.settings import TaskSettings
from rpsd_flow.tasks import task as rpsd_task
from rpsd_transport.models import TransportMessage

#: Environment variable prefix used for message metadata.
_ENV_PREFIX = "RPSD_"


class SubprocessResult(BaseModel):
    """
    Result of a subprocess task execution.

    Attributes:
        returncode: Exit code returned by the subprocess.
        stdout: Captured standard output, decoded as UTF-8. ``None``
            if stdout was not captured or was redirected.
        stderr: Captured standard error, decoded as UTF-8. ``None``
            if stderr was not captured or was redirected.
        success: ``True`` when ``returncode == 0``.
        stdout_target: Path where stdout was written, if a ``Path``
            was used as the redirect target. ``None`` otherwise.
        stderr_target: Path where stderr was written, if a ``Path``
            was used as the redirect target. ``None`` otherwise.
    """

    returncode: int
    stdout: str | None
    stderr: str | None
    success: bool
    stdout_target: Path | None = None
    stderr_target: Path | None = None


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
    *,
    # --- Prefect task parameters (resolved via TaskSettings) ---
    name: str | None = None,
    retries: int | None = None,
    retry_delay_seconds: float | None = None,
    timeout_seconds: float | None = None,
    log_prints: bool | None = None,
    settings: TaskSettings | None = None,
    task_kwargs: dict[str, Any] | None = None,
    # --- Subprocess parameters ---
    cwd: str | None = None,
    extra_env: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
    pass_metadata_as_env: bool = True,
    pass_content_to_stdin: bool = False,
    raise_on_failure: bool = True,
    stdin_source: Path | BinaryIO | None = None,
    stdout_target: Path | BinaryIO | int | None = None,
    stderr_target: Path | BinaryIO | int | None = None,
    subprocess_kwargs: dict[str, Any] | None = None,
) -> Callable:
    """
    Create a Prefect ``@task`` that runs a command-line script.

    The returned task accepts a single ``TransportMessage`` argument and
    runs the given ``command``, passing message data through the
    configured mechanisms (env vars, stdin, extra args, file
    redirection).

    Prefect task parameters (``name``, ``retries``, etc.) are resolved
    through ``TaskSettings``: explicit arguments override env-var
    defaults (``TASK__RETRIES``, ``TASK__TIMEOUT_SECONDS``, …).

    Args:
        command: Base command and arguments as a list, e.g.
            ``["python", "my_script.py"]``. ``extra_args`` are appended
            after this list at call time.
        name: Prefect task name. Defaults to the first element of
            ``command``.
        retries: Number of retries on task failure (non-zero exit code
            when ``raise_on_failure=True``). Falls back to
            ``TASK__RETRIES`` (default: 0).
        retry_delay_seconds: Seconds to wait between retries. Falls
            back to ``TASK__RETRY_DELAY_SECONDS`` (default: 0.0).
        timeout_seconds: Maximum time in seconds the subprocess may
            run. ``None`` means no timeout. Falls back to
            ``TASK__TIMEOUT_SECONDS``. Note: also enforced via
            ``subprocess.run``'s ``timeout`` parameter, which raises
            ``subprocess.TimeoutExpired`` (triggering Prefect retries
            when ``retries > 0``).
        log_prints: Whether to log print statements. Falls back to
            ``TASK__LOG_PRINTS`` (default: False).
        settings: Optional ``TaskSettings`` instance. If ``None``, one
            is created automatically from environment variables.
        task_kwargs: Additional keyword arguments forwarded to
            ``prefect.task()``, e.g. ``{"tags": ["etl"]}``.
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
            Cannot be combined with ``stdin_source``.
        raise_on_failure: If ``True`` (default), raise a ``RuntimeError``
            when the subprocess exits with a non-zero return code. This
            causes Prefect to mark the task run as failed and apply
            retries. If ``False``, the task always succeeds and callers
            must inspect ``SubprocessResult.success``.
        stdin_source: Redirect stdin from a file or file-like object.
            A ``Path`` is opened in ``"rb"`` mode automatically. A
            ``BinaryIO`` (e.g. ``io.BytesIO``, ``open(..., "rb")``)
            is passed directly — the caller is responsible for closing
            it. Cannot be combined with ``pass_content_to_stdin``.
        stdout_target: Redirect stdout to a file, file-like object, or
            ``subprocess.DEVNULL``. A ``Path`` is opened in ``"wb"``
            mode automatically. When set, ``SubprocessResult.stdout``
            is ``None``.
        stderr_target: Redirect stderr to a file, file-like object, or
            ``subprocess.DEVNULL``. A ``Path`` is opened in ``"wb"``
            mode automatically. When set, ``SubprocessResult.stderr``
            is ``None``.
        subprocess_kwargs: Additional keyword arguments forwarded to
            ``subprocess.run()``, e.g. ``{"shell": True}``. Our
            managed keys (``input``, ``stdin``, ``stdout``, ``stderr``,
            ``env``, ``cwd``, ``timeout``) take precedence over
            entries in this dict.

    Returns:
        A Prefect task callable that accepts a ``TransportMessage`` and
        returns a ``SubprocessResult``.

    Raises:
        ValueError: If both ``pass_content_to_stdin`` and
            ``stdin_source`` are specified.

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

    Example — redirect stdout to a file for large output::

        from pathlib import Path

        dump_task = create_subprocess_task(
            command=["pg_dump", "mydb"],
            name="db-dump",
            stdout_target=Path("/tmp/dump.sql"),
        )

    Example — pipe stdin from a file, discard stderr::

        import subprocess

        load_task = create_subprocess_task(
            command=["psql", "mydb"],
            name="db-load",
            stdin_source=Path("/tmp/dump.sql"),
            stderr_target=subprocess.DEVNULL,
        )
    """
    if pass_content_to_stdin and stdin_source is not None:
        raise ValueError(
            "Cannot use both 'pass_content_to_stdin=True' and "
            "'stdin_source'. Choose one mechanism for stdin."
        )

    task_name = name if name is not None else command[0]

    @rpsd_task(
        name=task_name,
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
        timeout_seconds=timeout_seconds,
        log_prints=log_prints,
        settings=settings,
        **(task_kwargs or {}),
    )
    def _subprocess_task(
        message: TransportMessage,
    ) -> SubprocessResult:
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

        # Determine stdin: stdin_source takes priority, then
        # pass_content_to_stdin, then no stdin.
        stdin_data: bytes | None = None
        stdin_handle = None
        stdin_file_to_close = None

        if stdin_source is not None:
            if isinstance(stdin_source, Path):
                stdin_file_to_close = open(  # noqa: SIM115
                    stdin_source, "rb"
                )
                stdin_handle = stdin_file_to_close
            else:
                stdin_handle = stdin_source
        elif pass_content_to_stdin and message.content is not None:
            stdin_data = message.content

        # Determine stdout target.
        stdout_handle = subprocess.PIPE
        stdout_file_to_close = None
        result_stdout_target: Path | None = None

        if stdout_target is not None:
            if isinstance(stdout_target, Path):
                stdout_file_to_close = open(  # noqa: SIM115
                    stdout_target, "wb"
                )
                stdout_handle = stdout_file_to_close
                result_stdout_target = stdout_target
            else:
                stdout_handle = stdout_target

        # Determine stderr target.
        stderr_handle = subprocess.PIPE
        stderr_file_to_close = None
        result_stderr_target: Path | None = None

        if stderr_target is not None:
            if isinstance(stderr_target, Path):
                stderr_file_to_close = open(  # noqa: SIM115
                    stderr_target, "wb"
                )
                stderr_handle = stderr_file_to_close
                result_stderr_target = stderr_target
            else:
                stderr_handle = stderr_target

        try:
            # Start from user-supplied subprocess kwargs, then
            # overlay our managed keys so they always win.
            run_kwargs: dict[str, Any] = dict(subprocess_kwargs or {})
            run_kwargs.update(
                input=(stdin_data if stdin_handle is None else None),
                stdin=stdin_handle,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env,
                cwd=cwd,
                timeout=timeout_seconds,
            )
            proc = subprocess.run(full_command, **run_kwargs)
        finally:
            if stdin_file_to_close is not None:
                stdin_file_to_close.close()
            if stdout_file_to_close is not None:
                stdout_file_to_close.close()
            if stderr_file_to_close is not None:
                stderr_file_to_close.close()

        captured_stdout = (
            proc.stdout.decode("utf-8", errors="replace") if proc.stdout else None
        )
        captured_stderr = (
            proc.stderr.decode("utf-8", errors="replace") if proc.stderr else None
        )

        result = SubprocessResult(
            returncode=proc.returncode,
            stdout=captured_stdout,
            stderr=captured_stderr,
            success=proc.returncode == 0,
            stdout_target=result_stdout_target,
            stderr_target=result_stderr_target,
        )

        if raise_on_failure and not result.success:
            stderr_info = result.stderr if result.stderr is not None else "<redirected>"
            raise RuntimeError(
                f"Subprocess '{task_name}' exited with "
                f"code {result.returncode}. "
                f"stderr: {stderr_info!r}"
            )

        return result

    return _subprocess_task
