# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""Tests for the result-artifact helpers."""

from datetime import UTC, datetime

import pytest
from prefect.client.schemas.objects import State

from rpsd_flow.artifacts import (
    _flow_artifact_key,
    parse_flow_artifact_json,
    publish_flow_artifact,
    render_flow_markdown,
    to_terminal_state,
)
from rpsd_flow.responses import FlowResponse, TaskResult
from rpsd_transport.models import MessageMetadata, TransportMessage


def _message(who: str = "sender", what: str = "document") -> TransportMessage:
    return TransportMessage(metadata=MessageMetadata(who=who, what=what))


def _response(*, success: bool | None = True, with_tasks: bool = True) -> FlowResponse:
    tasks = (
        [
            TaskResult(task_name="syntax", success=True, duration=0.5),
            TaskResult(task_name="semantic", success=False, error="bad ref"),
        ]
        if with_tasks
        else []
    )
    return FlowResponse(
        incoming=_message(),
        flow_name="netex-validate",
        status="COMPLETED" if success else "FAILED",
        success=success,
        started_at=datetime(2026, 6, 3, 10, 0, 0, tzinfo=UTC) if success else None,
        finished_at=datetime(2026, 6, 3, 10, 0, 3, tzinfo=UTC) if success else None,
        task_results=tasks,
    )


def test_render_roundtrips_through_parse() -> None:
    response = _response()
    markdown = render_flow_markdown(response)
    assert "```json" in markdown
    parsed = parse_flow_artifact_json(markdown)
    assert parsed == response


def test_render_failure_and_success_badges() -> None:
    assert "❌" in render_flow_markdown(_response(success=False))
    assert "✅" in render_flow_markdown(_response(success=True))


def test_render_tolerates_pending_and_missing_timestamps() -> None:
    pending = FlowResponse(
        incoming=_message(), flow_name="netex-validate", status="SCHEDULED"
    )
    markdown = render_flow_markdown(pending)  # must not raise
    assert "⏳" in markdown
    assert "—" in markdown  # missing timestamps render as a dash
    assert parse_flow_artifact_json(markdown) == pending


def test_parse_raises_without_json_block() -> None:
    with pytest.raises(ValueError, match="no fenced JSON block"):
        parse_flow_artifact_json("# just a heading, no code block")


def test_flow_artifact_key_slug() -> None:
    assert _flow_artifact_key("netex_validate") == "netex-validate-response"
    assert _flow_artifact_key("Ingest Flow!") == "ingest-flow-response"


def test_publish_calls_create_markdown_artifact(monkeypatch) -> None:
    captured: dict = {}

    def fake_create(*, key, markdown, description):
        captured["key"] = key
        captured["markdown"] = markdown
        captured["description"] = description
        return "artifact-id"

    monkeypatch.setattr("prefect.artifacts.create_markdown_artifact", fake_create)

    response = _response()
    publish_flow_artifact(response)

    assert captured["key"] == "netex-validate-response"
    assert parse_flow_artifact_json(captured["markdown"]) == response
    assert "netex-validate" in captured["description"]
    assert "sender/document" in captured["description"]


def test_to_terminal_state_success_returns_response() -> None:
    response = _response(success=True)
    assert to_terminal_state(response) is response


def test_to_terminal_state_failure_returns_failed_with_first_error() -> None:
    state = to_terminal_state(_response(success=False))
    assert isinstance(state, State)
    assert state.is_failed()
    assert state.message == "bad ref"


def test_to_terminal_state_failure_generic_message_when_no_task_error() -> None:
    response = _response(success=False, with_tasks=False)
    state = to_terminal_state(response)
    assert isinstance(state, State)
    assert state.is_failed()
    assert state.message == "netex-validate failed"
