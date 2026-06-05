# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Settings for rpsd-flow.

Environment variables use double underscore delimiter:

Flow decorator settings (FLOW__ prefix):
- FLOW__NAME=my-flow
- FLOW__RETRIES=3
- FLOW__TIMEOUT_SECONDS=60.0
- FLOW__LOG_PRINTS=true

Task decorator settings (TASK__ prefix):
- TASK__NAME=my-task
- TASK__RETRIES=3
- TASK__TIMEOUT_SECONDS=30.0
- TASK__LOG_PRINTS=true

Flow server settings (FLOW_SERVE__ prefix):
- FLOW_SERVE__LIMIT=5
- FLOW_SERVE__PAUSE_ON_SHUTDOWN=true
- FLOW_SERVE__PRINT_STARTING_MESSAGE=true

Task serve settings (TASK_SERVE__ prefix):
- TASK_SERVE__LIMIT=10
- TASK_SERVE__TIMEOUT=3600.0
- TASK_SERVE__STATUS_SERVER_PORT=8080
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class FlowSettings(BaseSettings):
    """
    Standard settings for Prefect flows in the Rapsodia project.

    Values are loaded from environment variables using the ``FLOW__`` prefix.
    Any parameter set explicitly in the ``@flow`` decorator call takes
    precedence over the corresponding setting.

    Environment variables:
    - FLOW__NAME: Flow name (default: None, Prefect infers from function)
    - FLOW__DESCRIPTION: Flow description (default: None, inferred from docstring)
    - FLOW__RETRIES: Number of retries on flow run failure (default: 0)
    - FLOW__RETRY_DELAY_SECONDS: Seconds to wait between retries (default: 0.0)
    - FLOW__TIMEOUT_SECONDS: Maximum runtime in seconds (default: None)
    - FLOW__LOG_PRINTS: Whether to log print statements (default: False)
    """

    model_config = SettingsConfigDict(
        env_prefix="FLOW__",
        env_nested_delimiter="__",
    )

    name: str | None = None
    description: str | None = None
    retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout_seconds: float | None = None
    log_prints: bool = False


class TaskSettings(BaseSettings):
    """
    Standard settings for Prefect tasks in the Rapsodia project.

    Values are loaded from environment variables using the ``TASK__`` prefix.
    Any parameter set explicitly in the ``@task`` decorator call takes
    precedence over the corresponding setting.

    Environment variables:
    - TASK__NAME: Task name (default: None, Prefect infers from function)
    - TASK__DESCRIPTION: Task description (default: None, inferred from docstring)
    - TASK__RETRIES: Number of retries on task failure (default: 0)
    - TASK__RETRY_DELAY_SECONDS: Seconds to wait between retries (default: 0.0)
    - TASK__TIMEOUT_SECONDS: Maximum runtime in seconds (default: None)
    - TASK__LOG_PRINTS: Whether to log print statements (default: False)
    """

    model_config = SettingsConfigDict(
        env_prefix="TASK__",
        env_nested_delimiter="__",
    )

    name: str | None = None
    description: str | None = None
    retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout_seconds: float | None = None
    log_prints: bool = False


class FlowServeSettings(BaseSettings):
    """
    Settings for ``serve_flows()`` — configures the Prefect flow runner process.

    Values are loaded from environment variables using the ``FLOW_SERVE__`` prefix.
    Any parameter passed explicitly to ``serve_flows()`` takes precedence.

    Environment variables:
    - FLOW_SERVE__LIMIT: Max concurrent flow runs (default: None = no limit)
    - FLOW_SERVE__PAUSE_ON_SHUTDOWN: Pause schedules on SIGTERM/SIGINT (default: True)
    - FLOW_SERVE__PRINT_STARTING_MESSAGE: Print Prefect banner on startup
      (default: True)
    """

    model_config = SettingsConfigDict(
        env_prefix="FLOW_SERVE__",
        env_nested_delimiter="__",
    )

    limit: int | None = None
    pause_on_shutdown: bool = True
    print_starting_message: bool = True


class TaskServeSettings(BaseSettings):
    """
    Settings for ``serve_tasks()`` — configures the Prefect task server process.

    Values are loaded from environment variables using the ``TASK_SERVE__`` prefix.
    Any parameter passed explicitly to ``serve_tasks()`` takes precedence.

    Environment variables:
    - TASK_SERVE__LIMIT: Max concurrent task runs. Unset = Prefect default (10).
      Set to an integer to cap concurrency.
    - TASK_SERVE__TIMEOUT: Seconds after which the server exits (default: None = run
      indefinitely).
    - TASK_SERVE__STATUS_SERVER_PORT: Port for the HTTP status server
      (default: None = disabled).
    """

    model_config = SettingsConfigDict(
        env_prefix="TASK_SERVE__",
        env_nested_delimiter="__",
    )

    limit: int | None = None
    timeout: float | None = None
    status_server_port: int | None = None
