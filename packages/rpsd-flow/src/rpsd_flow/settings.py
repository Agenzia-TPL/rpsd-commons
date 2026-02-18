"""
Settings for rpsd-flow: FlowSettings and TaskSettings.

Environment variables use double underscore delimiter:
- FLOW__NAME=my-flow
- FLOW__RETRIES=3
- FLOW__TIMEOUT_SECONDS=60.0
- FLOW__LOG_PRINTS=true

- TASK__NAME=my-task
- TASK__RETRIES=3
- TASK__TIMEOUT_SECONDS=30.0
- TASK__LOG_PRINTS=true
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
