# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""Tests for run_flow / run_flow_async return-shape behavior.

Prefect's ``run_deployment``, the task-run query, and the artifact read are
mocked so the homogeneous ``FlowResponse`` contract can be exercised without a
server. The rich, flow-authored response is recovered from the run's published
artifact (``_read_response_from_artifact_async``); when absent, the response is
synthesised from a task-run query.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from prefect.client.schemas.objects import StateType

from rpsd_flow.execute import (
    get_flow_response,
    get_flow_response_async,
    run_flow,
    run_flow_async,
)
from rpsd_flow.responses import FlowResponse, TaskResult
from rpsd_transport.models import MessageMetadata, TransportMessage


@pytest.fixture
def anyio_backend():
    """Use asyncio backend only (trio not installed)."""
    return "asyncio"


def _message(who: str = "sender", what: str = "document") -> TransportMessage:
    return TransportMessage(metadata=MessageMetadata(who=who, what=what))


class _FakeState:
    """Stands in for a Prefect ``State``.

    ``type`` is a real ``StateType`` enum so that status normalisation
    (``.value`` vs ``str(enum)``) is exercised faithfully.
    """

    _TERMINAL = {
        StateType.COMPLETED,
        StateType.FAILED,
        StateType.CRASHED,
        StateType.CANCELLED,
    }

    def __init__(self, type_name: str, *, message: str | None = None) -> None:
        self.type = StateType[type_name]
        self.message = message

    def is_completed(self) -> bool:
        return self.type == StateType.COMPLETED

    def is_final(self) -> bool:
        return self.type in self._TERMINAL


class _FakeFlowRun:
    def __init__(
        self,
        state: _FakeState | None,
        *,
        id=None,
        start_time=None,
        end_time=None,
        name: str = "run-xyz",
        flow_id=None,
        parameters=None,
    ) -> None:
        self.id = id or uuid4()
        self.name = name
        self.state = state
        self.start_time = start_time
        self.end_time = end_time
        self.flow_id = flow_id or uuid4()
        self.parameters = parameters if parameters is not None else {}


def _install(monkeypatch, flow_run, query_results, artifact, calls, capture=None):
    """Patch run_deployment (sync + .aio), the task-run query, and the read."""

    def fake_run_deployment(**kwargs):
        if capture is not None:
            capture.update(kwargs)
        return flow_run

    async def fake_aio(**kwargs):
        if capture is not None:
            capture.update(kwargs)
        return flow_run

    fake_run_deployment.aio = fake_aio
    monkeypatch.setattr("prefect.deployments.run_deployment", fake_run_deployment)

    async def fake_query(_flow_run):
        calls["query"] = True
        return list(query_results or [])

    monkeypatch.setattr("rpsd_flow.execute._query_task_results", fake_query)

    async def fake_artifact(_run_id, _flow_name):
        calls["artifact"] = True
        return artifact

    monkeypatch.setattr(
        "rpsd_flow.execute._read_response_from_artifact_async", fake_artifact
    )


_QUERY_RESULTS = [
    TaskResult(task_name="syntax", success=True, duration=0.5),
    TaskResult(task_name="semantic", success=False, error="bad"),
]

_STARTED = datetime(2026, 6, 3, 10, 0, 0, tzinfo=UTC)
_FINISHED = datetime(2026, 6, 3, 10, 0, 5, tzinfo=UTC)


def _verbatim_response(*, success: bool = True) -> FlowResponse:
    return FlowResponse(
        incoming=_message(),
        flow_name="verbatim-flow",
        status="COMPLETED" if success else "FAILED",
        success=success,
        task_results=[
            TaskResult(task_name="a", success=True),
            TaskResult(task_name="b", success=success, error=None if success else "x"),
        ],
    )


def _check_scheduled(response, flow_run, calls) -> None:
    assert response.status == "SCHEDULED"
    assert response.success is None
    assert response.started_at is None
    assert response.finished_at is None
    assert response.task_results == []
    assert response.flow_name == "my-flow"
    assert response.flow_run_id == flow_run.id
    assert "artifact" not in calls
    assert "query" not in calls


def _check_verbatim(response, flow_run, calls) -> None:
    # The flow's own artifact response is returned verbatim (not synthesised).
    assert response.flow_name == "verbatim-flow"
    assert response.success is True
    assert len(response.task_results) == 2
    assert calls.get("artifact") is True
    assert "query" not in calls


def _check_failed_verbatim(response, flow_run, calls) -> None:
    # A FAILED run still returns the curated response from its artifact.
    assert response.flow_name == "verbatim-flow"
    assert response.success is False
    assert response.task_results[-1].error == "x"
    assert calls.get("artifact") is True
    assert "query" not in calls


