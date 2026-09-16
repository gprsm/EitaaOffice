"""Tests for BaleProviderProcessWorker IPC operations."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker
from eitaa_bridge.errors import WorkerIpcError
from eitaa_bridge.infrastructure.worker_ipc import IpcEnvelope


def _envelope(method: str, payload: dict, account_id: str, provider: str = "bale") -> IpcEnvelope:
    return IpcEnvelope(
        kind="request",
        correlation_id=str(uuid4()),
        messenger_account_id=account_id,
        provider=provider,
        method=method,
        deadline_unix_ms=int(time.time() * 1000) + 60_000,
        nonce=uuid4().hex,
        payload=payload,
        key_id="synthetic",
        signature="0" * 64,
    )


def test_bale_worker_hello_and_health() -> None:
    account_id = str(uuid4())
    worker = BaleProviderProcessWorker(account_id)

    # worker.hello
    hello_req = _envelope("worker.hello", {}, account_id)
    res = worker.dispatch(hello_req)
    assert res.payload["status"] == "ready"
    assert res.payload["provider"] == "bale"
    assert res.payload["messenger_account_id"] == account_id
    assert "bale.send_text" in res.payload["capabilities"]

    # worker.health
    health_req = _envelope("worker.health", {}, account_id)
    h_res = worker.dispatch(health_req)
    assert h_res.payload["status"] == "ready"
    assert h_res.payload["request_count"] == 2


def test_bale_worker_scope_mismatch() -> None:
    account_id = str(uuid4())
    wrong_id = str(uuid4())
    worker = BaleProviderProcessWorker(account_id)

    req = _envelope("worker.hello", {}, wrong_id)
    with pytest.raises(WorkerIpcError) as exc_info:
        worker.dispatch(req)
    assert exc_info.value.code == "ipc_worker_scope_mismatch"


def test_bale_worker_operational_dispatch() -> None:
    account_id = str(uuid4())
    mock_api = MagicMock()
    mock_api.send_text = AsyncMock(return_value={"message_id": 999111, "date": 1726000000})
    mock_api.list_dialogs = AsyncMock(return_value=[{"title": "گفتگو ۱"}])
    mock_api.list_contacts = AsyncMock(return_value=[{"name": "محسن"}])

    worker = BaleProviderProcessWorker(account_id, api=mock_api)

    send_req = _envelope("bale.send_text", {"user_id": 1001, "text": "سلام بله"}, account_id)
    res = worker.dispatch(send_req)
    assert res.payload["ok"] is True
    assert res.payload["result"]["message_id"] == 999111
    mock_api.send_text.assert_awaited_once_with(user_id=1001, text="سلام بله")

    dialogs_req = _envelope("bale.list_dialogs", {"limit": 10}, account_id)
    d_res = worker.dispatch(dialogs_req)
    assert d_res.payload["ok"] is True
    assert len(d_res.payload["result"]) == 1

    contacts_req = _envelope("bale.list_contacts", {}, account_id)
    c_res = worker.dispatch(contacts_req)
    assert c_res.payload["ok"] is True
    assert c_res.payload["result"][0]["name"] == "محسن"


def test_bale_worker_stop() -> None:
    account_id = str(uuid4())
    mock_api = MagicMock()
    mock_api.close = AsyncMock()

    worker = BaleProviderProcessWorker(account_id, api=mock_api)
    stop_req = _envelope("worker.stop", {}, account_id)
    res = worker.dispatch(stop_req)
    assert res.payload["status"] == "stopped"
    assert res.stop_requested is True
    mock_api.close.assert_awaited_once()
