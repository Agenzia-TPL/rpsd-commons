# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""Tests for the FlowResponse / TaskResult models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rpsd_flow.responses import UNKNOWN_STATUS, FlowResponse, TaskResult
from rpsd_transport.models import MessageMetadata, TransportMessage


def _message(who: str = "sender", what: str = "document") -> TransportMessage:
    """Build a minimal valid TransportMessage for tests."""
    return TransportMessage(metadata=MessageMetadata(who=who, what=what))


def test_taskresult_roundtrip_minimal() -> None:
    tr = TaskResult(task_name="validate", success=True)
    assert tr.error is None
    assert tr.duration is None
    restored = TaskResult.model_validate_json(tr.model_dump_json())
    assert restored == tr


def test_taskresult_roundtrip_full() -> None:
    tr = TaskResult(
        task_name="validate",
        success=False,
        error="boom",
        duration=1.25,
    )
    restored = TaskResult.model_validate_json(tr.model_dump_json())
    assert restored == tr


def test_flowresponse_full_roundtrip() -> None:
    run_id = uuid4()
    started = datetime(2026, 6, 3, 10, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 6, 3, 10, 0, 5, tzinfo=UTC)
    response = FlowResponse(
        incoming=_message(),
        flow_name="netex-validate",
        flow_run_id=run_id,
        status="COMPLETED",
        success=True,
        started_at=started,
        finished_at=finished,
        task_results=[
            TaskResult(task_name="syntax", success=True, duration=0.5),
            TaskResult(task_name="semantic", success=True, duration=1.0),
        ],
    )

    restored = FlowResponse.model_validate_json(response.model_dump_json())
    assert restored == response
    assert restored.flow_run_id == run_id
    assert len(restored.task_results) == 2


def test_flowresponse_pending_minimal() -> None:
    response = FlowResponse(
        incoming=_message(),
        flow_name="netex-validate",
        status="SCHEDULED",
    )
    assert response.success is None
    assert response.started_at is None
    assert response.finished_at is None
    assert response.task_results == []

    restored = FlowResponse.model_validate_json(response.model_dump_json())
    assert restored == response


def test_flowresponse_status_defaults_to_unknown() -> None:
    response = FlowResponse(incoming=_message(), flow_name="f")
    assert response.status == UNKNOWN_STATUS


def test_flowresponse_requires_incoming() -> None:
    with pytest.raises(ValidationError):
        FlowResponse(flow_name="netex-validate")


def test_flowresponse_requires_flow_name() -> None:
    with pytest.raises(ValidationError):
        FlowResponse(incoming=_message())


def _parent() -> FlowResponse:
    """A parent response with one of its own task rows already recorded."""
    return FlowResponse(
        incoming=_message(),
        flow_name="ingest-flow",
        status="COMPLETED",
        task_results=[TaskResult(task_name="save-file", success=True, duration=0.1)],
    )


def _child(
    *,
    success: bool,
    flow_name: str = "validate-flow",
    task_results: list[TaskResult] | None = None,
) -> FlowResponse:
    started = datetime(2026, 6, 3, 10, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 6, 3, 10, 0, 3, tzinfo=UTC)
    return FlowResponse(
        incoming=_message(),
        flow_name=flow_name,
        status="COMPLETED" if success else "FAILED",
        success=success,
        started_at=started,
        finished_at=finished,
        task_results=task_results or [],
    )


def test_add_subflow_summary_carries_child_success_and_duration() -> None:
    parent = _parent()
    child = _child(
        success=True,
        task_results=[TaskResult(task_name="syntax", success=True, duration=1.0)],
    )

    returned = parent.add_subflow(child)

    assert returned is parent
    assert [tr.task_name for tr in parent.task_results] == [
        "save-file",
        "validate-flow",
    ]
    summary = parent.task_results[-1]
    assert summary.success is True
    assert summary.error is None
    assert summary.duration == 3.0


def test_add_subflow_summary_carries_first_child_error() -> None:
    child = _child(
        success=False,
        task_results=[
            TaskResult(task_name="syntax", success=True, duration=0.5),
            TaskResult(task_name="semantic", success=False, error="bad ref"),
            TaskResult(task_name="extra", success=False, error="later"),
        ],
    )

    parent = _parent().add_subflow(child)

    summary = parent.task_results[-1]
    assert summary.task_name == "validate-flow"
    assert summary.success is False
    assert summary.error == "bad ref"


def test_add_subflow_summary_failed_child_without_task_detail() -> None:
    # Robustness guarantee: a flow-level failure with no per-task detail still
    # appends a success=False row, so the failure cannot silently vanish.
    parent = _parent().add_subflow(_child(success=False, task_results=[]))

    summary = parent.task_results[-1]
    assert summary.task_name == "validate-flow"
    assert summary.success is False
    assert summary.error is None


def test_add_subflow_detail_prefixes_every_row_in_order() -> None:
    child = _child(
        success=False,
        task_results=[
            TaskResult(task_name="syntax", success=True, duration=0.5),
            TaskResult(task_name="semantic", success=False, error="bad ref"),
        ],
    )

    parent = _parent().add_subflow(child, detail=True)

    assert [tr.task_name for tr in parent.task_results] == [
        "save-file",
        "validate-flow/syntax",
        "validate-flow/semantic",
    ]
    semantic = parent.task_results[-1]
    assert semantic.success is False
    assert semantic.error == "bad ref"
    assert semantic.duration is None


def test_add_subflow_custom_prefix() -> None:
    child = _child(
        success=True,
        task_results=[TaskResult(task_name="syntax", success=True)],
    )

    summary_parent = _parent().add_subflow(child, prefix="val-2")
    assert summary_parent.task_results[-1].task_name == "val-2"

    detail_parent = _parent().add_subflow(child, detail=True, prefix="val-2")
    assert detail_parent.task_results[-1].task_name == "val-2/syntax"


def test_add_subflow_does_not_touch_parent_success() -> None:
    parent = _parent()
    assert parent.success is None

    parent.add_subflow(_child(success=False))

    assert parent.success is None
    # The parent owns its success; the folded row makes all(...) reflect it.
    assert all(tr.success for tr in parent.task_results) is False