def _check_completed_no_artifact(response, flow_run, calls) -> None:
    assert response.success is True
    assert response.status == "COMPLETED"
    assert response.started_at == _STARTED
    assert response.finished_at == _FINISHED
    assert response.task_results == _QUERY_RESULTS
    assert calls.get("artifact") is True
    assert calls.get("query") is True


def _check_failed_no_artifact(response, flow_run, calls) -> None:
    assert response.success is False
    assert response.status == "FAILED"
    assert response.task_results == _QUERY_RESULTS
    assert calls.get("artifact") is True
    assert calls.get("query") is True


def _check_none_flow_run(response, flow_run, calls) -> None:
    assert response.status == "UNKNOWN"
    assert response.success is None
    assert response.flow_run_id is None
    assert response.task_results == []
    assert "artifact" not in calls
    assert "query" not in calls


# name, flow_run factory, query_results, artifact, checker
SCENARIOS = [
    (
        "fire_and_forget_scheduled",
        lambda: _FakeFlowRun(_FakeState("SCHEDULED")),
        None,
        None,
        _check_scheduled,
    ),
    (
        "completed_verbatim_artifact",
        lambda: _FakeFlowRun(_FakeState("COMPLETED")),
        None,
        _verbatim_response(),
        _check_verbatim,
    ),
    (
        "failed_verbatim_artifact",
        lambda: _FakeFlowRun(
            _FakeState("FAILED", message="boom"),
            start_time=_STARTED,
            end_time=_FINISHED,
        ),
        None,
        _verbatim_response(success=False),
        _check_failed_verbatim,
    ),
    (
        "completed_no_artifact",
        lambda: _FakeFlowRun(
            _FakeState("COMPLETED"),
            start_time=_STARTED,
            end_time=_FINISHED,
        ),
        _QUERY_RESULTS,
        None,
        _check_completed_no_artifact,
    ),
    (
        "failed_no_artifact",
        lambda: _FakeFlowRun(
            _FakeState("FAILED", message="boom"),
            start_time=_STARTED,
            end_time=_FINISHED,
        ),
        _QUERY_RESULTS,
        None,
        _check_failed_no_artifact,
    ),
    (
        "none_flow_run",
        lambda: None,
        None,
        None,
        _check_none_flow_run,
    ),
]

_IDS = [name for name, *_ in SCENARIOS]


@pytest.mark.parametrize(
    "name,factory,query_results,artifact,check", SCENARIOS, ids=_IDS
)
def test_run_flow_sync(name, factory, query_results, artifact, check, monkeypatch):
    flow_run = factory()
    calls: dict[str, bool] = {}
    _install(monkeypatch, flow_run, query_results, artifact, calls)

    response = run_flow("my-flow/my-dep", _message())

    assert isinstance(response, FlowResponse)
    check(response, flow_run, calls)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name,factory,query_results,artifact,check", SCENARIOS, ids=_IDS
)
async def test_run_flow_async(
    name, factory, query_results, artifact, check, monkeypatch
):
    flow_run = factory()
    calls: dict[str, bool] = {}
    _install(monkeypatch, flow_run, query_results, artifact, calls)

    response = await run_flow_async("my-flow/my-dep", _message())

    assert isinstance(response, FlowResponse)
    check(response, flow_run, calls)


def test_run_flow_forwards_parameters(monkeypatch):
    flow_run = _FakeFlowRun(_FakeState("SCHEDULED"))
    calls: dict[str, bool] = {}
    capture: dict[str, object] = {}
    _install(monkeypatch, flow_run, None, None, calls, capture=capture)

    message = _message()
    run_flow("my-flow/my-dep", message, timeout=12.5)

    assert capture["name"] == "my-flow/my-dep"
    assert capture["parameters"] == {"message": message.model_dump()}
    assert capture["timeout"] == 12.5


@pytest.mark.anyio
async def test_run_flow_async_forwards_parameters(monkeypatch):
    flow_run = _FakeFlowRun(_FakeState("SCHEDULED"))
    calls: dict[str, bool] = {}
    capture: dict[str, object] = {}
    _install(monkeypatch, flow_run, None, None, calls, capture=capture)

    message = _message()
    await run_flow_async("my-flow/my-dep", message, timeout=12.5)

    assert capture["name"] == "my-flow/my-dep"
    assert capture["parameters"] == {"message": message.model_dump()}
    assert capture["timeout"] == 12.5


