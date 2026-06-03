# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""Tests for run_flow / run_flow_async return-shape behavior.

Prefect's ``run_deployment`` and the task-run query are mocked so the
homogeneous ``FlowResponse`` contract can be exercised without a server.
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

_NO_RESULT = object()


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

    def __init__(
        self,
        type_name: str,
        *,
        result: object = _NO_RESULT,
        raises: bool = False,
        message: str | None = None,
    ) -> None:
        self.type = StateType[type_name]
        self.message = message
        self._result = result
        self._raises = raises
        self.result_called = False
        self.aresult_called = False

    def is_completed(self) -> bool:
        return self.type == StateType.COMPLETED

    def is_final(self) -> bool:
        return self.type in self._TERMINAL

    def result(self, raise_on_failure: bool = False, _sync: bool | None = None):
        self.result_called = True
        if self._raises:
            raise RuntimeError("result not persisted")
        return self._result

    async def aresult(self, raise_on_failure: bool = False):
        self.aresult_called = True
        if self._raises:
            raise RuntimeError("result not persisted")
        return self._result


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


def _install(monkeypatch, flow_run, query_results, calls, capture=None):
    """Patch run_deployment (sync + .aio) and the task-run query."""

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


_QUERY_RESULTS = [
    TaskResult(task_name="syntax", success=True, duration=0.5),
    TaskResult(task_name="semantic", success=False, error="bad"),
]

_STARTED = datetime(2026, 6, 3, 10, 0, 0, tzinfo=UTC)
_FINISHED = datetime(2026, 6, 3, 10, 0, 5, tzinfo=UTC)


def _verbatim_response() -> FlowResponse:
    return FlowResponse(
        incoming=_message(),
        flow_name="verbatim-flow",
        status="COMPLETED",
        success=True,
        task_results=[
            TaskResult(task_name="a", success=True),
            TaskResult(task_name="b", success=True),
        ],
    )


def _check_scheduled(response, flow_run, state, calls) -> None:
    assert response.status == "SCHEDULED"
    assert response.success is None
    assert response.started_at is None
    assert response.finished_at is None
    assert response.task_results == []
    assert response.flow_name == "my-flow"
    assert response.flow_run_id == flow_run.id
    assert not state.result_called and not state.aresult_called
    assert "query" not in calls


def _check_verbatim(response, flow_run, state, calls) -> None:
    assert response.flow_name == "verbatim-flow"  # not synthesized "my-flow"
    assert response.success is True
    assert len(response.task_results) == 2
    assert state.result_called or state.aresult_called
    assert "query" not in calls


def _check_completed_non_flowresponse(response, flow_run, state, calls) -> None:
    assert response.success is True
    assert response.status == "COMPLETED"
    assert response.started_at == _STARTED
    assert response.finished_at == _FINISHED
    assert response.task_results == _QUERY_RESULTS
    assert state.result_called or state.aresult_called
    assert calls.get("query") is True


def _check_failed(response, flow_run, state, calls) -> None:
    assert response.success is False
    assert response.status == "FAILED"
    assert response.task_results == _QUERY_RESULTS
    assert not state.result_called and not state.aresult_called
    assert calls.get("query") is True


def _check_result_raises(response, flow_run, state, calls) -> None:
    # Result fetch raised but was caught: still a FlowResponse, falls back
    # to the task-run query.
    assert response.success is True
    assert response.status == "COMPLETED"
    assert response.task_results == _QUERY_RESULTS
    assert state.result_called or state.aresult_called
    assert calls.get("query") is True


def _check_none_flow_run(response, flow_run, state, calls) -> None:
    assert response.status == "UNKNOWN"
    assert response.success is None
    assert response.flow_run_id is None
    assert response.task_results == []
    assert "query" not in calls


# name, flow_run factory, query_results, checker
SCENARIOS = [
    (
        "fire_and_forget_scheduled",
        lambda: _FakeFlowRun(_FakeState("SCHEDULED")),
        None,
        _check_scheduled,
    ),
    (
        "completed_verbatim",
        lambda: _FakeFlowRun(_FakeState("COMPLETED", result=_verbatim_response())),
        None,
        _check_verbatim,
    ),
    (
        "completed_non_flowresponse",
        lambda: _FakeFlowRun(
            _FakeState("COMPLETED", result="hello"),
            start_time=_STARTED,
            end_time=_FINISHED,
        ),
        _QUERY_RESULTS,
        _check_completed_non_flowresponse,
    ),
    (
        "failed",
        lambda: _FakeFlowRun(
            _FakeState("FAILED", message="boom"),
            start_time=_STARTED,
            end_time=_FINISHED,
        ),
        _QUERY_RESULTS,
        _check_failed,
    ),
    (
        "completed_result_raises",
        lambda: _FakeFlowRun(
            _FakeState("COMPLETED", raises=True),
            start_time=_STARTED,
            end_time=_FINISHED,
        ),
        _QUERY_RESULTS,
        _check_result_raises,
    ),
    (
        "none_flow_run",
        lambda: None,
        None,
        _check_none_flow_run,
    ),
]

