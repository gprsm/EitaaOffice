"""Account-scoped Eitaa runtime and fail-closed registry.

The registry keeps API v1 pinned to one explicit runtime. With the feature flag
off that runtime is always Legacy. With the feature flag on, v1 can only use
the configured canonical default MessengerAccount. No login/logout transition
is implemented here; those remain Phase 4-C concerns.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Collection, Mapping
import ctypes
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Iterator
import uuid

from eitaa_core import EitaaAuth

from ..config import BridgeConfig
from ..errors import EitaaRuntimeError
from ..facade import EitaaBridge
from ..infrastructure.content_index_store import SQLiteContentIndexStore
from ..infrastructure.data_scope import ProviderAccountScope
from ..infrastructure.dialog_catalog import JsonDialogCatalog
from ..infrastructure.diagnostics import BridgeDiagnosticManager, RuntimeLogger
from ..infrastructure.eitaa.sender_directory import (
    SQLiteSenderDirectory,
    clear_legacy_sender_directory,
    configure_sender_directory,
    sender_directory_scope,
)
from ..infrastructure.eitaa.dialog_permissions import install_dialog_permission_capture
from ..infrastructure.eitaa.session_ownership import (
    EitaaSessionOwnership,
    SessionOwnershipMode,
    canonical_messenger_account_id,
)
from ..infrastructure.coordinator import (
    CoordinatorDatabase,
    MessengerAccountRuntimeRecord,
    PhoneProtector,
    WorkerInstanceRecord,
    default_phone_protector,
    validate_canonical_e164,
)
from .scheduler import EitaaOperationScheduler, EitaaPriority
from .process_runtime import EitaaProcessRuntime, EitaaProcessWorkerClient


install_dialog_permission_capture()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _process_is_alive(process_id: int) -> bool | None:
    """Return False only when the operating system confirms a process is gone."""

    if process_id <= 0:
        return False
    if process_id == os.getpid():
        return True
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        open_process.restype = ctypes.c_void_p
        handle = open_process(0x1000, False, process_id)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return False
            if error == 5:
                return True
            return None
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            return int(exit_code.value) == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _process_executable_name(process_id: int) -> str | None:
    """Return the OS-reported executable name without trusting a reused PID."""

    if process_id <= 0:
        return None
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class _ProcessEntry32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        create_snapshot = kernel32.CreateToolhelp32Snapshot
        create_snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
        create_snapshot.restype = ctypes.c_void_p
        process_first = kernel32.Process32FirstW
        process_first.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32W)]
        process_first.restype = ctypes.c_bool
        process_next = kernel32.Process32NextW
        process_next.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32W)]
        process_next.restype = ctypes.c_bool
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_bool

        snapshot = create_snapshot(0x00000002, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or snapshot == invalid_handle:
            return None
        try:
            entry = _ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(_ProcessEntry32W)
            if not process_first(snapshot, ctypes.byref(entry)):
                return None
            while True:
                if int(entry.th32ProcessID) == process_id:
                    selected = str(entry.szExeFile).strip()
                    return selected or None
                if not process_next(snapshot, ctypes.byref(entry)):
                    return None
        finally:
            close_handle(snapshot)

    proc_executable = Path(f"/proc/{process_id}/exe")
    try:
        return proc_executable.resolve(strict=True).name or None
    except OSError:
        return None


def _process_owns_worker(
    process_id: int,
    *,
    alive: bool | None = None,
) -> bool | None:
    """Distinguish a live worker from an unrelated process that reused its PID."""

    selected_alive = _process_is_alive(process_id) if alive is None else alive
    if selected_alive is not True:
        return selected_alive
    executable_name = _process_executable_name(process_id)
    if executable_name is None:
        return None
    return executable_name.casefold() == Path(sys.executable).name.casefold()


class AccountWorkerLease:
    """Exclusive, recoverable-on-clean-close ownership of one worker path."""

    def __init__(
        self,
        path: Path,
        messenger_account_id: str,
        lease_id: str,
        *,
        recovered_stale_archive: Path | None = None,
    ) -> None:
        self.path = path
        self.messenger_account_id = messenger_account_id
        self.lease_id = lease_id
        self.recovered_stale_archive = recovered_stale_archive
        self._released = False

    @classmethod
    def acquire(
        cls,
        path: Path,
        messenger_account_id: str,
        *,
        session_generation: int,
        storage_revision: int,
    ) -> "AccountWorkerLease":
        selected_id = canonical_messenger_account_id(messenger_account_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        lease_id = str(uuid.uuid4())
        payload = {
            "schema_version": 1,
            "messenger_account_id": selected_id,
            "provider": "eitaa",
            "lease_id": lease_id,
            "process_id": os.getpid(),
            "session_generation": session_generation,
            "storage_revision": storage_revision,
            "acquired_at": _utc_now(),
        }
        recovered_stale_archive: Path | None = None
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            recovered_stale_archive = cls._archive_confirmed_stale(
                path,
                selected_id,
            )
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError as exc:
                raise EitaaRuntimeError(
                    "An Eitaa worker already owns this MessengerAccount.",
                    safe_context={"messenger_account_id": selected_id},
                    code="eitaa_worker_lease_held",
                ) from exc
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return cls(
            path,
            selected_id,
            lease_id,
            recovered_stale_archive=recovered_stale_archive,
        )

    @classmethod
    def _archive_confirmed_stale(
        cls,
        path: Path,
        messenger_account_id: str,
    ) -> Path:
        """Archive a well-formed lease only when its PID is definitely dead."""

        recovery_lock = path.with_name(f".{path.name}.recovery.lock")
        recovery_descriptor: int | None = None
        try:
            recovery_descriptor = os.open(
                recovery_lock,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            )
            os.write(recovery_descriptor, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(recovery_descriptor)
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("lease payload is not an object")
            if (
                payload.get("schema_version") != 1
                or payload.get("messenger_account_id") != messenger_account_id
                or payload.get("provider") != "eitaa"
            ):
                raise ValueError("lease identity does not match")
            lease_id = str(payload.get("lease_id") or "")
            parsed_lease = uuid.UUID(lease_id)
            if parsed_lease.version != 4 or str(parsed_lease) != lease_id:
                raise ValueError("lease identifier is invalid")
            process_id = payload.get("process_id")
            if not isinstance(process_id, int) or process_id <= 0:
                raise ValueError("lease process identifier is invalid")
            session_generation = payload.get("session_generation")
            storage_revision = payload.get("storage_revision")
            acquired_at = payload.get("acquired_at")
            if (
                not isinstance(session_generation, int)
                or session_generation < 0
                or not isinstance(storage_revision, int)
                or storage_revision <= 0
                or not isinstance(acquired_at, str)
                or not acquired_at
            ):
                raise ValueError("lease metadata is invalid")
            alive = _process_is_alive(process_id)
            owns_worker = _process_owns_worker(process_id, alive=alive)
            if owns_worker is not False:
                raise EitaaRuntimeError(
                    "An Eitaa worker already owns this MessengerAccount.",
                    safe_context={"messenger_account_id": messenger_account_id},
                    code=(
                        "eitaa_worker_lease_held"
                        if owns_worker is True
                        else "eitaa_worker_lease_owner_unknown"
                    ),
                )
            if path.read_bytes() != raw:
                raise EitaaRuntimeError(
                    "The Eitaa worker lease changed during stale recovery.",
                    safe_context={"messenger_account_id": messenger_account_id},
                    code="eitaa_worker_lease_recovery_race",
                )
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            archive = path.with_name(
                f"{path.name}.stale.{stamp}.{lease_id}.json"
            )
            os.replace(path, archive)
            return archive
        except EitaaRuntimeError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise EitaaRuntimeError(
                "The existing Eitaa worker lease cannot be recovered safely.",
                safe_context={
                    "messenger_account_id": messenger_account_id,
                    "error_type": type(exc).__name__,
                },
                code="eitaa_worker_lease_recovery_unsafe",
            ) from exc
        finally:
            if recovery_descriptor is not None:
                os.close(recovery_descriptor)
                try:
                    recovery_lock.unlink()
                except OSError:
                    pass

    def release(self) -> None:
        if self._released:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict) or payload.get("lease_id") != self.lease_id:
            raise EitaaRuntimeError(
                "The Eitaa worker lease changed before clean shutdown.",
                safe_context={"messenger_account_id": self.messenger_account_id},
                code="eitaa_worker_lease_mismatch",
            )
        try:
            self.path.unlink()
        except OSError as exc:
            raise EitaaRuntimeError(
                "The Eitaa worker lease could not be released.",
                safe_context={
                    "messenger_account_id": self.messenger_account_id,
                    "error_type": type(exc).__name__,
                },
                code="eitaa_worker_lease_release_failed",
            ) from exc
        self._released = True

    def update_session_generation(self, session_generation: int) -> None:
        """Atomically refresh the generation carried by the owned lease."""

        if self._released:
            raise EitaaRuntimeError(
                "The Eitaa worker lease is already released.",
                safe_context={"messenger_account_id": self.messenger_account_id},
                code="eitaa_worker_lease_released",
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EitaaRuntimeError(
                "The Eitaa worker lease could not be refreshed.",
                safe_context={
                    "messenger_account_id": self.messenger_account_id,
                    "error_type": type(exc).__name__,
                },
                code="eitaa_worker_lease_refresh_failed",
            ) from exc
        if not isinstance(payload, dict) or payload.get("lease_id") != self.lease_id:
            raise EitaaRuntimeError(
                "The Eitaa worker lease changed before its generation refresh.",
                safe_context={"messenger_account_id": self.messenger_account_id},
                code="eitaa_worker_lease_mismatch",
            )
        if payload.get("session_generation") == session_generation:
            return
        payload["session_generation"] = session_generation
        payload["refreshed_at"] = _utc_now()
        temporary = self.path.with_name(
            f".{self.path.name}.{self.lease_id}.refresh.tmp"
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                descriptor = None
                json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            if descriptor is not None:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
            raise EitaaRuntimeError(
                "The Eitaa worker lease generation refresh failed.",
                safe_context={
                    "messenger_account_id": self.messenger_account_id,
                    "error_type": type(exc).__name__,
                },
                code="eitaa_worker_lease_refresh_failed",
            ) from exc


class EitaaAccountRuntime:
    """All mutable provider state owned by one explicit session boundary."""

    def __init__(
        self,
        ownership: EitaaSessionOwnership,
        *,
        diagnostics: BridgeDiagnosticManager,
        logger: RuntimeLogger,
        owns_logger: bool,
        runtime_record: MessengerAccountRuntimeRecord | None = None,
        worker_lease: AccountWorkerLease | None = None,
        coordinator: CoordinatorDatabase | None = None,
        phone_protector: PhoneProtector | None = None,
    ) -> None:
        self.ownership = ownership
        self.runtime_record = runtime_record
        self.diagnostics = diagnostics
        self.logger = logger
        self._owns_logger = owns_logger
        self._worker_lease = worker_lease
        self._worker_instance_id: str | None = None
        self._worker_heartbeat_stop = threading.Event()
        self._worker_heartbeat_thread: threading.Thread | None = None
        self._coordinator = coordinator
        self._phone_protector = phone_protector
        account_suffix = (
            ownership.messenger_account_id[:8]
            if ownership.messenger_account_id is not None
            else "legacy"
        )
        self.data_scope = (
            ProviderAccountScope.for_account(ownership.messenger_account_id)
            if ownership.messenger_account_id is not None
            else ProviderAccountScope.legacy()
        )

        self.media_cache_lock = threading.RLock()
        self.media_cache_files: dict[str, tuple[Path, str, float, str]] = {}
        self.avatar_source_cache_lock = threading.RLock()
        self.avatar_source_cache: dict[
            str, tuple[float, dict[str, tuple[Any, Any]]]
        ] = {}
        self.avatar_source_cache_ttl_seconds = 300.0
        self.auth_lock = threading.RLock()
        self.eitaa_lock = threading.RLock()
        self.scheduler = EitaaOperationScheduler(
            worker_name=(
                "eitaa-operation-scheduler"
                if ownership.mode is SessionOwnershipMode.LEGACY
                else f"eitaa-operation-{account_suffix}"
            )
        )
        self.jobs_lock = threading.RLock()
        self.dialog_sync_jobs: dict[str, dict[str, Any]] = {}
        self.active_dialog_sync_job: str | None = None
        self.content_index_lock = threading.RLock()
        self.content_index_jobs: dict[str, dict[str, Any]] = {}
        self.content_index_active: dict[str, str] = {}
        self.content_index_cancellations: dict[str, threading.Event] = {}
        self.content_index_store = SQLiteContentIndexStore(
            ownership.content_index_file,
            scope=self.data_scope,
        )
        self.sender_directory: SQLiteSenderDirectory = configure_sender_directory(
            ownership.sender_directory_file,
            legacy_default=ownership.mode is SessionOwnershipMode.LEGACY,
            scope=self.data_scope,
        )
        self.contact_import_lock = threading.RLock()
        self.contact_import_jobs: dict[str, dict[str, Any]] = {}
        self.contact_import_cancellations: dict[str, threading.Event] = {}
        self.eitaa_contacts_cache_lock = threading.RLock()
        self.eitaa_contacts_cache: dict[
            str, tuple[float, tuple[dict[str, Any], ...], bool]
        ] = {}
        self.eitaa_contacts_cache_ttl_seconds = 300.0
        self.background_tasks: dict[str, dict[str, Any]] = {}
        self.read_queue_lock = threading.RLock()
        self.pending_read_receipts: dict[str, dict[str, Any]] = {}
        self.read_worker_active = False
        self.read_receipt_delay_seconds = 3.0
        self.auth_runtime: EitaaAuth | None = None
        self.auth_challenge: Any | None = None
        self.dialog_catalog = JsonDialogCatalog(
            ownership.dialog_catalog_file,
            base_directory=ownership.installation_root,
            scope=self.data_scope,
        )
        repaired_dialog_peer_paths = self.dialog_catalog.repair_migrated_peer_paths()
        self._closed = False
        self._close_lock = threading.Lock()
        self.logger.emit(
            "eitaa_runtime_started",
            fields={
                **ownership.safe_summary(),
                "repaired_dialog_peer_paths": repaired_dialog_peer_paths,
                "session_generation": (
                    runtime_record.session_generation if runtime_record else None
                ),
                "storage_revision": (
                    runtime_record.storage_revision if runtime_record else None
                ),
            },
        )
        if worker_lease is not None and worker_lease.recovered_stale_archive is not None:
            self.logger.emit(
                "eitaa_worker_stale_lease_recovered",
                level="warning",
                fields={
                    "archive_name": worker_lease.recovered_stale_archive.name,
                },
            )

    @classmethod
    def legacy(
        cls,
        config: BridgeConfig,
        *,
        diagnostics: BridgeDiagnosticManager,
        logger: RuntimeLogger,
    ) -> "EitaaAccountRuntime":
        ownership = EitaaSessionOwnership.legacy(
            config.source_file.parent,
            config.core,
        )
        return cls(
            ownership,
            diagnostics=diagnostics,
            logger=logger,
            owns_logger=False,
        )

    @classmethod
    def account(
        cls,
        config: BridgeConfig,
        runtime_record: MessengerAccountRuntimeRecord,
        *,
        coordinator: CoordinatorDatabase,
        phone_protector: PhoneProtector,
    ) -> "EitaaAccountRuntime":
        ownership = EitaaSessionOwnership.for_messenger_account(
            config.source_file.parent,
            runtime_record.messenger_account_id,
            core_template=config.core,
        )
        if ownership.worker_lock_file is None or ownership.worker_log_file is None:
            raise EitaaRuntimeError(
                "The account runtime path contract is incomplete.",
                code="eitaa_runtime_path_contract_incomplete",
            )
        if ownership.worker_diagnostics_root is None:
            raise EitaaRuntimeError(
                "The account diagnostics path contract is incomplete.",
                code="eitaa_runtime_path_contract_incomplete",
            )
        lease = AccountWorkerLease.acquire(
            ownership.worker_lock_file,
            runtime_record.messenger_account_id,
            session_generation=runtime_record.session_generation,
            storage_revision=runtime_record.storage_revision,
        )
        logger: RuntimeLogger | None = None
        try:
            logger = RuntimeLogger(
                ownership.worker_log_file,
                source="provider_worker",
                context_fields={
                    "messenger_account_id": runtime_record.messenger_account_id,
                    "provider": "eitaa",
                    "owner_mode": SessionOwnershipMode.MESSENGER_ACCOUNT.value,
                },
            )
            diagnostics = BridgeDiagnosticManager(
                ownership.worker_diagnostics_root,
                enabled=config.diagnostics.enabled,
            )
            return cls(
                ownership,
                diagnostics=diagnostics,
                logger=logger,
                owns_logger=True,
                runtime_record=runtime_record,
                worker_lease=lease,
                coordinator=coordinator,
                phone_protector=phone_protector,
            )
        except Exception:
            if logger is not None:
                logger.close()
            lease.release()
            raise

    @classmethod
    def account_process(
        cls,
        config: BridgeConfig,
        runtime_record: MessengerAccountRuntimeRecord,
    ) -> "EitaaAccountRuntime":
        """Open account-owned mutable state inside its dedicated Child only."""

        ownership = EitaaSessionOwnership.for_messenger_account(
            config.source_file.parent,
            runtime_record.messenger_account_id,
            core_template=config.core,
        )
        if ownership.worker_lock_file is None or ownership.worker_log_file is None:
            raise EitaaRuntimeError(
                "The account runtime path contract is incomplete.",
                code="eitaa_runtime_path_contract_incomplete",
            )
        if ownership.worker_diagnostics_root is None:
            raise EitaaRuntimeError(
                "The account diagnostics path contract is incomplete.",
                code="eitaa_runtime_path_contract_incomplete",
            )
        lease = AccountWorkerLease.acquire(
            ownership.worker_lock_file,
            runtime_record.messenger_account_id,
            session_generation=runtime_record.session_generation,
            storage_revision=runtime_record.storage_revision,
        )
        logger: RuntimeLogger | None = None
        try:
            logger = RuntimeLogger(
                ownership.worker_log_file,
                source="provider_worker",
                context_fields={
                    "messenger_account_id": runtime_record.messenger_account_id,
                    "provider": "eitaa",
                    "owner_mode": SessionOwnershipMode.MESSENGER_ACCOUNT.value,
                    "runtime_boundary": "child_process",
                },
            )
            diagnostics = BridgeDiagnosticManager(
                ownership.worker_diagnostics_root,
                enabled=config.diagnostics.enabled,
            )
            coordinator_root = (
                config.source_file.parent / "data" / "coordinator"
            )
            coordinator = CoordinatorDatabase(
                coordinator_root / "coordinator.sqlite3"
            )
            phone_protector = default_phone_protector(coordinator_root)
            return cls(
                ownership,
                diagnostics=diagnostics,
                logger=logger,
                owns_logger=True,
                runtime_record=runtime_record,
                worker_lease=lease,
                coordinator=coordinator,
                phone_protector=phone_protector,
            )
        except Exception:
            if logger is not None:
                logger.close()
            lease.release()
            raise

    def refresh_process_session_generation(self, session_generation: int) -> None:
        if (
            self._worker_lease is None
            or isinstance(session_generation, bool)
            or not isinstance(session_generation, int)
            or session_generation < 0
        ):
            raise EitaaRuntimeError(
                "The process runtime generation cannot be refreshed.",
                code="eitaa_process_generation_refresh_invalid",
            )
        self._worker_lease.update_session_generation(session_generation)

    @property
    def peer_directory(self) -> Path:
        return self.ownership.dialog_catalog_file.parent

    @property
    def contact_peers_directory(self) -> Path:
        return self.ownership.contact_peers_directory

    @property
    def upload_directory(self) -> Path:
        if self.ownership.worker_cache_directory is not None:
            return self.ownership.worker_cache_directory / "uploads"
        return self.ownership.installation_root / "runtime" / "uploads"

    @contextmanager
    def operation_scope(self) -> Iterator[None]:
        with self.eitaa_lock, sender_directory_scope(self.sender_directory):
            yield

    def run_sync(
        self,
        *,
        priority: EitaaPriority,
        kind: str,
        callback: Callable[[], Any],
        timeout: float | None = None,
    ) -> Any:
        def guarded() -> Any:
            with self.operation_scope():
                return callback()

        return self.scheduler.run_sync(
            priority=priority,
            kind=kind,
            callback=guarded,
            timeout=timeout,
        )

    def close_shared_core(self) -> None:
        EitaaBridge.close_shared_core(self.ownership.core)

    @property
    def is_account_scoped(self) -> bool:
        return self.ownership.mode is SessionOwnershipMode.MESSENGER_ACCOUNT

    def refresh_auth_record(self) -> MessengerAccountRuntimeRecord:
        coordinator, account_id = self._require_account_coordinator()
        record = coordinator.messenger_account_runtime(account_id)
        self.runtime_record = record
        return record

    def resolve_login_phone(self, supplied_phone: str | None = None) -> str:
        """Reveal only this account's protected PhoneAccount for provider login."""

        coordinator, account_id = self._require_account_coordinator()
        if self._phone_protector is None:
            raise EitaaRuntimeError(
                "The account phone protector is unavailable.",
                safe_context={"messenger_account_id": account_id},
                code="eitaa_account_phone_protector_missing",
            )
        identity = coordinator.messenger_account_phone_identity(account_id)
        if identity.provider != "eitaa":
            raise EitaaRuntimeError(
                "The account phone identity belongs to another provider.",
                safe_context={"messenger_account_id": account_id},
                code="eitaa_account_phone_provider_mismatch",
            )
        phone = self._phone_protector.reveal(identity.protected_phone)
        if supplied_phone is not None and str(supplied_phone).strip():
            candidate = validate_canonical_e164(str(supplied_phone).strip())
            if not hmac.compare_digest(candidate, phone):
                raise EitaaRuntimeError(
                    "The supplied phone does not own the selected MessengerAccount.",
                    safe_context={"messenger_account_id": account_id},
                    code="eitaa_account_phone_mismatch",
                )
        return phone

    def transition_auth(
        self,
        *,
        expected_states: Collection[str],
        expected_generation: int,
        new_state: str,
        increment_generation: bool,
        reason_code: str,
        action: str,
        mark_validated: bool = False,
        audit_when_unchanged: bool = True,
        actor_app_user_id: str | None = None,
        actor_global_role: str | None = None,
        request_id: str | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> MessengerAccountRuntimeRecord:
        coordinator, account_id = self._require_account_coordinator()
        record = coordinator.transition_messenger_auth(
            account_id,
            expected_states=expected_states,
            expected_generation=expected_generation,
            new_state=new_state,
            increment_generation=increment_generation,
            reason_code=reason_code,
            action=action,
            mark_validated=mark_validated,
            audit_when_unchanged=audit_when_unchanged,
            actor_app_user_id=actor_app_user_id,
            actor_global_role=actor_global_role,
            request_id=request_id,
            safe_metadata=safe_metadata,
        )
        self.runtime_record = record
        if self._worker_lease is not None:
            try:
                self._worker_lease.update_session_generation(record.session_generation)
            except EitaaRuntimeError as exc:
                self.logger.emit(
                    "eitaa_worker_lease_generation_refresh_failed",
                    level="warning",
                    fields={
                        "session_generation": record.session_generation,
                        "error_code": exc.code,
                    },
                )
        return record

    def audit_auth_event(
        self,
        *,
        action: str,
        result: str,
        reason_code: str,
        actor_app_user_id: str | None = None,
        actor_global_role: str | None = None,
        request_id: str | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        coordinator, account_id = self._require_account_coordinator()
        coordinator.audit_messenger_auth_event(
            account_id,
            action=action,
            result=result,
            reason_code=reason_code,
            actor_app_user_id=actor_app_user_id,
            actor_global_role=actor_global_role,
            request_id=request_id,
            safe_metadata=safe_metadata,
        )

    def attach_worker_supervisor(
        self,
        worker: WorkerInstanceRecord,
        *,
        heartbeat_seconds: float = 5.0,
    ) -> None:
        """Attach one coordinator heartbeat loop to this account runtime."""

        if not self.is_account_scoped or self._coordinator is None:
            raise EitaaRuntimeError(
                "Worker supervision requires an account runtime.",
                code="eitaa_worker_supervisor_account_required",
            )
        if worker.messenger_account_id != self.ownership.messenger_account_id:
            raise EitaaRuntimeError(
                "The worker instance belongs to another account.",
                code="eitaa_worker_supervisor_account_mismatch",
            )
        if self._worker_heartbeat_thread is not None:
            if self._worker_instance_id == worker.worker_instance_id:
                return
            raise EitaaRuntimeError(
                "The account runtime already has a worker supervisor.",
                code="eitaa_worker_supervisor_already_attached",
            )
        self._worker_instance_id = worker.worker_instance_id
        self._worker_heartbeat_stop.clear()

        def heartbeat_loop() -> None:
            failures = 0
            while not self._worker_heartbeat_stop.wait(heartbeat_seconds):
                try:
                    assert self._coordinator is not None
                    self._coordinator.heartbeat_worker(worker.worker_instance_id)
                    if failures:
                        self.logger.emit(
                            "eitaa_worker_heartbeat_recovered",
                            fields={
                                "worker_instance_id": worker.worker_instance_id,
                                "consecutive_failures": failures,
                            },
                        )
                    failures = 0
                except Exception as exc:
                    failures += 1
                    self.logger.emit(
                        "eitaa_worker_heartbeat_failed",
                        level="warning",
                        fields={
                            "worker_instance_id": worker.worker_instance_id,
                            "consecutive_failures": failures,
                            "error_type": type(exc).__name__,
                        },
                    )

        self._worker_heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            name=f"eitaa-heartbeat-{worker.messenger_account_id[:8]}",
            daemon=True,
        )
        self._worker_heartbeat_thread.start()
        self.logger.emit(
            "eitaa_worker_supervisor_started",
            fields=worker.safe_summary(),
        )

    def _require_account_coordinator(self) -> tuple[CoordinatorDatabase, str]:
        account_id = self.ownership.messenger_account_id
        if (
            self.ownership.mode is not SessionOwnershipMode.MESSENGER_ACCOUNT
            or account_id is None
            or self._coordinator is None
        ):
            raise EitaaRuntimeError(
                "This operation requires a MessengerAccount runtime.",
                code="eitaa_account_runtime_required",
            )
        return self._coordinator, account_id

    def safe_summary(self) -> dict[str, object]:
        return {
            **self.ownership.safe_summary(),
            "scheduler": self.scheduler.snapshot(),
            "closed": self._closed,
        }

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        with self.content_index_lock:
            for cancellation in self.content_index_cancellations.values():
                cancellation.set()
        with self.auth_lock:
            if self.auth_runtime is not None:
                try:
                    self.auth_runtime.close()
                except Exception as exc:
                    self.logger.emit(
                        "auth_runtime_close_failed",
                        level="warning",
                        reason_code="auth_runtime_close_failed",
                        fields={"error_type": type(exc).__name__},
                    )
                self.auth_runtime = None
                self.auth_challenge = None
        self._worker_heartbeat_stop.set()
        if self._worker_heartbeat_thread is not None:
            self._worker_heartbeat_thread.join(timeout=2.0)
            self._worker_heartbeat_thread = None
        self.scheduler.close()
        self.close_shared_core()
        if (
            self._coordinator is not None
            and self.ownership.messenger_account_id is not None
            and self._worker_instance_id is not None
        ):
            try:
                self._coordinator.complete_worker_stop(
                    self.ownership.messenger_account_id,
                    worker_instance_id=self._worker_instance_id,
                    reason_code="worker_runtime_closed",
                    pause_account=False,
                )
            except Exception as exc:
                self.logger.emit(
                    "eitaa_worker_stop_reconciliation_failed",
                    level="warning",
                    fields={"error_type": type(exc).__name__},
                )
        self.logger.emit("eitaa_runtime_stopped", fields=self.ownership.safe_summary())
        if self.ownership.mode is SessionOwnershipMode.LEGACY:
            clear_legacy_sender_directory(self.sender_directory)
        if self._owns_logger:
            self.logger.close()
        if self._worker_lease is not None:
            self._worker_lease.release()


class EitaaRuntimeRegistry:
    """Create and retain one runtime per canonical MessengerAccount."""

    def __init__(
        self,
        config: BridgeConfig,
        *,
        application_diagnostics: BridgeDiagnosticManager,
        application_logger: RuntimeLogger,
        coordinator_database: str | Path | None = None,
        allow_empty_bootstrap: bool = False,
    ) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._closed = False
        self._shutdown_event = threading.Event()
        self._account_runtimes: dict[
            str, EitaaAccountRuntime | EitaaProcessRuntime
        ] = {}
        self._legacy_runtime: EitaaAccountRuntime | None = None
        if not config.features.worker_process.enabled:
            self._legacy_runtime = EitaaAccountRuntime.legacy(
                config,
                diagnostics=application_diagnostics,
                logger=application_logger,
            )
        self._application_diagnostics = application_diagnostics
        self._application_logger = application_logger
        coordinator_path = (
            Path(coordinator_database).expanduser().resolve()
            if coordinator_database is not None
            else config.source_file.parent
            / "data"
            / "coordinator"
            / "coordinator.sqlite3"
        )
        self._coordinator = CoordinatorDatabase(coordinator_path)
        self._phone_protector = default_phone_protector(
            config.source_file.parent / "data" / "coordinator"
        )
        feature = config.features.multi_session
        if (
            feature.enabled
            and feature.legacy_default_messenger_account_id is None
            and not allow_empty_bootstrap
            and self._coordinator.runnable_messenger_account_id() is None
        ):
            # No account is runnable and none can be resolved as the v1
            # default; the caller must treat this as an onboarding bootstrap.
            if self._legacy_runtime is not None:
                self._legacy_runtime.close()
            raise EitaaRuntimeError(
                "Multi-session v1 compatibility requires an explicit default account.",
                code="multi_session_legacy_default_required",
            )

    @property
    def legacy_runtime(self) -> EitaaAccountRuntime:
        if self._legacy_runtime is None:
            raise EitaaRuntimeError(
                "Legacy Eitaa runtime is disabled while process isolation is enabled.",
                code="eitaa_process_legacy_runtime_disabled",
            )
        return self._legacy_runtime

    @property
    def coordinator(self) -> CoordinatorDatabase:
        return self._coordinator

    def resolve_v1(self) -> EitaaAccountRuntime | EitaaProcessRuntime:
        feature = self.config.features.multi_session
        if not feature.enabled:
            return self.legacy_runtime
        selected_id = feature.legacy_default_messenger_account_id
        if selected_id is None:
            # A worker-process installation that started an account has no
            # configured legacy default by design; the running account is the
            # v1 runtime.  Booting after that explicit Start must not die.
            selected_id = self._coordinator.runnable_messenger_account_id()
        if selected_id is None:
            raise EitaaRuntimeError(
                "Multi-session v1 compatibility has no default account.",
                code="multi_session_legacy_default_required",
            )
        return self.runtime_for_account(selected_id)

    def peek_runtime_for_account(
        self,
        messenger_account_id: str,
    ) -> EitaaAccountRuntime | EitaaProcessRuntime | None:
        """Return an already-running account runtime without starting one.

        Read-only access for surfaces that must not have runtime-start side
        effects (e.g. the M2M recipient lookup). Returns None when the account
        has no live runtime in this process.
        """
        selected_id = canonical_messenger_account_id(messenger_account_id)
        with self._lock:
            if self._closed:
                return None
            return self._account_runtimes.get(selected_id)

    def runtime_for_account(
        self,
        messenger_account_id: str,
    ) -> EitaaAccountRuntime | EitaaProcessRuntime:
        if not self.config.features.multi_session.enabled:
            raise EitaaRuntimeError(
                "Account runtime selection is disabled.",
                code="multi_session_runtime_disabled",
            )
        selected_id = canonical_messenger_account_id(messenger_account_id)
        with self._lock:
            if self._closed:
                raise EitaaRuntimeError(
                    "The Eitaa runtime registry is closed.",
                    code="eitaa_runtime_registry_closed",
                )
            existing = self._account_runtimes.get(selected_id)
            if existing is not None:
                return existing
            record = self._coordinator.messenger_account_runtime(selected_id)
            self._assert_runnable(record)
            if self.config.features.worker_process.enabled:
                return self._start_process_runtime(
                    record,
                    actor_app_user_id=None,
                    actor_global_role=None,
                    request_id=None,
                )[0]
            self._prepare_worker_start(selected_id, request_id=None)
            worker = self._coordinator.request_worker_start(
                selected_id,
                process_id=os.getpid(),
                actor_app_user_id=None,
                actor_global_role=None,
            )[1]
            return self._open_account_runtime(record, worker)

    def start_account(
        self,
        messenger_account_id: str,
        *,
        actor_app_user_id: str,
        actor_global_role: str,
        request_id: str | None,
    ) -> tuple[EitaaAccountRuntime | EitaaProcessRuntime, WorkerInstanceRecord]:
        if not self.config.features.multi_session.enabled:
            raise EitaaRuntimeError(
                "Account worker management is disabled.",
                code="multi_session_runtime_disabled",
            )
        selected_id = canonical_messenger_account_id(messenger_account_id)
        with self._lock:
            existing = self._account_runtimes.get(selected_id)
            if existing is not None:
                record, worker = self._coordinator.request_worker_start(
                    selected_id,
                    process_id=(
                    existing.process_id
                        if isinstance(existing, EitaaProcessRuntime) or getattr(existing, "client", None) is not None
                        else os.getpid()
                    ),
                    actor_app_user_id=actor_app_user_id,
                    actor_global_role=actor_global_role,
                    request_id=request_id,
                )
                existing.runtime_record = record
                return existing, worker
            if self.config.features.worker_process.enabled:
                record = self._coordinator.messenger_account_runtime(selected_id)
                self._assert_startable(record)
                return self._start_process_runtime(
                    record,
                    actor_app_user_id=actor_app_user_id,
                    actor_global_role=actor_global_role,
                    request_id=request_id,
                )
            self._prepare_worker_start(selected_id, request_id=request_id)
            record, worker = self._coordinator.request_worker_start(
                selected_id,
                process_id=os.getpid(),
                actor_app_user_id=actor_app_user_id,
                actor_global_role=actor_global_role,
                request_id=request_id,
            )
            try:
                runtime = self._open_account_runtime(record, worker)
            except Exception as exc:
                try:
                    self._coordinator.fail_worker_start(
                        worker.worker_instance_id,
                        reason_code="worker_runtime_open_failed",
                        request_id=request_id,
                    )
                finally:
                    raise exc
            return runtime, worker

    def _start_process_runtime(
        self,
        record: MessengerAccountRuntimeRecord,
        *,
        actor_app_user_id: str | None,
        actor_global_role: str | None,
        request_id: str | None,
    ) -> tuple[EitaaProcessRuntime, WorkerInstanceRecord]:
        if record.provider == "bale":
            return self._start_bale_process_runtime(
                record,
                actor_app_user_id=actor_app_user_id,
                actor_global_role=actor_global_role,
                request_id=request_id,
            )
        account_id = record.messenger_account_id
        self._prepare_worker_start(account_id, request_id=request_id)
        self._coordinator.assert_worker_start_allowed(account_id)
        ownership = EitaaSessionOwnership.for_messenger_account(
            self.config.source_file.parent,
            account_id,
            core_template=self.config.core,
        )
        client = EitaaProcessWorkerClient.spawn(self.config, ownership)
        worker: WorkerInstanceRecord | None = None
        try:
            record, worker = self._coordinator.request_worker_start(
                account_id,
                process_id=client.process_id,
                actor_app_user_id=actor_app_user_id,
                actor_global_role=actor_global_role,
                request_id=request_id,
            )
            started = client.request(
                "eitaa.runtime.start",
                {
                    "runtime_record": record.safe_summary(),
                    "worker_instance_id": worker.worker_instance_id,
                    "worker_generation": worker.generation,
                },
                timeout_seconds=self.config.features.worker_process.startup_timeout_seconds,
            )
            if (
                started.get("status") != "ready"
                or started.get("worker_pid") != client.process_id
                or started.get("worker_instance_id") != worker.worker_instance_id
                or started.get("worker_generation") != worker.generation
                or started.get("core_owner_pid") != client.process_id
                or started.get("core_opened") is not False
                or started.get("core_open_deferred") is not True
            ):
                raise EitaaRuntimeError(
                    "The Eitaa Child returned an invalid runtime handshake.",
                    code="eitaa_process_runtime_handshake_invalid",
                )
            client.bind_fence(worker.worker_instance_id, worker.generation)
            ready = self._coordinator.mark_worker_ready(worker.worker_instance_id)
            runtime = EitaaProcessRuntime(
                self.config,
                record,
                ready,
                ownership,
                client,
                coordinator=self._coordinator,
                application_logger=self._application_logger,
            )
            self._account_runtimes[account_id] = runtime
            runtime.start_supervisor(self._handle_process_runtime_failure)
            return runtime, ready
        except Exception:
            self._account_runtimes.pop(account_id, None)
            try:
                client.close()
            except Exception:
                client.terminate()
            if worker is not None:
                try:
                    self._coordinator.fail_worker_start(
                        worker.worker_instance_id,
                        reason_code="worker_process_open_failed",
                        request_id=request_id,
                    )
                except Exception:
                    pass
            raise

    def _start_bale_process_runtime(
        self,
        record: MessengerAccountRuntimeRecord,
        *,
        actor_app_user_id: str | None,
        actor_global_role: str | None,
        request_id: str | None,
    ):
        from .bale_runtime import BaleAccountRuntime, BaleWorkerOwnership

        account_id = record.messenger_account_id
        self._prepare_worker_start(account_id, request_id=request_id)
        self._coordinator.assert_worker_start_allowed(account_id)
        client = EitaaProcessWorkerClient.spawn(
            self.config,
            BaleWorkerOwnership.for_account(self.config, account_id),
            provider="bale",
        )
        worker = None
        try:
            record, worker = self._coordinator.request_worker_start(
                account_id,
                process_id=client.process_id,
                actor_app_user_id=actor_app_user_id,
                actor_global_role=actor_global_role,
                request_id=request_id,
            )
            runtime = BaleAccountRuntime(
                self.config, record, worker, self._coordinator,
                self._application_logger, client=client,
                failure_callback=self._handle_process_runtime_failure,
            )
            runtime.worker = self._coordinator.mark_worker_ready(worker.worker_instance_id)
            self._account_runtimes[account_id] = runtime
            runtime.start_supervisor()
            return runtime, runtime.worker
        except Exception:
            self._account_runtimes.pop(account_id, None)
            try:
                client.close()
            except Exception:
                client.terminate()
            if worker is not None:
                self._coordinator.fail_worker_start(
                    worker.worker_instance_id,
                    reason_code="worker_process_open_failed",
                    request_id=request_id,
                )
            raise

    def _handle_process_runtime_failure(
        self,
        runtime: EitaaProcessRuntime,
        reason_code: str,
        exit_code: int | None,
    ) -> None:
        account_id = runtime.runtime_record.messenger_account_id
        with self._lock:
            if self._closed or self._account_runtimes.get(account_id) is not runtime:
                return
            self._account_runtimes.pop(account_id, None)
        runtime.fence(reason_code=reason_code)
        selected_exit_code = exit_code
        if selected_exit_code is None:
            selected_exit_code = runtime.client.process.poll()
        feature = self.config.features.worker_process
        decision = self._coordinator.record_worker_crash(
            runtime.worker.worker_instance_id,
            expected_generation=runtime.worker.generation,
            expected_process_id=runtime.process_id,
            reason_code=reason_code,
            exit_code=selected_exit_code,
            restart_window_seconds=feature.restart_window_seconds,
            max_restarts=feature.max_restarts,
            backoff_initial_seconds=feature.backoff_initial_seconds,
            backoff_max_seconds=feature.backoff_max_seconds,
            quarantine_seconds=feature.quarantine_seconds,
        )
        self._application_logger.emit(
            "eitaa_process_recovery_decided",
            level="warning",
            fields=decision.safe_summary(),
        )
        if not decision.restart_allowed:
            return
        if self._shutdown_event.wait(decision.retry_after_seconds):
            return
        with self._lock:
            if self._closed or account_id in self._account_runtimes:
                return
            record = self._coordinator.messenger_account_runtime(account_id)
            if record.lifecycle_state != "active" or record.desired_worker_state != "running":
                return
            try:
                replacement, replacement_worker = self._start_process_runtime(
                    record,
                    actor_app_user_id=None,
                    actor_global_role=None,
                    request_id=None,
                )
            except Exception as exc:
                self._application_logger.emit(
                    "eitaa_process_restart_failed",
                    level="error",
                    fields={
                        "messenger_account_id": account_id,
                        "previous_worker_instance_id": (
                            runtime.worker.worker_instance_id
                        ),
                        "previous_worker_generation": runtime.worker.generation,
                        "error_type": type(exc).__name__,
                        "error_code": getattr(exc, "code", None),
                    },
                )
                return
        self._application_logger.emit(
            "eitaa_process_restart_succeeded",
            fields={
                "messenger_account_id": account_id,
                "previous_worker_instance_id": runtime.worker.worker_instance_id,
                "previous_worker_generation": runtime.worker.generation,
                "worker_instance_id": replacement_worker.worker_instance_id,
                "worker_generation": replacement_worker.generation,
                "process_id": replacement.process_id,
            },
        )

    def _prepare_worker_start(
        self,
        messenger_account_id: str,
        *,
        request_id: str | None,
    ) -> None:
        active = self._coordinator.active_worker_instance(messenger_account_id)
        if active is None or active.process_id == os.getpid():
            return
        if active.process_id is None:
            raise EitaaRuntimeError(
                "The active worker record has no process owner.",
                safe_context={"messenger_account_id": messenger_account_id},
                code="eitaa_worker_process_owner_unknown",
            )
        alive = _process_is_alive(active.process_id)
        owns_worker = _process_owns_worker(active.process_id, alive=alive)
        if owns_worker is True:
            raise EitaaRuntimeError(
                "Another process still owns this MessengerAccount worker.",
                safe_context={"messenger_account_id": messenger_account_id},
                code="eitaa_worker_process_alive",
            )
        if owns_worker is None:
            raise EitaaRuntimeError(
                "The worker process owner could not be verified.",
                safe_context={"messenger_account_id": messenger_account_id},
                code="eitaa_worker_process_owner_unknown",
            )
        self._coordinator.recover_dead_worker_instance(
            active.worker_instance_id,
            expected_process_id=active.process_id,
            request_id=request_id,
            reason_code=(
                "worker_process_confirmed_dead"
                if alive is False
                else "worker_process_pid_reused"
            ),
        )

    def stop_account(
        self,
        messenger_account_id: str,
        *,
        actor_app_user_id: str,
        actor_global_role: str,
        request_id: str | None,
    ) -> MessengerAccountRuntimeRecord:
        if not self.config.features.multi_session.enabled:
            raise EitaaRuntimeError(
                "Account worker management is disabled.",
                code="multi_session_runtime_disabled",
            )
        selected_id = canonical_messenger_account_id(messenger_account_id)
        with self._lock:
            worker = self._coordinator.request_worker_stop(
                selected_id,
                actor_app_user_id=actor_app_user_id,
                actor_global_role=actor_global_role,
                request_id=request_id,
            )
            runtime = self._account_runtimes.pop(selected_id, None)
        close_error: Exception | None = None
        if runtime is not None:
            try:
                runtime.close()
            except Exception as exc:
                close_error = exc
        record = self._coordinator.complete_worker_stop(
            selected_id,
            worker_instance_id=(worker.worker_instance_id if worker else None),
            reason_code=(
                "worker_stop_completed" if close_error is None else "worker_stop_close_failed"
            ),
            pause_account=True,
        )
        if close_error is not None:
            raise EitaaRuntimeError(
                "The Eitaa account worker did not stop cleanly.",
                safe_context={"messenger_account_id": selected_id},
                code="eitaa_worker_stop_failed",
            ) from close_error
        return record

    def close_account(self, messenger_account_id: str) -> None:
        selected_id = canonical_messenger_account_id(messenger_account_id)
        with self._lock:
            runtime = self._account_runtimes.pop(selected_id, None)
        if runtime is not None:
            runtime.close()

    def _open_account_runtime(
        self,
        record: MessengerAccountRuntimeRecord,
        worker: WorkerInstanceRecord,
    ) -> EitaaAccountRuntime:
        if record.provider == "bale":
            from .bale_runtime import BaleAccountRuntime

            runtime = BaleAccountRuntime(
                self.config, record, worker, self._coordinator,
                self._application_logger,
            )
            try:
                runtime.worker = self._coordinator.mark_worker_ready(worker.worker_instance_id)
                runtime.start_supervisor()
            except Exception:
                runtime.close()
                raise
            self._account_runtimes[record.messenger_account_id] = runtime
            return runtime
        runtime = EitaaAccountRuntime.account(
            self.config,
            record,
            coordinator=self._coordinator,
            phone_protector=self._phone_protector,
        )
        try:
            ready = self._coordinator.mark_worker_ready(worker.worker_instance_id)
            runtime.attach_worker_supervisor(ready)
        except Exception:
            runtime.close()
            raise
        self._account_runtimes[record.messenger_account_id] = runtime
        return runtime

    @staticmethod
    def _assert_runnable(record: MessengerAccountRuntimeRecord) -> None:
        if record.provider not in {"eitaa", "bale"}:
            raise EitaaRuntimeError(
                "The selected MessengerAccount is not an Eitaa account.",
                safe_context={"messenger_account_id": record.messenger_account_id},
                code="eitaa_runtime_provider_mismatch",
            )
        if record.storage_revision != 1:
            raise EitaaRuntimeError(
                "The account storage revision is unsupported.",
                safe_context={
                    "messenger_account_id": record.messenger_account_id,
                    "storage_revision": record.storage_revision,
                },
                code="eitaa_runtime_storage_revision_unsupported",
            )
        if record.lifecycle_state != "active" or record.desired_worker_state != "running":
            raise EitaaRuntimeError(
                "The selected Eitaa account is not runnable.",
                safe_context={
                    "messenger_account_id": record.messenger_account_id,
                    "lifecycle_state": record.lifecycle_state,
                    "desired_worker_state": record.desired_worker_state,
                },
                code="eitaa_runtime_account_not_runnable",
            )

    @staticmethod
    def _assert_startable(record: MessengerAccountRuntimeRecord) -> None:
        """Validate an explicit Start request before the lifecycle transition.

        The coordinator's own start contract only blocks disabled,
        quarantined, or archived accounts; ``created`` and ``paused``
        accounts are exactly the ones an explicit Start is meant to
        promote to active/running.
        """

        if record.provider not in {"eitaa", "bale"}:
            raise EitaaRuntimeError(
                "The selected MessengerAccount is not an Eitaa account.",
                safe_context={"messenger_account_id": record.messenger_account_id},
                code="eitaa_runtime_provider_mismatch",
            )
        if record.storage_revision != 1:
            raise EitaaRuntimeError(
                "The account storage revision is unsupported.",
                safe_context={
                    "messenger_account_id": record.messenger_account_id,
                    "storage_revision": record.storage_revision,
                },
                code="eitaa_runtime_storage_revision_unsupported",
            )
        if record.lifecycle_state in {"disabled", "quarantined", "archived"}:
            raise EitaaRuntimeError(
                "The selected Eitaa account is not runnable.",
                safe_context={
                    "messenger_account_id": record.messenger_account_id,
                    "lifecycle_state": record.lifecycle_state,
                    "desired_worker_state": record.desired_worker_state,
                },
                code="eitaa_runtime_account_not_runnable",
            )

    def safe_summary(self) -> dict[str, object]:
        with self._lock:
            return {
                "feature_enabled": self.config.features.multi_session.enabled,
                "worker_process_enabled": self.config.features.worker_process.enabled,
                "v1_owner_mode": (
                    SessionOwnershipMode.MESSENGER_ACCOUNT.value
                    if self.config.features.multi_session.enabled
                    else SessionOwnershipMode.LEGACY.value
                ),
                "account_runtime_count": len(self._account_runtimes),
                "account_ids": tuple(sorted(self._account_runtimes)),
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._shutdown_event.set()
            accounts = list(self._account_runtimes.values())
            self._account_runtimes.clear()
        errors: list[Exception] = []
        for runtime in accounts:
            try:
                runtime.close()
            except Exception as exc:
                errors.append(exc)
        try:
            if self._legacy_runtime is not None:
                self._legacy_runtime.close()
        except Exception as exc:
            errors.append(exc)
        if errors:
            raise EitaaRuntimeError(
                "One or more Eitaa runtimes did not close cleanly.",
                safe_context={"failure_count": len(errors)},
                code="eitaa_runtime_close_failed",
            )