# --- get_flow_response / get_flow_response_async ---


class _FakeFlow:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeClient:
    def __init__(self, flow_run, flow_name: str) -> None:
        self._flow_run = flow_run
        self._flow_name = flow_name
        self.read_flow_run_id = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read_flow_run(self, flow_run_id):
        self.read_flow_run_id = flow_run_id
        return self._flow_run

    async def read_flow(self, flow_id):
        return _FakeFlow(self._flow_name)


def _install_get_client(
    monkeypatch, flow_run, query_results, artifact, calls, flow_name
):
    monkeypatch.setattr(
        "prefect.client.orchestration.get_client",
        lambda: _FakeClient(flow_run, flow_name),
    )

    async def fake_query(_flow_run):
        calls["query"] = True
        return list(query_results or [])

    monkeypatch.setattr("rpsd_flow.execute._query_task_results", fake_query)

    async def fake_artifact(_run_id, _flow_name):
        calls["artifact"] = True
        return artifact

    monkeypatch.setattr(
        "rpsd_flow.execute._read_response_from_artifact_async", fake_artifact
    )


@pytest.mark.anyio
async def test_get_flow_response_pending(monkeypatch):
    msg = _message()
    flow_run = _FakeFlowRun(
        _FakeState("SCHEDULED"), parameters={"message": msg.model_dump()}
    )
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, None, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id)

    assert resp.status == "SCHEDULED"
    assert resp.success is None
    assert resp.flow_name == "ingest-flow"
    assert resp.flow_run_id == flow_run.id
    assert resp.incoming == msg  # reconstructed from parameters
    assert resp.task_results == []
    assert "artifact" not in calls
    assert "query" not in calls


@pytest.mark.anyio
async def test_get_flow_response_verbatim_from_artifact(monkeypatch):
    verbatim = _verbatim_response()
    flow_run = _FakeFlowRun(_FakeState("COMPLETED"))
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, verbatim, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id)

    assert resp is verbatim  # returned untouched, carries its own incoming
    assert "query" not in calls


@pytest.mark.anyio
async def test_get_flow_response_failed_verbatim_from_artifact(monkeypatch):
    # A FAILED run with no stored 'message' parameter still resolves, because
    # the artifact response carries its own incoming.
    verbatim = _verbatim_response(success=False)
    flow_run = _FakeFlowRun(_FakeState("FAILED", message="boom"), parameters={})
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, verbatim, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id)

    assert resp is verbatim
    assert resp.success is False
    assert "query" not in calls


@pytest.mark.anyio
async def test_get_flow_response_synthesized_with_task_query(monkeypatch):
    msg = _message()
    flow_run = _FakeFlowRun(
        _FakeState("FAILED", message="boom"),
        start_time=_STARTED,
        end_time=_FINISHED,
        parameters={"message": msg.model_dump()},
    )
    calls: dict[str, bool] = {}
    _install_get_client(
        monkeypatch, flow_run, _QUERY_RESULTS, None, calls, "ingest-flow"
    )

    resp = await get_flow_response_async(flow_run.id)

    assert resp.status == "FAILED"
    assert resp.success is False
    assert resp.task_results == _QUERY_RESULTS
    assert resp.incoming == msg
    assert calls.get("query") is True


@pytest.mark.anyio
async def test_get_flow_response_incoming_override(monkeypatch):
    override = _message(who="bob", what="audit")
    flow_run = _FakeFlowRun(_FakeState("SCHEDULED"), parameters={})
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, None, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id, incoming=override)

    assert resp.incoming == override


@pytest.mark.anyio
async def test_get_flow_response_no_message_raises(monkeypatch):
    flow_run = _FakeFlowRun(_FakeState("SCHEDULED"), parameters={})
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, None, calls, "ingest-flow")

    with pytest.raises(ValueError, match="no 'message' parameter"):
        await get_flow_response_async(flow_run.id)


def test_get_flow_response_sync(monkeypatch):
    msg = _message()
    flow_run = _FakeFlowRun(
        _FakeState("COMPLETED"),
        start_time=_STARTED,
        end_time=_FINISHED,
        parameters={"message": msg.model_dump()},
    )
    calls: dict[str, bool] = {}
    _install_get_client(
        monkeypatch, flow_run, _QUERY_RESULTS, None, calls, "ingest-flow"
    )

    resp = get_flow_response(str(flow_run.id))  # accepts str id

    assert isinstance(resp, FlowResponse)
    assert resp.success is True
    assert resp.status == "COMPLETED"
    assert resp.task_results == _QUERY_RESULTS
    assert resp.incoming == msg
