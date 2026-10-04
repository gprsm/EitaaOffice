"""Tests for single-process reporting store ownership lease."""

from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from eitaa_bridge.reporting.ownership import (
    ReportingStoreOwnershipError,
    StoreOwnershipLease,
)


def test_second_acquire_rejected(tmp_path: Path) -> None:
    # Second lease acquire on same db and runtime dir must be rejected with error details containing pid
    db_path = tmp_path / "reporting.db"
    runtime_dir = tmp_path / "runtime"
    lease1 = StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir)
    lease2 = StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir)

    lease1.acquire()
    try:
        with pytest.raises(ReportingStoreOwnershipError) as exc_info:
            lease2.acquire()

        assert "pid" in exc_info.value.details
    finally:
        lease1.release()


def test_reporting_store_shares_lease_within_process(tmp_path: Path) -> None:
    # Multi-account installations build several BridgeApplicationApi instances
    # against one reporting DB inside a single process; the stores must share
    # one ownership lease (refcounted) instead of fighting over the lock file.
    from eitaa_bridge.reporting.store import ReportingStore

    db_path = tmp_path / "reporting.db"
    runtime_dir = tmp_path / "runtime"
    first = ReportingStore(db_path, acquire_lease=True, runtime_dir=runtime_dir)
    try:
        second = ReportingStore(db_path, acquire_lease=True, runtime_dir=runtime_dir)
        try:
            assert first.ownership_lease is second.ownership_lease
            assert first.ownership_lease.lock_path.is_file()

            second.close()
            # Lease must stay alive while at least one store still holds it.
            assert first.ownership_lease is not None
            assert first.ownership_lease.lock_path.is_file()
        finally:
            second.close()
    finally:
        lease = first.ownership_lease
        first.close()
        assert lease is not None
        assert not lease.lock_path.exists()


def test_stale_takeover(tmp_path: Path) -> None:
    # Stale lease should be taken over and recorded in takeovers list with reason 'stale'
    db_path = tmp_path / "reporting.db"
    runtime_dir = tmp_path / "runtime"
    lease1 = StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir)
    lease2 = StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir)

    lease1.acquire()
    lock_file = lease1.lock_path
    data = json.loads(lock_file.read_text(encoding="utf-8"))
    data["heartbeat_at"] = time.time() - 999.0
    lock_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lease2.acquire()
    try:
        new_data = json.loads(lease2.lock_path.read_text(encoding="utf-8"))
        takeovers = new_data.get("takeovers", [])
        assert len(takeovers) == 1
        assert takeovers[0].get("reason") == "stale"
    finally:
        lease2.release()


def test_release_then_reacquire(tmp_path: Path) -> None:
    # Releasing the first lease allows a second lease to acquire ownership successfully
    db_path = tmp_path / "reporting.db"
    runtime_dir = tmp_path / "runtime"
    lease1 = StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir)
    lease2 = StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir)

    lease1.acquire()
    lease1.release()

    lease2.acquire()
    try:
        assert lease2.lock_path.exists()
        data = json.loads(lease2.lock_path.read_text(encoding="utf-8"))
        assert data.get("holder_id") == lease2.holder_id
    finally:
        lease2.release()


def test_context_manager_releases(tmp_path: Path) -> None:
    # Context manager unlinks the lock file on exit
    db_path = tmp_path / "reporting.db"
    runtime_dir = tmp_path / "runtime"

    with StoreOwnershipLease(db_path=db_path, runtime_dir=runtime_dir) as lease:
        assert lease.lock_path.exists()

    assert not lease.lock_path.exists()


def test_heartbeat_thread(tmp_path: Path) -> None:
    # Heartbeat thread refreshes heartbeat_at across multiple time steps
    db_path = tmp_path / "reporting.db"
    runtime_dir = tmp_path / "runtime"
    lease = StoreOwnershipLease(
        db_path=db_path,
        runtime_dir=runtime_dir,
        ttl_seconds=2.0,
        heartbeat_interval=0.2,
    )
    lease.acquire()
    lease.start_heartbeat()
    try:
        hb_values = []
        for _ in range(3):
            time.sleep(0.3)
            data = json.loads(lease.lock_path.read_text(encoding="utf-8"))
            hb_values.append(data["heartbeat_at"])

        assert len(hb_values) == 3
        assert hb_values[0] < hb_values[1] < hb_values[2]
    finally:
        lease.stop_heartbeat()
        lease.release()
