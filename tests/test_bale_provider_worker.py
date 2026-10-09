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


def test_bale_worker_hello_and_health(tmp_path) -> None:
    account_id = str(uuid4())
    worker = BaleProviderProcessWorker(account_id, tmp_path / "bridge.json")

    # worker.hello
    hello_req = _envelope("worker.hello", {}, account_id)
    res = worker.dispatch(hello_req)
    assert res.payload["status"] == "bootstrap_ready"
    assert res.payload["provider"] == "bale"
    assert res.payload["messenger_account_id"] == account_id
    worker.close()


def test_bale_worker_scope_mismatch(tmp_path) -> None:
    account_id = str(uuid4())
    wrong_id = str(uuid4())
    worker = BaleProviderProcessWorker(account_id, tmp_path / "bridge.json")

    req = _envelope("worker.hello", {}, wrong_id)
    with pytest.raises(WorkerIpcError) as exc_info:
        worker.dispatch(req)
    assert exc_info.value.code == "ipc_worker_scope_mismatch"
    worker.close()


def test_bale_worker_operational_dispatch(tmp_path) -> None:
    account_id = str(uuid4())
    instance_id = str(uuid4())

    mock_owner = MagicMock()
    mock_owner.send_text = AsyncMock(return_value={"sent": True, "message_id": 999111})
    mock_owner.list_dialogs = AsyncMock(return_value=[{"title": "گفتگو ۱", "peer": {"id": 1, "type": 1}}])
    mock_owner.list_contacts = AsyncMock(return_value=[{"name": "محسن", "peer": {"id": 1001, "type": 1}}])
    mock_owner.close = AsyncMock()

    worker = BaleProviderProcessWorker(
        account_id,
        tmp_path / "bridge.json",
        owner_factory=lambda root, acc_id: mock_owner,
    )

    worker.dispatch(_envelope("bale.runtime.start", {
        "runtime_record": {
            "provider": "bale", "messenger_account_id": account_id,
            "lifecycle_state": "active", "desired_worker_state": "running",
            "storage_revision": 1, "session_generation": 1,
        }, "worker_instance_id": instance_id, "worker_generation": 1,
    }, account_id))

    worker._authenticated = True

    send_req = _envelope("bale.provider.messages.send_text", {
        "user_id": 1001,
        "peer_type": 1,
        "text": "سلام بله",
        "worker_instance_id": instance_id,
        "worker_generation": 1,
        "session_generation": 1,
    }, account_id)
    res = worker.dispatch(send_req)
    assert res.payload["sent"] is True
    mock_owner.send_text.assert_awaited_once()

    dialogs_req = _envelope("bale.provider.dialogs.query", {
        "limit": 10,
        "offset_date": None,
        "worker_instance_id": instance_id,
        "worker_generation": 1,
        "session_generation": 1,
    }, account_id)
    d_res = worker.dispatch(dialogs_req)
    assert len(d_res.payload["dialogs"]) == 1

    contacts_req = _envelope("bale.provider.contacts.query", {
        "limit": 10,
        "worker_instance_id": instance_id,
        "worker_generation": 1,
        "session_generation": 1,
    }, account_id)
    c_res = worker.dispatch(contacts_req)
    assert len(c_res.payload["contacts"]) == 1
    worker.close()


def test_bale_worker_stop(tmp_path) -> None:
    account_id = str(uuid4())
    instance_id = str(uuid4())
    mock_owner = MagicMock()
    mock_owner.close = AsyncMock()

    worker = BaleProviderProcessWorker(
        account_id,
        tmp_path / "bridge.json",
        owner_factory=lambda root, acc_id: mock_owner,
    )
    worker.dispatch(_envelope("bale.runtime.start", {
        "runtime_record": {
            "provider": "bale", "messenger_account_id": account_id,
            "lifecycle_state": "active", "desired_worker_state": "running",
            "storage_revision": 1, "session_generation": 1,
        }, "worker_instance_id": instance_id, "worker_generation": 1,
    }, account_id))

    stop_req = _envelope("worker.stop", {
        "worker_instance_id": instance_id,
        "worker_generation": 1,
        "session_generation": 1,
    }, account_id)
    res = worker.dispatch(stop_req)
    assert res.payload["status"] == "stopped"
    assert res.stop_requested is True
    mock_owner.close.assert_awaited_once()
