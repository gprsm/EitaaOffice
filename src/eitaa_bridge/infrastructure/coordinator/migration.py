"""Copy-and-verify migration from the single-account legacy layout."""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys
from typing import Iterable, Iterator
from uuid import UUID, uuid4

from ...config import BridgeConfig
from ...errors import CoordinatorMigrationError, CoordinatorPreflightError
from ..eitaa.session_ownership import (
    ACCOUNT_CONTACT_PEERS_RELATIVE_PATH,
    ACCOUNT_CONTENT_INDEX_RELATIVE_PATH,
    ACCOUNT_CORE_DATABASE_RELATIVE_PATH,
    ACCOUNT_DIALOG_CATALOG_RELATIVE_PATH,
    ACCOUNT_MEDIA_RELATIVE_PATH,
    ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH,
    ACCOUNT_SESSION_RELATIVE_PATH,
)
from .identity import ProtectedPhone
from .store import CoordinatorDatabase, LegacyBootstrapResult

_SHA256_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    code: str

    def safe_summary(self) -> dict[str, object]:
        return {"name": self.name, "ok": self.ok, "code": self.code}


@dataclass(frozen=True, slots=True)
class MigrationSource:
    source: Path
    destination: PurePosixPath


@dataclass(frozen=True, slots=True)
class LegacyPreflightReport:
    checks: tuple[PreflightCheck, ...]
    source_file_count: int
    source_total_bytes: int
    required_free_bytes: int
    available_free_bytes: int

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.checks)

    def safe_summary(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checks": [item.safe_summary() for item in self.checks],
            "source_file_count": self.source_file_count,
            "source_total_bytes": self.source_total_bytes,
            "required_free_bytes": self.required_free_bytes,
            "available_free_bytes": self.available_free_bytes,
        }

    def require_ok(self) -> None:
        if self.ok:
            return
        failed = [item.code for item in self.checks if not item.ok]
        raise CoordinatorPreflightError(
            "The legacy migration preflight did not pass.",
            safe_context={"failed_checks": failed, "failed_count": len(failed)},
            code="legacy_migration_preflight_failed",
        )


