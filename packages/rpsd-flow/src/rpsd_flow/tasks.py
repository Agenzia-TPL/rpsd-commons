"""
Task decorator factory for rpsd-flow.

Provides a ``task`` decorator factory that wraps Prefect's ``@task``
with project-standard defaults loaded from environment variables via
``TaskSettings``. Explicit decorator arguments always take precedence
over settings values.

Usage::

    from rpsd_flow import task
    from rpsd_transport import TransportMessage

    @task(name="my-task", retries=3)
    def my_task(message: TransportMessage) -> None:
        ...
"""

from collections.abc import Callable
from typing import Any

import prefect

from rpsd_flow.settings import TaskSettings


def task(
    name: str | None = None,
    description: str | None = None,
    retries: int | None = None,
    retry_delay_seconds: float | None = None,
    timeout_seconds: float | None = None,
    log_prints: bool | None = None,
    settings: TaskSettings | None = None,
    **kwargs: Any,
) -> Callable:
    """
    Decorator factory that wraps Prefect's ``@task`` with rpsd defaults.

    Loads default values from ``TaskSettings`` (env vars with ``TASK__``
    prefix). Explicit arguments passed to this decorator always override
    the corresponding settings value.

    Args:
        name: Task name. Overrides ``TASK__NAME`` env var. If neither
            is set, Prefect infers the name from the function name.
        description: Task description. Overrides ``TASK__DESCRIPTION``.
            If neither is set, Prefect uses the function docstring.
        retries: Number of retries on task failure. Overrides
            ``TASK__RETRIES`` (default: 0).
        retry_delay_seconds: Seconds to wait between retries. Overrides
            ``TASK__RETRY_DELAY_SECONDS`` (default: 0.0).
        timeout_seconds: Maximum runtime in seconds. Overrides
            ``TASK__TIMEOUT_SECONDS`` (default: None = no timeout).
        log_prints: Whether to log print statements. Overrides
            ``TASK__LOG_PRINTS`` (default: False).
        settings: Optional ``TaskSettings`` instance. If None, one is
            created automatically from environment variables.
        **kwargs: Additional keyword arguments passed through to
            ``prefect.task()``, e.g. ``cache_key_fn``, ``tags``.

    Returns:
        A Prefect task decorator configured with the resolved settings.

    Example::

        @task(name="process-document", retries=2, timeout_seconds=60.0)
        def process_document(message: TransportMessage) -> str:
            ...

        # Submit the task from within a flow:
        @flow(name="my-flow")
        def my_flow(message: TransportMessage) -> None:
            future = process_document.submit(message)
            result = future.result()
    """
    resolved_settings = settings or TaskSettings()

    resolved_name = name if name is not None else resolved_settings.name
    resolved_description = (
        description if description is not None else resolved_settings.description
    )
    resolved_retries = retries if retries is not None else resolved_settings.retries
    resolved_retry_delay = (
        retry_delay_seconds
        if retry_delay_seconds is not None
        else resolved_settings.retry_delay_seconds
    )
    resolved_timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else resolved_settings.timeout_seconds
    )
    resolved_log_prints = (
        log_prints if log_prints is not None else resolved_settings.log_prints
    )

    return prefect.task(
        name=resolved_name,
        description=resolved_description,
        retries=resolved_retries,
        retry_delay_seconds=resolved_retry_delay,
        timeout_seconds=resolved_timeout,
        log_prints=resolved_log_prints,
        **kwargs,
    )
