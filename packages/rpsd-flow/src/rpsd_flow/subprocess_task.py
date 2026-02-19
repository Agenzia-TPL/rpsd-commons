"""
Subprocess task decorator for rpsd-flow.

Provides ``subprocess_task`` — a decorator factory that builds a Prefect
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

import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

from prefect.tasks import Task
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


def subprocess_task(
    command: list[str] | None = None,
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
) -> Callable[[Callable], Task]:
    """
    Decorator factory that creates a Prefect ``@task`` running a CLI script.

    Decorate a function whose **name** becomes the Prefect task name
    (snake_case converted to kebab-case automatically) and whose
    **docstring** becomes the task description. The decorated name becomes
    a callable Prefect task that runs a command-line script as an async
    subprocess.

    The command to run can be specified in two ways:

    1. **Static command** — pass ``command`` to the decorator. The function
       body is ignored (use ``...`` as a placeholder).
    2. **Command builder** — omit ``command``. The function body is called
       at runtime with the ``TransportMessage`` and must return the command
       as a ``list[str]``. This allows choosing the command dynamically
       based on the message.

    The task accepts a single ``TransportMessage`` argument and runs the
    command, passing message data through the configured mechanisms
    (env vars, stdin, extra args, file redirection).

    Prefect task parameters (``retries``, etc.) are resolved through
    ``TaskSettings``: explicit arguments override env-var defaults
    (``TASK__RETRIES``, ``TASK__TIMEOUT_SECONDS``, …).

    Args:
        command: Base command and arguments as a list, e.g.
            ``["python", "my_script.py"]``. ``extra_args`` are appended
            after this list at call time. When ``None`` (the default),
            the decorated function is called at runtime with the message
            and must return the command list.
        name: Prefect task name. Defaults to the decorated function's
            name with underscores replaced by hyphens.
        retries: Number of retries on task failure (non-zero exit code
            when ``raise_on_failure=True``). Falls back to
            ``TASK__RETRIES`` (default: 0).
        retry_delay_seconds: Seconds to wait between retries. Falls
            back to ``TASK__RETRY_DELAY_SECONDS`` (default: 0.0).
        timeout_seconds: Maximum time in seconds the subprocess may
            run. ``None`` means no timeout. Falls back to
            ``TASK__TIMEOUT_SECONDS``. Enforced via
            ``asyncio.wait_for``, which reliably kills the subprocess
            when the deadline is reached.
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
            ``asyncio.create_subprocess_exec()``. Keys managed by this
            task (``stdin``, ``stdout``, ``stderr``, ``env``, ``cwd``)
            take precedence over entries in this dict. The ``input``
            and ``timeout`` keys are not forwarded (they are handled
            via ``proc.communicate()`` and ``asyncio.wait_for``
            respectively).

    Returns:
        A decorator that accepts a function and returns a Prefect
        task callable accepting a ``TransportMessage`` and returning
        a ``SubprocessResult``.

    Raises:
        ValueError: If both ``pass_content_to_stdin`` and
            ``stdin_source`` are specified.

    Example — static command, script reads from storage URL::

        from rpsd_flow import subprocess_task

        @subprocess_task(
            command=["python", "ocr_script.py"],
            retries=2,
            timeout_seconds=120.0,
        )
        def ocr_document(message: TransportMessage) -> SubprocessResult:
            \"\"\"Run OCR on the document at RPSD_WHERE.\"\"\"
            ...

        # In a flow:
        result = ocr_document(message)

    Example — command builder, choose script based on content type::

        @subprocess_task(retries=2, timeout_seconds=120.0)
        def process_content(
            message: TransportMessage,
        ) -> list[str]:
            \"\"\"Choose processor based on content type.\"\"\"
            if message.metadata.content_type == "application/pdf":
                return ["python", "ocr_script.py"]
            return ["python", "text_script.py"]

    Example — slim/fast message, pipe content to stdin::

        @subprocess_task(
            command=["jq", ".title"],
            pass_content_to_stdin=True,
        )
        def extract_title(message: TransportMessage) -> SubprocessResult:
            \"\"\"Extract the title field via jq.\"\"\"
            ...

    Example — redirect stdout to a file for large output::

        from pathlib import Path

        @subprocess_task(
            command=["pg_dump", "mydb"],
            stdout_target=Path("/tmp/dump.sql"),
        )
        def dump_database(message: TransportMessage) -> SubprocessResult:
            \"\"\"Dump the database to /tmp/dump.sql.\"\"\"
            ...
    """
    if pass_content_to_stdin and stdin_source is not None:
        raise ValueError(
            "Cannot use both 'pass_content_to_stdin=True' and "
            "'stdin_source'. Choose one mechanism for stdin."
        )

    def decorator(fn: Callable) -> Task:
        task_name = name if name is not None else fn.__name__.replace("_", "-")
        description = fn.__doc__

        async def _run(
            message: TransportMessage,
        ) -> SubprocessResult:
            # Build final environment: inherit current process env, then
            # add RPSD_* vars (if enabled), then apply extra_env overrides.
            env = dict(os.environ)

            if pass_metadata_as_env:
                env.update(_build_rpsd_env(message))

            if extra_env:
                env.update(extra_env)

            # Build final command: static or from builder.
            base_command = command if command is not None else fn(message)
            full_command = list(base_command)
            if extra_args:
                full_command.extend(extra_args)

            # Determine stdin: stdin_source takes priority, then
            # pass_content_to_stdin, then no stdin.
            communicate_input: bytes | None = None
            stdin_for_proc = None
            stdin_file_to_close = None

            if stdin_source is not None:
                if isinstance(stdin_source, Path):
                    stdin_file_to_close = open(  # noqa: SIM115
                        stdin_source, "rb"
                    )
                    stdin_for_proc = stdin_file_to_close
                else:
                    stdin_for_proc = stdin_source
            elif pass_content_to_stdin and message.content is not None:
                communicate_input = message.content
                stdin_for_proc = asyncio.subprocess.PIPE

            # Determine stdout target.
            stdout_handle: Any = asyncio.subprocess.PIPE
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
            stderr_handle: Any = asyncio.subprocess.PIPE
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

            # Filter subprocess_kwargs: remove keys that are managed
            # by us or that are incompatible with
            # asyncio.create_subprocess_exec (input, timeout).
            proc_kwargs: dict[str, Any] = {
                k: v
                for k, v in (subprocess_kwargs or {}).items()
                if k
                not in {
                    "input",
                    "timeout",
                    "stdin",
                    "stdout",
                    "stderr",
                    "env",
                    "cwd",
                }
            }

            try:
                proc = await asyncio.create_subprocess_exec(
                    *full_command,
                    stdin=stdin_for_proc,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    env=env,
                    cwd=cwd,
                    **proc_kwargs,
                )

                try:
                    if timeout_seconds is not None:
                        stdout_bytes, stderr_bytes = await asyncio.wait_for(
                            proc.communicate(input=communicate_input),
                            timeout=timeout_seconds,
                        )
                    else:
                        stdout_bytes, stderr_bytes = await proc.communicate(
                            input=communicate_input
                        )
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise

            finally:
                if stdin_file_to_close is not None:
                    stdin_file_to_close.close()
                if stdout_file_to_close is not None:
                    stdout_file_to_close.close()
                if stderr_file_to_close is not None:
                    stderr_file_to_close.close()

            captured_stdout = (
                stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else None
            )
            captured_stderr = (
                stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else None
            )

            # returncode is always set after communicate() resolves.
            assert proc.returncode is not None
            result = SubprocessResult(
                returncode=proc.returncode,
                stdout=captured_stdout,
                stderr=captured_stderr,
                success=proc.returncode == 0,
                stdout_target=result_stdout_target,
                stderr_target=result_stderr_target,
            )

            if raise_on_failure and not result.success:
                stderr_info = (
                    result.stderr if result.stderr is not None else "<redirected>"
                )
                raise RuntimeError(
                    f"Subprocess '{task_name}' exited with "
                    f"code {result.returncode}. "
                    f"stderr: {stderr_info!r}"
                )

            return result

        return rpsd_task(
            name=task_name,
            description=description,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            timeout_seconds=timeout_seconds,
            log_prints=log_prints,
            settings=settings,
            **(task_kwargs or {}),
        )(_run)

    return decorator
