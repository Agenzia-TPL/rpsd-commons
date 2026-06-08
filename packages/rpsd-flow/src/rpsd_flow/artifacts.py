# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Result artifacts for rpsd-flow.

A Flow records its outcome by **publishing a Markdown artifact** carrying a
human ✅/❌ summary *and* a fenced ``json`` block with the full
:class:`FlowResponse`. The artifact — not Prefect result persistence — is the
durable, UI-visible, machine-readable carrier of the outcome: it is published on
success and failure alike, so the outcome survives regardless of run state.

Flow authors use two helpers::

    from rpsd_flow import flow, publish_flow_artifact, to_terminal_state

    @flow(name="netex-validate")
    def netex_validate(message):
        response = FlowResponse(...)        # build it from the Tasks' outcomes
        publish_flow_artifact(response)     # always, before deciding the state
        return to_terminal_state(response)  # FlowResponse (green) | Failed (red)

Callers do **not** touch artifacts or keys: ``run_flow`` / ``get_flow_response``
read the artifact internally (by a key derived from the flow name) and return
the rich :class:`FlowResponse` for any terminal run — see ``execute.py``.

``render_flow_markdown`` / ``parse_flow_artifact_json`` are low-level helpers for
code that deliberately works with the raw artifact (e.g. a custom UI rendering
the markdown); normal flow authors and callers need neither.
"""

import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from rpsd_flow.responses import FlowResponse

if TYPE_CHECKING:
    from prefect.client.schemas.objects import State

# Matches the fenced ``json`` block that ``render_flow_markdown`` embeds.
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _badge(success: bool | None) -> str:
    """Outcome badge: pending when ``success`` is not yet known."""
    if success is None:
        return "⏳"
    return "✅" if success else "❌"


def _flow_artifact_key(flow_name: str) -> str:
    """Derive a stable, valid Prefect artifact key from a Flow name.

    Prefect artifact keys allow only lowercase letters, numbers and dashes, so
    e.g. ``"netex_validate"`` becomes ``"netex-validate-response"``. The same
    derivation is used on the publish and read sides, so they always agree and
    callers never handle a key.
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", flow_name.strip().lower().replace("_", "-"))
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"{slug or 'flow'}-response"


def render_flow_markdown(response: FlowResponse) -> str:
    """Render a :class:`FlowResponse` as a Prefect Markdown artifact body.

    Two consumers in mind: humans browsing the Prefect UI (summary + table) and
    a custom UI parsing the fenced ``json`` block at the bottom. The optional
    lifecycle fields are tolerated, so a pending/partial response renders too.
    """
    inc = response.incoming
    rows = []
    for r in response.task_results:
        duration = f"{r.duration:.2f}s" if r.duration is not None else "—"
        rows.append(
            f"| `{r.task_name}` | {_badge(r.success)} | {duration} | {r.error or ''} |"
        )
    table = "\n".join(rows) if rows else "| (no tasks ran) | — | — | — |"

    started = response.started_at.isoformat() if response.started_at else "—"
    finished = response.finished_at.isoformat() if response.finished_at else "—"
    payload_json = response.model_dump_json(indent=2)

    return (
        f"# Flow response: `{response.flow_name}`\n"
        f"\n"
        f"- **File**: `{inc.who}/{inc.what}/{inc.metadata.filename or '?'}`\n"
        f"- **Storage**: `{inc.where or '(slim message — content inline)'}`\n"
        f"- **OK**: {_badge(response.success)}\n"
        f"- **Status**: `{response.status}`\n"
        f"- **Started**: `{started}`\n"
        f"- **Finished**: `{finished}`\n"
        f"\n"
        f"| Task | OK | Duration | Error |\n"
        f"|------|----|----------|-------|\n"
        f"{table}\n"
        f"\n"
        f"## Raw response (JSON)\n"
        f"\n"
        f"```json\n"
        f"{payload_json}\n"
        f"```\n"
    )


def parse_flow_artifact_json(markdown: str) -> FlowResponse:
    """Reconstruct a :class:`FlowResponse` from an artifact's markdown body.

    Extracts the fenced ``json`` block embedded by ``render_flow_markdown``.

    Raises:
        ValueError: If no fenced ``json`` block is present.
    """
    match = _JSON_BLOCK_RE.search(markdown)
    if match is None:
        raise ValueError("no fenced JSON block found in artifact markdown")
    return FlowResponse.model_validate_json(match.group(1))


def publish_flow_artifact(
    response: FlowResponse,
    *,
    description: str | None = None,
) -> UUID | None:
    """Publish ``response`` as a Prefect Markdown artifact.

    The artifact key is derived from ``response.flow_name`` (so
    ``run_flow`` / ``get_flow_response`` can find it again with no caller-side
    key handling). Call this from inside a running Flow/Task, once per run,
    before returning.

    Returns:
        The created artifact's id, or ``None`` if Prefect returns none.
    """
    from prefect.artifacts import create_markdown_artifact

    if description is None:
        description = (
            f"Outcome of {response.flow_name} for "
            f"{response.incoming.who}/{response.incoming.what}"
        )
    return create_markdown_artifact(
        key=_flow_artifact_key(response.flow_name),
        markdown=render_flow_markdown(response),
        description=description,
    )


def to_terminal_state(response: FlowResponse) -> "FlowResponse | State":
    """Pick a Flow's terminal return value from its ``FlowResponse``.

    Returns the ``response`` unchanged when ``response.success`` is truthy (the
    run ends *Completed* / green). Otherwise returns a Prefect ``Failed`` state
    (the run ends *Failed* / red, so the Prefect UI is honest and retries can
    fire) whose message is the first failing Task's error. The curated detail
    still reaches consumers through the published artifact.
    """
    if response.success:
        return response

    from prefect.states import Failed

    message = next(
        (r.error for r in response.task_results if not r.success and r.error),
        None,
    )
    return Failed(message=message or f"{response.flow_name} failed")


async def _read_response_from_artifact_async(
    flow_run_id: Any,
    flow_name: str,
) -> FlowResponse | None:
    """Read a run's published :class:`FlowResponse` back from its artifact.

    Used by ``execute.py`` as the verbatim source for a terminal run. Returns
    ``None`` (so the caller falls back to a synthesised task-run query) when the
    run published no matching artifact or it cannot be parsed. Never raises.
    """
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import (
        ArtifactFilter,
        ArtifactFilterFlowRunId,
        ArtifactFilterKey,
    )
    from prefect.client.schemas.sorting import ArtifactSort

    key = _flow_artifact_key(flow_name)
    try:
        async with get_client() as client:
            artifacts = await client.read_artifacts(
                artifact_filter=ArtifactFilter(
                    flow_run_id=ArtifactFilterFlowRunId(any_=[flow_run_id]),
                    key=ArtifactFilterKey(any_=[key]),
                ),
                sort=ArtifactSort.CREATED_DESC,
                limit=1,
            )
    except Exception:
        return None

    if not artifacts:
        return None
    data = getattr(artifacts[0], "data", None)
    if not isinstance(data, str):
        return None
    try:
        return parse_flow_artifact_json(data)
    except Exception:
        return None
