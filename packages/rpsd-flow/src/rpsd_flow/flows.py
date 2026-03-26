# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Flow decorator factory for rpsd-flow.

Provides a ``flow`` decorator factory that wraps Prefect's ``@flow``
with project-standard defaults loaded from environment variables via
``FlowSettings``. Explicit decorator arguments always take precedence
over settings values.

Usage::

    from rpsd_flow import flow
    from rpsd_transport import TransportMessage

    @flow(name="my-flow", retries=2)
    def my_flow(message: TransportMessage) -> None:
        ...
"""

from collections.abc import Callable
from typing import Any

import prefect

from rpsd_flow.settings import FlowSettings


def flow(
    name: str | None = None,
    description: str | None = None,
    retries: int | None = None,
    retry_delay_seconds: float | None = None,
    timeout_seconds: float | None = None,
    log_prints: bool | None = None,
    settings: FlowSettings | None = None,
    **kwargs: Any,
) -> Callable:
    """
    Decorator factory that wraps Prefect's ``@flow`` with rpsd defaults.

    Loads default values from ``FlowSettings`` (env vars with ``FLOW__``
    prefix). Explicit arguments passed to this decorator always override
    the corresponding settings value.

    Args:
        name: Flow name. Overrides ``FLOW__NAME`` env var. If neither
            is set, Prefect infers the name from the function name.
        description: Flow description. Overrides ``FLOW__DESCRIPTION``.
            If neither is set, Prefect uses the function docstring.
        retries: Number of retries on flow run failure. Overrides
            ``FLOW__RETRIES`` (default: 0).
        retry_delay_seconds: Seconds to wait between retries. Overrides
            ``FLOW__RETRY_DELAY_SECONDS`` (default: 0.0).
        timeout_seconds: Maximum runtime in seconds. Overrides
            ``FLOW__TIMEOUT_SECONDS`` (default: None = no timeout).
        log_prints: Whether to log print statements. Overrides
            ``FLOW__LOG_PRINTS`` (default: False).
        settings: Optional ``FlowSettings`` instance. If None, one is
            created automatically from environment variables.
        **kwargs: Additional keyword arguments passed through to
            ``prefect.flow()``.

    Returns:
        A Prefect flow decorator configured with the resolved settings.

    Example::

        @flow(name="ingest-flow", retries=3, timeout_seconds=120.0)
        def ingest_flow(message: TransportMessage) -> None:
            ...

        # Serving the flow (single deployment):
        if __name__ == "__main__":
            ingest_flow.serve(name="ingest-deployment")
    """
    resolved_settings = settings or FlowSettings()

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

    return prefect.flow(
        name=resolved_name,
        description=resolved_description,
        retries=resolved_retries,
        retry_delay_seconds=resolved_retry_delay,
        timeout_seconds=resolved_timeout,
        log_prints=resolved_log_prints,
        **kwargs,
    )