_IDS = [name for name, *_ in SCENARIOS]


@pytest.mark.parametrize("name,factory,query_results,check", SCENARIOS, ids=_IDS)
def test_run_flow_sync(name, factory, query_results, check, monkeypatch):
    flow_run = factory()
    state = flow_run.state if flow_run is not None else None
    calls: dict[str, bool] = {}
    _install(monkeypatch, flow_run, query_results, calls)

    response = run_flow("my-flow/my-dep", _message())

    assert isinstance(response, FlowResponse)
    check(response, flow_run, state, calls)


@pytest.mark.anyio
@pytest.mark.parametrize("name,factory,query_results,check", SCENARIOS, ids=_IDS)
async def test_run_flow_async(name, factory, query_results, check, monkeypatch):
    flow_run = factory()
    state = flow_run.state if flow_run is not None else None
    calls: dict[str, bool] = {}
    _install(monkeypatch, flow_run, query_results, calls)

    response = await run_flow_async("my-flow/my-dep", _message())

    assert isinstance(response, FlowResponse)
    check(response, flow_run, state, calls)


def test_run_flow_forwards_parameters(monkeypatch):
    flow_run = _FakeFlowRun(_FakeState("SCHEDULED"))
    calls: dict[str, bool] = {}
    capture: dict[str, object] = {}
    _install(monkeypatch, flow_run, None, calls, capture=capture)

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
    _install(monkeypatch, flow_run, None, calls, capture=capture)

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


def _install_get_client(monkeypatch, flow_run, query_results, calls, flow_name):
    monkeypatch.setattr(
        "prefect.client.orchestration.get_client",
        lambda: _FakeClient(flow_run, flow_name),
    )

    async def fake_query(_flow_run):
        calls["query"] = True
        return list(query_results or [])

    monkeypatch.setattr("rpsd_flow.execute._query_task_results", fake_query)


@pytest.mark.anyio
async def test_get_flow_response_pending(monkeypatch):
    msg = _message()
    flow_run = _FakeFlowRun(
        _FakeState("SCHEDULED"), parameters={"message": msg.model_dump()}
    )
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id)

    assert resp.status == "SCHEDULED"
    assert resp.success is None
    assert resp.flow_name == "ingest-flow"
    assert resp.flow_run_id == flow_run.id
    assert resp.incoming == msg  # reconstructed from parameters
    assert resp.task_results == []
    assert "query" not in calls


@pytest.mark.anyio
async def test_get_flow_response_verbatim(monkeypatch):
    verbatim = _verbatim_response()
    flow_run = _FakeFlowRun(_FakeState("COMPLETED", result=verbatim))
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id)

    assert resp is verbatim  # returned untouched
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
    _install_get_client(monkeypatch, flow_run, _QUERY_RESULTS, calls, "ingest-flow")

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
    _install_get_client(monkeypatch, flow_run, None, calls, "ingest-flow")

    resp = await get_flow_response_async(flow_run.id, incoming=override)

    assert resp.incoming == override


@pytest.mark.anyio
async def test_get_flow_response_no_message_raises(monkeypatch):
    flow_run = _FakeFlowRun(_FakeState("SCHEDULED"), parameters={})
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, None, calls, "ingest-flow")

    with pytest.raises(ValueError, match="no 'message' parameter"):
        await get_flow_response_async(flow_run.id)


def test_get_flow_response_sync(monkeypatch):
    msg = _message()
    flow_run = _FakeFlowRun(
        _FakeState("COMPLETED", result="not-a-flowresponse"),
        start_time=_STARTED,
        end_time=_FINISHED,
        parameters={"message": msg.model_dump()},
    )
    calls: dict[str, bool] = {}
    _install_get_client(monkeypatch, flow_run, _QUERY_RESULTS, calls, "ingest-flow")

    resp = get_flow_response(str(flow_run.id))  # accepts str id

    assert isinstance(resp, FlowResponse)
    assert resp.success is True
    assert resp.status == "COMPLETED"
    assert resp.task_results == _QUERY_RESULTS
    assert resp.incoming == msg
