# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
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
        outgoing=_message(what="result"),
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
    assert restored.outgoing is not None
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
    assert response.outgoing is None
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