@dataclass(frozen=True, slots=True)
class MigrationResult:
    bootstrap: LegacyBootstrapResult
    account_directory: Path
    coordinator_database: Path
    manifest_file: Path
    source_file_count: int
    source_total_bytes: int
    source_manifest_sha256: str

    def safe_summary(self) -> dict[str, object]:
        return {
            **self.bootstrap.safe_summary(),
            "account_directory_name": self.account_directory.name,
            "coordinator_database_name": self.coordinator_database.name,
            "manifest_file_name": self.manifest_file.name,
            "source_file_count": self.source_file_count,
            "source_total_bytes": self.source_total_bytes,
            "source_manifest_sha256": self.source_manifest_sha256,
            "feature_enabled": False,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and not (set(value) - _SHA256_HEX)


def _is_within(path: Path, root: Path) -> bool:
    selected = path.resolve()
    base = root.resolve()
    return selected == base or base in selected.parents


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        open_process.restype = ctypes.c_void_p
        handle = open_process(0x00100000 | 0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return int(exit_code.value) == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def _instance_lock(path: Path) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                acquired = False
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                acquired = False
        yield acquired
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


class LegacyMigrationService:
    """Stage, hash-verify, and atomically expose an initial Eitaa account."""

    def __init__(self, root: str | Path, config: BridgeConfig) -> None:
        self.root = Path(root).expanduser().resolve()
        self.config = config
        self.data_root = self.root / "data"
        self.accounts_root = self.data_root / "accounts"
        self.coordinator_root = self.data_root / "coordinator"
        self.coordinator_database = self.coordinator_root / "coordinator.sqlite3"

    def preflight(self) -> LegacyPreflightReport:
        checks: list[PreflightCheck] = []
        checks.append(
            PreflightCheck(
                "feature_flag_disabled",
                not self.config.features.multi_session.enabled,
                (
                    "feature_flag_disabled"
                    if not self.config.features.multi_session.enabled
                    else "feature_flag_must_be_disabled"
                ),
            )
        )
        runtime_active = self._runtime_active()
        checks.append(
            PreflightCheck(
                "legacy_runtime_stopped",
                not runtime_active,
                "runtime_stopped" if not runtime_active else "legacy_runtime_active",
            )
        )
        required_paths = (
            self.config.core.session_file,
            self.config.core.database_file,
        )
        paths_inside = all(_is_within(path, self.root) for path in required_paths)
        checks.append(
            PreflightCheck(
                "legacy_paths_inside_installation",
                paths_inside,
                "paths_safe" if paths_inside else "legacy_path_outside_installation",
            )
        )
        session_ok = self._valid_session_container(self.config.core.session_file)
        checks.append(
            PreflightCheck(
                "legacy_session_readable",
                session_ok,
                "session_container_readable" if session_ok else "legacy_session_invalid",
            )
        )
        database_ok = self._sqlite_quick_check(self.config.core.database_file)
        checks.append(
            PreflightCheck(
                "legacy_core_database_readable",
                database_ok,
                "core_database_readable" if database_ok else "legacy_core_database_invalid",
            )
        )
        target_absent = self._migration_targets_clean()
        checks.append(
            PreflightCheck(
                "coordinator_target_absent",
                target_absent,
                "coordinator_target_absent" if target_absent else "coordinator_already_exists",
            )
        )
        sources = tuple(self._sources())
        total_bytes = sum(item.source.stat().st_size for item in sources)
        required_free = max(64 * 1024 * 1024, total_bytes * 2)
        probe = self.data_root if self.data_root.exists() else self.root
        available = int(shutil.disk_usage(probe).free)
        checks.append(
            PreflightCheck(
                "sufficient_free_space",
                available >= required_free,
                "free_space_sufficient" if available >= required_free else "free_space_insufficient",
            )
        )
        return LegacyPreflightReport(
            checks=tuple(checks),
            source_file_count=len(sources),
            source_total_bytes=total_bytes,
            required_free_bytes=required_free,
            available_free_bytes=available,
        )

    def migrate(
        self,
        *,
        protected_phone: ProtectedPhone,
        display_name: str,
        backup_name: str,
        backup_manifest_sha256: str,
        operator_confirmed: bool,
    ) -> MigrationResult:
        if not operator_confirmed:
            raise CoordinatorMigrationError(
                "The legacy phone/account migration was not explicitly confirmed.",
                code="legacy_account_confirmation_required",
            )
        with _instance_lock(self.root / "runtime" / "office-launcher.lock") as acquired:
            if not acquired:
                raise CoordinatorMigrationError(
                    "The Office runtime owns the installation.",
                    code="migration_runtime_lock_unavailable",
                )
            return self._migrate_locked(
                protected_phone=protected_phone,
                display_name=display_name,
                backup_name=backup_name,
                backup_manifest_sha256=backup_manifest_sha256,
            )

    def _migrate_locked(
        self,
        *,
        protected_phone: ProtectedPhone,
        display_name: str,
        backup_name: str,
        backup_manifest_sha256: str,
    ) -> MigrationResult:
        preflight = self.preflight()
        preflight.require_ok()
        if not _valid_sha256(backup_manifest_sha256):
            raise CoordinatorMigrationError(
                "The required pre-migration backup was not verified.",
                code="migration_backup_not_verified",
            )
        migration_id = str(uuid4())
        app_user_id = str(uuid4())
        phone_account_id = str(uuid4())
        membership_id = str(uuid4())
        messenger_account_id = str(uuid4())
        staging_account = self.accounts_root / f".staging-{messenger_account_id}"
        final_account = self.accounts_root / messenger_account_id
        staging_database = self.coordinator_root / (
            f"coordinator.sqlite3.staging-{migration_id}"
        )
        if staging_account.exists() or final_account.exists() or staging_database.exists():
            raise CoordinatorMigrationError(
                "A migration staging target already exists.",
                code="migration_staging_collision",
            )
        sources = tuple(self._sources())
        try:
            staging_account.mkdir(parents=True, exist_ok=False)
            copied_files: list[dict[str, object]] = []
            for item in sources:
                destination = staging_account.joinpath(*item.destination.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.source, destination)
                source_hash = _sha256_file(item.source)
                destination_hash = _sha256_file(destination)
                if source_hash != destination_hash or item.source.stat().st_size != destination.stat().st_size:
                    raise CoordinatorMigrationError(
                        "A staged migration file did not match its source.",
                        safe_context={"destination_name": destination.name},
                        code="migration_copy_verification_failed",
                    )
                copied_files.append(
                    {
                        "destination": item.destination.as_posix(),
                        "size": destination.stat().st_size,
                        "sha256": destination_hash,
                    }
                )
            if self._runtime_active():
                raise CoordinatorMigrationError(
                    "The legacy runtime started while migration files were being staged.",
                    code="legacy_runtime_started_during_migration",
                )
            for item, copied in zip(sources, copied_files, strict=True):
                if (
                    _sha256_file(item.source) != copied["sha256"]
                    or item.source.stat().st_size != copied["size"]
                ):
                    raise CoordinatorMigrationError(
                        "A legacy source changed while migration files were being staged.",
                        safe_context={"source_name": item.source.name},
                        code="legacy_source_changed_during_migration",
                    )
            manifest_payload = {
                "format": "eitaa-bridge-legacy-account-migration-v1",
                "migration_id": migration_id,
                "messenger_account_id": messenger_account_id,
                "provider": "eitaa",
                "created_at": _now(),
                "source_file_count": len(copied_files),
                "source_total_bytes": sum(int(item["size"]) for item in copied_files),
                "files": copied_files,
            }
            canonical_manifest = json.dumps(
                manifest_payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            source_manifest_sha256 = hashlib.sha256(canonical_manifest).hexdigest()
            account_manifest = staging_account / "_migration" / "source-manifest.json"
            account_manifest.parent.mkdir(parents=True, exist_ok=True)
            account_manifest.write_text(
                json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            database = CoordinatorDatabase(staging_database)
            bootstrap = database.bootstrap_legacy_account(
                protected_phone=protected_phone,
                display_name=display_name,
                backup_name=backup_name,
                source_manifest_sha256=source_manifest_sha256,
                source_file_count=len(copied_files),
                source_total_bytes=sum(int(item["size"]) for item in copied_files),
                migration_id=migration_id,
                app_user_id=app_user_id,
                phone_account_id=phone_account_id,
                membership_id=membership_id,
                messenger_account_id=messenger_account_id,
            )
            self.accounts_root.mkdir(parents=True, exist_ok=True)
            os.replace(staging_account, final_account)
            self.coordinator_root.mkdir(parents=True, exist_ok=True)
            os.replace(staging_database, self.coordinator_database)
            activation_manifest = self.coordinator_root / "migrations" / f"{migration_id}.json"
            activation_manifest.parent.mkdir(parents=True, exist_ok=True)
            activation_manifest.write_text(
                json.dumps(
                    {
                        **manifest_payload,
                        "source_manifest_sha256": source_manifest_sha256,
                        "backup_name": Path(backup_name).name,
                        "backup_manifest_sha256": backup_manifest_sha256,
                        "activated_at": _now(),
                        "feature_enabled": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            CoordinatorDatabase(self.coordinator_database).mark_migration_activated(bootstrap)
            return MigrationResult(
                bootstrap=bootstrap,
                account_directory=final_account,
                coordinator_database=self.coordinator_database,
                manifest_file=activation_manifest,
                source_file_count=len(copied_files),
                source_total_bytes=sum(int(item["size"]) for item in copied_files),
                source_manifest_sha256=source_manifest_sha256,
            )
        except CoordinatorMigrationError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise CoordinatorMigrationError(
                "The legacy migration stopped with all existing legacy data preserved.",
                safe_context={"error_type": type(exc).__name__},
                code="legacy_migration_staging_failed",
            ) from exc

    def rollback(self, migration_id: str, *, operator_confirmed: bool) -> dict[str, object]:
        if not operator_confirmed:
            raise CoordinatorMigrationError(
                "The migration rollback was not explicitly confirmed.",
                code="migration_rollback_confirmation_required",
            )
        with _instance_lock(self.root / "runtime" / "office-launcher.lock") as acquired:
            if not acquired:
                raise CoordinatorMigrationError(
                    "The Office runtime owns the installation.",
                    code="migration_rollback_runtime_lock_unavailable",
                )
            return self._rollback_locked(migration_id)

    def _rollback_locked(self, migration_id: str) -> dict[str, object]:
        if self.config.features.multi_session.enabled:
            raise CoordinatorMigrationError(
                "The multi-session feature must be disabled before rollback.",
                code="migration_rollback_feature_enabled",
            )
        if self._runtime_active():
            raise CoordinatorMigrationError(
                "The legacy runtime must be stopped before rollback.",
                code="migration_rollback_runtime_active",
            )
        database = CoordinatorDatabase(self.coordinator_database)
        bootstrap = database.bootstrap_result_for_migration(migration_id)
        account = self.accounts_root / bootstrap.messenger_account_id
        if not account.is_dir():
            raise CoordinatorMigrationError(
                "The migrated account directory was not found.",
                code="migration_rollback_account_missing",
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        preserved_account = self.accounts_root / (
            f".rolled-back-{bootstrap.messenger_account_id}-{stamp}"
        )
        preserved_database = self.coordinator_root / (
            f"coordinator.sqlite3.rolled-back-{stamp}"
        )
        if preserved_account.exists() or preserved_database.exists():
            raise CoordinatorMigrationError(
                "A rollback preservation target already exists.",
                code="migration_rollback_target_collision",
            )
        try:
            os.replace(account, preserved_account)
            database.mark_migration_rolled_back(bootstrap)
            os.replace(self.coordinator_database, preserved_database)
        except OSError as exc:
            raise CoordinatorMigrationError(
                "Rollback stopped without deleting legacy or migrated data.",
                safe_context={"error_type": type(exc).__name__},
                code="migration_rollback_failed",
            ) from exc
        return {
            "migration_id": bootstrap.migration_id,
            "messenger_account_id": bootstrap.messenger_account_id,
            "preserved_account_directory_name": preserved_account.name,
            "preserved_database_name": preserved_database.name,
            "data_deleted": False,
            "feature_enabled": False,
        }

    def _migration_targets_clean(self) -> bool:
        if self.coordinator_database.exists():
            return False
        if self.coordinator_root.is_dir() and any(
            path.name.startswith("coordinator.sqlite3.staging-")
            for path in self.coordinator_root.iterdir()
        ):
            return False
        if not self.accounts_root.is_dir():
            return True
        for path in self.accounts_root.iterdir():
            if path.name.startswith(".rolled-back-"):
                continue
            if path.name.startswith(".staging-"):
                return False
            try:
                parsed = UUID(path.name)
            except ValueError:
                continue
            if parsed.version == 4 and str(parsed) == path.name:
                return False
        return True

    def _sources(self) -> Iterable[MigrationSource]:
        seen: set[PurePosixPath] = set()

        def add_file(source: Path, destination: str, *, required: bool = False) -> Iterable[MigrationSource]:
            selected = source.expanduser().resolve()
            if not _is_within(selected, self.root):
                if required:
                    raise CoordinatorPreflightError(
                        "A required legacy source is outside the installation.",
                        code="legacy_source_outside_installation",
                    )
                return ()
            if not selected.is_file():
                if required:
                    raise CoordinatorPreflightError(
                        "A required legacy source file is missing.",
                        safe_context={"source_name": selected.name},
                        code="legacy_source_missing",
                    )
                return ()
            target = PurePosixPath(destination)
            if target in seen:
                raise CoordinatorPreflightError(
                    "Two legacy sources map to the same account destination.",
                    code="legacy_source_destination_collision",
                )
            seen.add(target)
            return (MigrationSource(selected, target),)

        def add_directory(source: Path, destination: str) -> Iterable[MigrationSource]:
            selected = source.expanduser().resolve()
            if not _is_within(selected, self.root) or not selected.is_dir():
                return ()
            rows: list[MigrationSource] = []
            for path in sorted(selected.rglob("*")):
                if not path.is_file() or self._excluded_source(path):
                    continue
                target = PurePosixPath(destination) / path.relative_to(selected).as_posix()
                if target in seen:
                    raise CoordinatorPreflightError(
                        "Two legacy sources map to the same account destination.",
                        code="legacy_source_destination_collision",
                    )
                seen.add(target)
                rows.append(MigrationSource(path, target))
            return rows

        yield from add_file(
            self.config.core.session_file,
            ACCOUNT_SESSION_RELATIVE_PATH.as_posix(),
            required=True,
        )
        core = self.config.core.database_file
        yield from add_file(
            core,
            ACCOUNT_CORE_DATABASE_RELATIVE_PATH.as_posix(),
            required=True,
        )
        for suffix in ("-wal", "-shm"):
            yield from add_file(
                Path(str(core) + suffix),
                f"{ACCOUNT_CORE_DATABASE_RELATIVE_PATH.as_posix()}{suffix}",
            )
        yield from add_directory(
            self.config.core.media_directory,
            ACCOUNT_MEDIA_RELATIVE_PATH.as_posix(),
        )
        for source_name, destination in (
            (
                "content_index.sqlite3",
                ACCOUNT_CONTENT_INDEX_RELATIVE_PATH.as_posix(),
            ),
            (
                "sender_directory.sqlite3",
                ACCOUNT_SENDER_DIRECTORY_RELATIVE_PATH.as_posix(),
            ),
        ):
            source = self.data_root / source_name
            yield from add_file(source, destination)
            for suffix in ("-wal", "-shm"):
                yield from add_file(
                    Path(str(source) + suffix),
                    f"{destination}{suffix}",
                )
        yield from add_directory(
            self.data_root / "ui-peers",
            ACCOUNT_DIALOG_CATALOG_RELATIVE_PATH.parent.as_posix(),
        )
        yield from add_directory(
            self.data_root / "eitaa-contact-peers",
            ACCOUNT_CONTACT_PEERS_RELATIVE_PATH.as_posix(),
        )

    @staticmethod
    def _excluded_source(path: Path) -> bool:
        lowered = path.name.lower()
        return lowered in {"lock"} or lowered.endswith((".tmp", ".lock", ".part"))

    def _runtime_active(self) -> bool:
        state_file = self.root / "runtime" / "backend-state.json"
        if not state_file.is_file():
            return False
        try:
            payload = json.loads(state_file.read_text(encoding="utf-8"))
            pid = int(payload.get("pid") or 0)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return True
        return _process_alive(pid)

    @staticmethod
    def _valid_session_container(path: Path) -> bool:
        try:
            if not path.is_file() or path.stat().st_size <= 0:
                return False
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            return isinstance(payload, dict)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _sqlite_quick_check(path: Path) -> bool:
        if not path.is_file():
            return False
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=5.0)
            result = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            return result.lower() == "ok"
        except sqlite3.Error:
            return False
        finally:
            if connection is not None:
                connection.close()
