"""Single-process ownership lease for reporting store (resolves F-104)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any
import uuid


class ReportingStoreOwnershipError(Exception):
    """Raised when store ownership cannot be acquired or has been lost."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details: dict[str, Any] = dict(details) if details else {}


class StoreOwnershipLease:
    """File-backed ownership lease with heartbeat and takeover support."""

    def __init__(
        self,
        db_path: Path,
        runtime_dir: Path | None = None,
        ttl_seconds: float = 30.0,
        heartbeat_interval: float = 10.0,
        owner_label: str = "",
    ) -> None:
        self._db_path = Path(db_path)
        if runtime_dir is None:
            self._runtime_dir = Path(__file__).resolve().parents[2] / "runtime"
        else:
            self._runtime_dir = Path(runtime_dir)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)

        db_hash = hashlib.sha1(str(self._db_path.resolve()).encode()).hexdigest()[:12]
        self._lock_path = self._runtime_dir / f"reporting_store_{db_hash}.lock"

        self._holder_id: str = uuid.uuid4().hex
        self._ttl_seconds: float = float(ttl_seconds)
        self._heartbeat_interval: float = float(heartbeat_interval)
        self._owner_label: str = owner_label

        self._lost: bool = False
        self._stop_event = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()

    @property
    def holder_id(self) -> str:
        """Read-only unique holder ID for this lease instance."""
        return self._holder_id

    @property
    def lock_path(self) -> Path:
        """Read-only path to the lock file."""
        return self._lock_path

    @property
    def lost(self) -> bool:
        """Read-only flag indicating whether ownership was lost."""
        return self._lost

    @property
    def db_path(self) -> Path:
        """Path to the database file being guarded."""
        return self._db_path

    @property
    def runtime_dir(self) -> Path:
        """Directory holding the lock file."""
        return self._runtime_dir

    @property
    def ttl_seconds(self) -> float:
        """Time-to-live in seconds before an unrefreshed lease becomes stale."""
        return self._ttl_seconds

    @property
    def heartbeat_interval(self) -> float:
        """Interval in seconds between background heartbeats."""
        return self._heartbeat_interval

    @property
    def owner_label(self) -> str:
        """Human-readable label identifying this owner instance."""
        return self._owner_label

    def _read_lock_data(self) -> tuple[dict[str, Any] | None, str | None]:
        """Read and parse lock file data with single retry on transient error."""
        for attempt in range(2):
            try:
                if not self._lock_path.exists():
                    return None, None
                content = self._lock_path.read_text(encoding="utf-8")
                if not content.strip():
                    if attempt == 0:
                        time.sleep(0.05)
                        continue
                    return None, "corrupt"
                data = json.loads(content)
                if not isinstance(data, dict):
                    return None, "corrupt"
                return data, None
            except FileNotFoundError:
                return None, None
            except (OSError, json.JSONDecodeError):
                if attempt == 0:
                    time.sleep(0.05)
                    continue
                return None, "corrupt"
        return None, "corrupt"

    def _write_lock_file(self, payload: dict[str, Any]) -> None:
        """Write payload atomically via sibling tmp file with fsync and os.replace."""
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._lock_path.with_name(f"{self._lock_path.name}.tmp{uuid.uuid4().hex}")
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.replace(tmp_path, self._lock_path)
            except OSError:
                time.sleep(0.05)
                os.replace(tmp_path, self._lock_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def acquire(self) -> None:
        """Acquire lease; take over if stale/corrupt; raise if actively held."""
        now = time.time()
        data, error_reason = self._read_lock_data()

        if error_reason == "corrupt":
            takeovers: list[dict[str, Any]] = [
                {
                    "taken_at": now,
                    "previous": {
                        "pid": None,
                        "host": None,
                        "acquired_at": None,
                        "heartbeat_at": None,
                    },
                    "reason": "corrupt",
                }
            ]
        elif data is not None:
            raw_hb = data.get("heartbeat_at")
            heartbeat_val: float | None = None
            if isinstance(raw_hb, (int, float)):
                heartbeat_val = float(raw_hb)

            if heartbeat_val is None:
                # Malformed heartbeat field counts as corrupt
                takeovers = [
                    {
                        "taken_at": now,
                        "previous": {
                            "pid": data.get("pid"),
                            "host": data.get("host"),
                            "acquired_at": data.get("acquired_at"),
                            "heartbeat_at": None,
                        },
                        "reason": "corrupt",
                    }
                ]
            else:
                file_ttl = data.get("ttl_seconds")
                effective_ttl = (
                    float(file_ttl)
                    if isinstance(file_ttl, (int, float)) and file_ttl > 0
                    else self._ttl_seconds
                )
                age = now - heartbeat_val

                # Active lease held by someone else (allowing small clock jitter)
                if data.get("holder_id") != self._holder_id and -5.0 <= age < effective_ttl:
                    details = {
                        "holder_id": data.get("holder_id"),
                        "pid": data.get("pid"),
                        "host": data.get("host"),
                        "owner_label": data.get("owner_label", ""),
                        "acquired_at": data.get("acquired_at"),
                        "heartbeat_at": heartbeat_val,
                    }
                    raise ReportingStoreOwnershipError(
                        f"Reporting store is currently owned by pid {details['pid']} on {details['host']}.",
                        details=details,
                    )

                # Lease is stale: record takeover
                takeovers = (
                    list(data.get("takeovers", []))
                    if isinstance(data.get("takeovers"), list)
                    else []
                )
                takeovers.append(
                    {
                        "taken_at": now,
                        "previous": {
                            "pid": data.get("pid"),
                            "host": data.get("host"),
                            "acquired_at": data.get("acquired_at"),
                            "heartbeat_at": heartbeat_val,
                        },
                        "reason": "stale",
                    }
                )
        else:
            # File does not exist: fresh acquisition
            takeovers = []

        payload: dict[str, Any] = {
            "holder_id": self._holder_id,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "owner_label": self._owner_label,
            "acquired_at": now,
            "heartbeat_at": now,
            "ttl_seconds": self._ttl_seconds,
            "takeovers": takeovers,
        }
        self._write_lock_file(payload)
        self._lost = False

    def heartbeat(self) -> None:
        """Update heartbeat timestamp if still the owner; raise if ownership lost."""
        data, error_reason = self._read_lock_data()
        if error_reason is not None or data is None:
            self._lost = True
            raise ReportingStoreOwnershipError(
                "Lock file is missing or unreadable; ownership lost.",
                details={"holder_id": self._holder_id},
            )

        current_holder = data.get("holder_id")
        if current_holder != self._holder_id:
            self._lost = True
            details = {
                "holder_id": current_holder,
                "pid": data.get("pid"),
                "host": data.get("host"),
                "owner_label": data.get("owner_label", ""),
                "acquired_at": data.get("acquired_at"),
                "heartbeat_at": data.get("heartbeat_at"),
            }
            raise ReportingStoreOwnershipError(
                f"Ownership lost to holder {current_holder}.",
                details=details,
            )

        now = time.time()
        data["heartbeat_at"] = now
        self._write_lock_file(data)

    def _heartbeat_loop(self) -> None:
        """Background thread loop refreshing heartbeat at interval."""
        while not self._stop_event.wait(self._heartbeat_interval):
            if self._stop_event.is_set():
                break
            try:
                self.heartbeat()
            except ReportingStoreOwnershipError:
                self._lost = True
                break
            except Exception:
                pass

    def start_heartbeat(self) -> None:
        """Start background daemon thread to refresh heartbeat."""
        with self._thread_lock:
            if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
                return
            self._stop_event.clear()
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"StoreOwnershipHeartbeat-{self._holder_id[:8]}",
                daemon=True,
            )
            self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        """Signal background heartbeat thread to stop and wait for it to finish."""
        self._stop_event.set()
        with self._thread_lock:
            thread = self._heartbeat_thread
            self._heartbeat_thread = None
        if thread is not None and thread.is_alive():
            if thread is not threading.current_thread():
                thread.join(timeout=2.0)

    def release(self) -> None:
        """Stop heartbeat and remove lock file if still held by this lease."""
        self.stop_heartbeat()
        data, _ = self._read_lock_data()
        if data is not None and data.get("holder_id") == self._holder_id:
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass

    def __enter__(self) -> StoreOwnershipLease:
        self.acquire()
        self.start_heartbeat()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.release()
