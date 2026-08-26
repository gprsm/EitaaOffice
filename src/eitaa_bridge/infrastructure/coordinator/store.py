"""Transactional coordinator database with safe bootstrap and append-only audit."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping
import unicodedata
from uuid import UUID, uuid4

from ...errors import CoordinatorConflictError, CoordinatorSchemaError
from ..diagnostics.redaction import redact
from .identity import ProtectedPhone
from .schema import (
    COORDINATOR_SCHEMA_VERSION,
    REQUIRED_TABLES,
    REQUIRED_TABLES_V1,
    REQUIRED_TABLES_V2,
    REQUIRED_TABLES_V3,
    REQUIRED_TABLES_V4,
    REQUIRED_TABLES_V5,
    REQUIRED_TABLES_V6,
    SCHEMA_CHECKSUMS,
    initial_schema_script,
    upgrade_schema_script,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INTEGRATION_KEY = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_MAX_SELF_SERVICE_MESSENGER_ACCOUNTS = 20
_AUTH_AUDIT_ACTION = re.compile(r"^eitaa\.auth\.[a-z0-9_.-]{1,80}$")
_AUTH_STATES = frozenset(
    {"absent", "challenge_pending", "authenticated", "expired", "revoked", "invalid"}
)
_AUTH_TRANSITIONS = {
    "absent": frozenset(
        {"absent", "challenge_pending", "authenticated", "invalid", "revoked"}
    ),
    "challenge_pending": frozenset(
        {"challenge_pending", "authenticated", "expired", "revoked", "invalid", "absent"}
    ),
    "authenticated": frozenset(
        {"authenticated", "challenge_pending", "revoked", "invalid", "absent"}
    ),
    "expired": frozenset(
        {"expired", "challenge_pending", "authenticated", "revoked", "invalid", "absent"}
    ),
    "revoked": frozenset({"revoked", "challenge_pending", "absent"}),
    "invalid": frozenset({"invalid", "challenge_pending", "revoked", "absent"}),
}
_UNSAFE_AUTH_METADATA_KEY_PARTS = (
    "phone",
    "token",
    "password",
    "secret",
    "code",
    "hash",
    "ciphertext",
    "imei",
)
_PROVIDER_ACCOUNT_KINDS = frozenset({"personal", "bot", "service", "test", "legacy"})
_PROVIDER_IMPLEMENTATION_STATES = frozenset(
    {"scaffold", "implemented", "contract_verified", "live_accepted"}
)
_PROVIDER_AUTHORIZATION_BASES = frozenset(
    {"official_api", "written_permission", "existing_accepted_integration", "test_only"}
)
_PROVIDER_AUTH_STAGE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_PROVIDER_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.]{1,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _new_uuid() -> str:
    return str(uuid4())


def _canonical_uuid(value: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise CoordinatorSchemaError(
            "An internal coordinator identifier is invalid.",
            code="coordinator_identifier_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise CoordinatorSchemaError(
            "An internal coordinator identifier is invalid.",
            code="coordinator_identifier_invalid",
        )
    return value


@dataclass(frozen=True, slots=True)
class LegacyBootstrapResult:
    migration_id: str
    app_user_id: str
    phone_account_id: str
    membership_id: str
    messenger_account_id: str

    def safe_summary(self) -> dict[str, str]:
        return {
            "migration_id": self.migration_id,
            "app_user_id": self.app_user_id,
            "phone_account_id": self.phone_account_id,
            "membership_id": self.membership_id,
            "messenger_account_id": self.messenger_account_id,
        }


@dataclass(frozen=True, slots=True)
class MessengerAccountRuntimeRecord:
    messenger_account_id: str
    phone_account_id: str
    provider: str
    lifecycle_state: str
    desired_worker_state: str
    auth_state: str
    session_generation: int
    storage_revision: int

    def safe_summary(self) -> dict[str, object]:
        return {
            "messenger_account_id": self.messenger_account_id,
            "phone_account_id": self.phone_account_id,
            "provider": self.provider,
            "lifecycle_state": self.lifecycle_state,
            "desired_worker_state": self.desired_worker_state,
            "auth_state": self.auth_state,
            "session_generation": self.session_generation,
            "storage_revision": self.storage_revision,
        }


@dataclass(frozen=True, slots=True)
class MessengerAccountOnboardingResult:
    messenger_account_id: str
    phone_account_id: str
    membership_id: str
    provider: str
    lifecycle_state: str
    auth_state: str
    created: bool
    phone_account_created: bool
    membership_created: bool

    def safe_summary(self) -> dict[str, object]:
        return {
            "messenger_account_id": self.messenger_account_id,
            "phone_account_id": self.phone_account_id,
            "membership_id": self.membership_id,
            "provider": self.provider,
            "lifecycle_state": self.lifecycle_state,
            "auth_state": self.auth_state,
            "created": self.created,
            "phone_account_created": self.phone_account_created,
            "membership_created": self.membership_created,
        }


@dataclass(frozen=True, slots=True)
class WorkerInstanceRecord:
    worker_instance_id: str
    messenger_account_id: str
    generation: int
    runtime_state: str
    process_id: int | None
    started_at: str
    last_heartbeat_at: str | None
    retry_not_before: str | None
    stopped_at: str | None
    exit_code: int | None
    safe_reason_code: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "worker_instance_id": self.worker_instance_id,
            "messenger_account_id": self.messenger_account_id,
            "generation": self.generation,
            "runtime_state": self.runtime_state,
            "process_id": self.process_id,
            "started_at": self.started_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "retry_not_before": self.retry_not_before,
            "stopped_at": self.stopped_at,
            "exit_code": self.exit_code,
            "safe_reason_code": self.safe_reason_code,
        }


@dataclass(frozen=True, slots=True)
class WorkerRecoveryDecision:
    worker_instance_id: str
    messenger_account_id: str
    restart_allowed: bool
    quarantined: bool
    crash_count: int
    retry_after_seconds: int
    retry_not_before: str
    safe_reason_code: str
    exit_code: int | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "worker_instance_id": self.worker_instance_id,
            "messenger_account_id": self.messenger_account_id,
            "restart_allowed": self.restart_allowed,
            "quarantined": self.quarantined,
            "crash_count": self.crash_count,
            "retry_after_seconds": self.retry_after_seconds,
            "retry_not_before": self.retry_not_before,
            "safe_reason_code": self.safe_reason_code,
            "exit_code": self.exit_code,
        }


@dataclass(frozen=True, slots=True)
class MessengerAccountPhoneIdentity:
    messenger_account_id: str
    phone_account_id: str
    provider: str
    protected_phone: ProtectedPhone

    def safe_summary(self) -> dict[str, str]:
        return {
            "messenger_account_id": self.messenger_account_id,
            "phone_account_id": self.phone_account_id,
            "provider": self.provider,
            "phone_hint": self.protected_phone.display_hint,
        }


@dataclass(frozen=True, slots=True)
class AppIntegrationRecord:
    integration_id: str
    integration_type: str
    integration_key: str
    display_name: str
    status: str

    def safe_summary(self) -> dict[str, str]:
        """Return metadata only; integration credentials never enter this model."""

        return {
            "integration_id": self.integration_id,
            "integration_type": self.integration_type,
            "integration_key": self.integration_key,
            "display_name": self.display_name,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ProviderRegistrationRecord:
    provider: str
    display_name: str
    account_kind: str
    implementation_state: str
    authorization_basis: str | None
    configured: bool
    runtime_enabled: bool
    onboarding_enabled: bool
    account_identity_kind: str | None
    auth_steps: tuple[str, ...]
    capabilities: tuple[str, ...]
    catalog_visible: bool
    extension_api_version: int
    status: str

    def safe_summary(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "account_kind": self.account_kind,
            "implementation_state": self.implementation_state,
            "authorization_basis": self.authorization_basis,
            "configured": self.configured,
            "runtime_enabled": self.runtime_enabled,
            "onboarding_enabled": self.onboarding_enabled,
            "account_identity_kind": self.account_identity_kind,
            "auth_steps": list(self.auth_steps),
            "capabilities": list(self.capabilities),
            "catalog_visible": self.catalog_visible,
            "extension_api_version": self.extension_api_version,
            "status": self.status,
        }


class CoordinatorDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > COORDINATOR_SCHEMA_VERSION:
                    raise CoordinatorSchemaError(
                        "The coordinator database is newer than this application.",
                        safe_context={
                            "database_version": version,
                            "supported_version": COORDINATOR_SCHEMA_VERSION,
                        },
                        code="coordinator_schema_newer",
                    )
                if version == 0:
                    connection.executescript(initial_schema_script())
                elif version < COORDINATOR_SCHEMA_VERSION:
                    self._verify_schema(connection, expected_version=version)
                    connection.executescript(upgrade_schema_script(version))
                self._verify_schema(connection)
        except CoordinatorSchemaError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise CoordinatorSchemaError(
                "The coordinator database could not be initialized.",
                safe_context={"error_type": type(exc).__name__, "file_name": self.path.name},
                code="coordinator_schema_initialize_failed",
            ) from exc

    @staticmethod
    def _validate_protected_phone(protected_phone: ProtectedPhone) -> None:
        if not _SHA256.fullmatch(protected_phone.fingerprint):
            raise CoordinatorSchemaError(
                "The protected phone fingerprint is invalid.",
                code="phone_fingerprint_invalid",
            )
        if not protected_phone.ciphertext or protected_phone.key_version <= 0:
            raise CoordinatorSchemaError(
                "The protected phone payload is invalid.",
                code="protected_phone_invalid",
            )
        hint_digits = re.findall(r"[0-9]", protected_phone.display_hint)
        if (
            not 4 <= len(protected_phone.display_hint) <= 32
            or len(hint_digits) > 15
            or not protected_phone.display_hint.startswith("+")
        ):
            raise CoordinatorSchemaError(
                "The protected phone display hint is unsafe.",
                code="phone_display_hint_invalid",
            )

    def bootstrap_legacy_account(
        self,
        *,
        protected_phone: ProtectedPhone,
        display_name: str,
        backup_name: str,
        source_manifest_sha256: str,
        source_file_count: int,
        source_total_bytes: int,
        migration_id: str | None = None,
        app_user_id: str | None = None,
        phone_account_id: str | None = None,
        membership_id: str | None = None,
        messenger_account_id: str | None = None,
    ) -> LegacyBootstrapResult:
        self.initialize()
        selected_name = str(display_name or "").strip()
        if not 1 <= len(selected_name) <= 120:
            raise CoordinatorSchemaError(
                "The bootstrap display name is invalid.",
                code="bootstrap_display_name_invalid",
            )
        self._validate_protected_phone(protected_phone)
        if not _SHA256.fullmatch(source_manifest_sha256):
            raise CoordinatorSchemaError(
                "The migration source manifest is invalid.",
                code="migration_manifest_invalid",
            )
        if source_file_count < 0 or source_total_bytes < 0:
            raise CoordinatorSchemaError(
                "The migration source counts are invalid.",
                code="migration_source_counts_invalid",
            )
        safe_backup_name = Path(str(backup_name)).name
        if not safe_backup_name or safe_backup_name != str(backup_name):
            raise CoordinatorSchemaError(
                "The migration backup name is invalid.",
                code="migration_backup_name_invalid",
            )
        result = LegacyBootstrapResult(
            migration_id=_canonical_uuid(migration_id) if migration_id else _new_uuid(),
            app_user_id=_canonical_uuid(app_user_id) if app_user_id else _new_uuid(),
            phone_account_id=_canonical_uuid(phone_account_id) if phone_account_id else _new_uuid(),
            membership_id=_canonical_uuid(membership_id) if membership_id else _new_uuid(),
            messenger_account_id=(
                _canonical_uuid(messenger_account_id) if messenger_account_id else _new_uuid()
            ),
        )
        now = _now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO app_users(
                        id,display_name,global_role,status,created_at,updated_at
                    ) VALUES(?,?,'admin','active',?,?)
                    """,
                    (result.app_user_id, selected_name, now, now),
                )
                connection.execute(
                    """
                    INSERT INTO phone_accounts(
                        id,phone_ciphertext,phone_key_version,phone_fingerprint,
                        display_hint,status,created_at,updated_at
                    ) VALUES(?,?,?,?,?,'active',?,?)
                    """,
                    (
                        result.phone_account_id,
                        protected_phone.ciphertext,
                        protected_phone.key_version,
                        protected_phone.fingerprint,
                        protected_phone.display_hint,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO phone_account_memberships(
                        id,app_user_id,phone_account_id,role,status,
                        created_by_app_user_id,created_at,updated_at
                    ) VALUES(?,?,?,'owner','active',?,?,?)
                    """,
                    (
                        result.membership_id,
                        result.app_user_id,
                        result.phone_account_id,
                        result.app_user_id,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO messenger_accounts(
                        id,phone_account_id,provider,label,lifecycle_state,
                        desired_worker_state,capability_revision,created_at,updated_at
                    ) VALUES(?,?,'eitaa','Legacy Eitaa account','created','stopped',0,?,?)
                    """,
                    (result.messenger_account_id, result.phone_account_id, now, now),
                )
                connection.execute(
                    """
                    INSERT INTO messenger_session_metadata(
                        messenger_account_id,auth_state,session_generation,storage_revision,
                        last_auth_transition_at,safe_reason_code,created_at,updated_at
                    ) VALUES(?,'absent',1,1,?,'legacy_session_copied_unverified',?,?)
                    """,
                    (result.messenger_account_id, now, now, now),
                )
                connection.execute(
                    """
                    INSERT INTO migration_runs(
                        id,migration_kind,status,backup_name,source_manifest_sha256,
                        source_file_count,source_total_bytes,messenger_account_id,
                        started_at,created_at,updated_at
                    ) VALUES(?,'legacy_single_eitaa_v1','verified',?,?,?,?,?,?,?,?)
                    """,
                    (
                        result.migration_id,
                        safe_backup_name,
                        source_manifest_sha256,
                        source_file_count,
                        source_total_bytes,
                        result.messenger_account_id,
                        now,
                        now,
                        now,
                    ),
                )
                self._append_audit(
                    connection,
                    actor_type="system",
                    actor_app_user_id=None,
                    actor_global_role=None,
                    action="migration.legacy.verified",
                    target_type="migration_run",
                    target_id=result.migration_id,
                    phone_account_id=result.phone_account_id,
                    messenger_account_id=result.messenger_account_id,
                    provider="eitaa",
                    result="succeeded",
                    reason_code="legacy_copy_hash_verified",
                    safe_metadata={
                        "source_file_count": source_file_count,
                        "source_total_bytes": source_total_bytes,
                        "session_auth_state": "absent",
                    },
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The legacy coordinator bootstrap transaction failed.",
                safe_context={"error_type": type(exc).__name__},
                code="coordinator_bootstrap_failed",
            ) from exc
        return result

    def mark_migration_activated(self, result: LegacyBootstrapResult) -> None:
        now = _now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE migration_runs
                    SET status='activated',completed_at=?,updated_at=?
                    WHERE id=? AND status='verified' AND messenger_account_id=?
                    """,
                    (now, now, result.migration_id, result.messenger_account_id),
                )
                if cursor.rowcount != 1:
                    raise CoordinatorSchemaError(
                        "The verified migration could not be activated.",
                        code="migration_activation_state_invalid",
                    )
                self._append_audit(
                    connection,
                    actor_type="system",
                    actor_app_user_id=None,
                    actor_global_role=None,
                    action="migration.legacy.activated",
                    target_type="migration_run",
                    target_id=result.migration_id,
                    phone_account_id=result.phone_account_id,
                    messenger_account_id=result.messenger_account_id,
                    provider="eitaa",
                    result="succeeded",
                    reason_code="atomic_layout_activation_complete",
                    safe_metadata={"feature_enabled": False},
                )
                connection.commit()
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The verified migration could not be activated.",
                safe_context={"error_type": type(exc).__name__},
                code="migration_activation_failed",
            ) from exc

    def mark_migration_rolled_back(
        self,
        result: LegacyBootstrapResult,
        *,
        reason_code: str = "operator_confirmed_rollback",
    ) -> None:
        now = _now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE migration_runs
                    SET status='rolled_back',completed_at=?,updated_at=?
                    WHERE id=? AND status IN ('verified','activated')
                      AND messenger_account_id=?
                    """,
                    (now, now, result.migration_id, result.messenger_account_id),
                )
                if cursor.rowcount != 1:
                    raise CoordinatorSchemaError(
                        "The migration cannot be rolled back from its current state.",
                        code="migration_rollback_state_invalid",
                    )
                self._append_audit(
                    connection,
                    actor_type="system",
                    actor_app_user_id=None,
                    actor_global_role=None,
                    action="migration.legacy.rolled_back",
                    target_type="migration_run",
                    target_id=result.migration_id,
                    phone_account_id=result.phone_account_id,
                    messenger_account_id=result.messenger_account_id,
                    provider="eitaa",
                    result="succeeded",
                    reason_code=reason_code,
                    safe_metadata={"feature_enabled": False, "data_deleted": False},
                )
                connection.commit()
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The migration rollback could not be recorded.",
                safe_context={"error_type": type(exc).__name__},
                code="migration_rollback_record_failed",
            ) from exc

    def bootstrap_result_for_migration(self, migration_id: str) -> LegacyBootstrapResult:
        selected_id = _canonical_uuid(migration_id)
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    mr.id AS migration_id,
                    mr.messenger_account_id,
                    ma.phone_account_id,
                    pam.id AS membership_id,
                    pam.app_user_id
                FROM migration_runs mr
                JOIN messenger_accounts ma ON ma.id=mr.messenger_account_id
                JOIN phone_account_memberships pam
                  ON pam.phone_account_id=ma.phone_account_id
                 AND pam.role='owner' AND pam.status='active'
                WHERE mr.id=?
                ORDER BY pam.created_at
                LIMIT 1
                """,
                (selected_id,),
            ).fetchone()
            if row is None:
                raise CoordinatorSchemaError(
                    "The migration record was not found.",
                    code="migration_not_found",
                )
            return LegacyBootstrapResult(
                migration_id=str(row["migration_id"]),
                app_user_id=str(row["app_user_id"]),
                phone_account_id=str(row["phone_account_id"]),
                membership_id=str(row["membership_id"]),
                messenger_account_id=str(row["messenger_account_id"]),
            )

    def safe_summary(self) -> dict[str, Any]:
        self.initialize()
        with self._connect() as connection:
            migration = connection.execute(
                """
                SELECT id,status,messenger_account_id,source_file_count,source_total_bytes
                FROM migration_runs ORDER BY created_at DESC LIMIT 1
                """
            ).fetchone()
            counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in (
                    "app_users",
                    "phone_accounts",
                    "phone_account_memberships",
                    "messenger_accounts",
                    "audit_events",
                )
            }
            return {
                "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
                "counts": counts,
                "latest_migration": dict(migration) if migration is not None else None,
            }

    def read_only_safe_summary(self) -> dict[str, Any]:
        """Inspect an existing coordinator database without upgrading or writing it."""

        if not self.path.is_file():
            raise CoordinatorSchemaError(
                "The coordinator database was not found.",
                safe_context={"file_name": self.path.name},
                code="coordinator_database_not_found",
            )
        for suffix in ("-wal", "-journal"):
            sidecar = Path(f"{self.path}{suffix}")
            try:
                if sidecar.is_file() and sidecar.stat().st_size > 0:
                    raise CoordinatorSchemaError(
                        "The coordinator database has uncheckpointed runtime state.",
                        safe_context={"sidecar_kind": suffix.removeprefix("-")},
                        code="coordinator_read_only_sidecar_present",
                    )
            except OSError as exc:
                raise CoordinatorSchemaError(
                    "The coordinator database sidecar state could not be inspected.",
                    safe_context={"error_type": type(exc).__name__},
                    code="coordinator_read_only_sidecar_check_failed",
                ) from exc
        try:
            uri = f"{self.path.as_uri()}?mode=ro&immutable=1"
            with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA query_only=ON")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version < 1 or version > COORDINATOR_SCHEMA_VERSION:
                    raise CoordinatorSchemaError(
                        "The coordinator schema version is unsupported.",
                        safe_context={
                            "database_version": version,
                            "supported_version": COORDINATOR_SCHEMA_VERSION,
                        },
                        code="coordinator_schema_version_invalid",
                    )
                self._verify_schema(connection, expected_version=version)
                migration = connection.execute(
                    """
                    SELECT id,status,messenger_account_id,source_file_count,source_total_bytes
                    FROM migration_runs ORDER BY created_at DESC LIMIT 1
                    """
                ).fetchone()
                counts = {
                    table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for table in (
                        "app_users",
                        "phone_accounts",
                        "phone_account_memberships",
                        "messenger_accounts",
                        "audit_events",
                    )
                }
                return {
                    "schema_version": version,
                    "schema_upgrade_required": version < COORDINATOR_SCHEMA_VERSION,
                    "counts": counts,
                    "latest_migration": dict(migration) if migration is not None else None,
                }
        except CoordinatorSchemaError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise CoordinatorSchemaError(
                "The coordinator database could not be inspected read-only.",
                safe_context={"error_type": type(exc).__name__, "file_name": self.path.name},
                code="coordinator_read_only_inspection_failed",
            ) from exc

    def messenger_account_runtime(
        self,
        messenger_account_id: str,
    ) -> MessengerAccountRuntimeRecord:
        """Load only safe runtime metadata for one canonical account."""

        selected_id = _canonical_uuid(messenger_account_id)
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    ma.id AS messenger_account_id,
                    ma.phone_account_id,
                    ma.provider,
                    ma.lifecycle_state,
                    ma.desired_worker_state,
                    sm.auth_state,
                    sm.session_generation,
                    sm.storage_revision
                FROM messenger_accounts ma
                JOIN messenger_session_metadata sm
                  ON sm.messenger_account_id=ma.id
                WHERE ma.id=?
                """,
                (selected_id,),
            ).fetchone()
        if row is None:
            raise CoordinatorSchemaError(
                "The MessengerAccount runtime record was not found.",
                code="messenger_account_runtime_not_found",
            )
        return MessengerAccountRuntimeRecord(
            messenger_account_id=str(row["messenger_account_id"]),
            phone_account_id=str(row["phone_account_id"]),
            provider=str(row["provider"]),
            lifecycle_state=str(row["lifecycle_state"]),
            desired_worker_state=str(row["desired_worker_state"]),
            auth_state=str(row["auth_state"]),
            session_generation=int(row["session_generation"]),
            storage_revision=int(row["storage_revision"]),
        )

    def messenger_account_phone_identity(
        self,
        messenger_account_id: str,
    ) -> MessengerAccountPhoneIdentity:
        """Load the protected PhoneAccount identity owned by one messenger account."""

        selected_id = _canonical_uuid(messenger_account_id)
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    ma.id AS messenger_account_id,
                    ma.phone_account_id,
                    ma.provider,
                    pa.phone_ciphertext,
                    pa.phone_key_version,
                    pa.phone_fingerprint,
                    pa.display_hint
                FROM messenger_accounts ma
                JOIN phone_accounts pa ON pa.id=ma.phone_account_id
                WHERE ma.id=? AND pa.status='active'
                """,
                (selected_id,),
            ).fetchone()
        if row is None:
            raise CoordinatorSchemaError(
                "The MessengerAccount phone identity was not found.",
                code="messenger_account_phone_identity_not_found",
            )
        return MessengerAccountPhoneIdentity(
            messenger_account_id=str(row["messenger_account_id"]),
            phone_account_id=str(row["phone_account_id"]),
            provider=str(row["provider"]),
            protected_phone=ProtectedPhone(
                ciphertext=bytes(row["phone_ciphertext"]),
                key_version=int(row["phone_key_version"]),
                fingerprint=str(row["phone_fingerprint"]),
                display_hint=str(row["display_hint"]),
            ),
        )

    def replace_messenger_account_phone_identity(
        self,
        messenger_account_id: str,
        *,
        protected_phone: ProtectedPhone,
        actor_app_user_id: str | None,
        actor_global_role: str | None,
        request_id: str | None = None,
    ) -> MessengerAccountPhoneIdentity:
        """Replace one unrecoverable protected identity with an audited value."""

        selected_id = _canonical_uuid(messenger_account_id)
        actor_id = _canonical_uuid(actor_app_user_id) if actor_app_user_id else None
        if actor_id is not None and actor_global_role != "admin":
            raise CoordinatorSchemaError(
                "Only an administrator can recover a protected phone identity.",
                code="phone_identity_recovery_admin_required",
            )
        if not _SHA256.fullmatch(protected_phone.fingerprint):
            raise CoordinatorSchemaError(
                "The replacement phone fingerprint is invalid.",
                code="phone_fingerprint_invalid",
            )
        if not protected_phone.ciphertext or protected_phone.key_version <= 0:
            raise CoordinatorSchemaError(
                "The replacement protected phone payload is invalid.",
                code="protected_phone_invalid",
            )
        hint_digits = re.findall(r"[0-9]", protected_phone.display_hint)
        if (
            not 4 <= len(protected_phone.display_hint) <= 32
            or len(hint_digits) > 15
            or not protected_phone.display_hint.startswith("+")
        ):
            raise CoordinatorSchemaError(
                "The replacement phone display hint is unsafe.",
                code="phone_display_hint_invalid",
            )

        self.initialize()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                account_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM phone_accounts WHERE status='active'"
                    ).fetchone()[0]
                )
                if account_count != 1:
                    raise CoordinatorSchemaError(
                        "Protected identity recovery currently requires exactly one active phone account.",
                        safe_context={"active_phone_account_count": account_count},
                        code="phone_identity_recovery_multi_account_unsupported",
                    )
                row = connection.execute(
                    """
                    SELECT ma.phone_account_id,ma.provider,ma.lifecycle_state,sm.auth_state
                    FROM messenger_accounts ma
                    JOIN messenger_session_metadata sm ON sm.messenger_account_id=ma.id
                    WHERE ma.id=?
                    """,
                    (selected_id,),
                ).fetchone()
                if row is None:
                    raise CoordinatorSchemaError(
                        "The MessengerAccount phone identity was not found.",
                        code="messenger_account_phone_identity_not_found",
                    )
                if str(row["provider"]) != "eitaa":
                    raise CoordinatorSchemaError(
                        "Protected identity recovery is unavailable for this provider.",
                        code="phone_identity_recovery_provider_unsupported",
                    )
                if str(row["lifecycle_state"]) == "archived":
                    raise CoordinatorSchemaError(
                        "An archived account identity cannot be recovered.",
                        code="phone_identity_recovery_account_archived",
                    )
                if str(row["auth_state"]) != "absent":
                    raise CoordinatorSchemaError(
                        "The active provider session must be archived before identity recovery.",
                        safe_context={"auth_state": str(row["auth_state"])},
                        code="phone_identity_recovery_session_present",
                    )
                now = _now()
                connection.execute(
                    """
                    UPDATE phone_accounts
                    SET phone_ciphertext=?,phone_key_version=?,phone_fingerprint=?,
                        display_hint=?,updated_at=?
                    WHERE id=? AND status='active'
                    """,
                    (
                        protected_phone.ciphertext,
                        protected_phone.key_version,
                        protected_phone.fingerprint,
                        protected_phone.display_hint,
                        now,
                        str(row["phone_account_id"]),
                    ),
                )
                self._append_audit(
                    connection,
                    actor_type="app_user" if actor_id else "system",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_global_role if actor_id else None,
                    action="eitaa.auth.phone_identity.recovered",
                    target_type="phone_account",
                    target_id=str(row["phone_account_id"]),
                    phone_account_id=str(row["phone_account_id"]),
                    messenger_account_id=selected_id,
                    provider=str(row["provider"]),
                    result="succeeded",
                    reason_code="dpapi_scope_recovery",
                    safe_metadata={
                        "key_version": protected_phone.key_version,
                        "machine_scope": True,
                    },
                    request_id=request_id,
                )
                connection.commit()
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The protected phone identity could not be replaced.",
                safe_context={"error_type": type(exc).__name__},
                code="phone_identity_recovery_failed",
            ) from exc
        return self.messenger_account_phone_identity(selected_id)

    def onboard_messenger_account(
        self,
        *,
        actor_app_user_id: str,
        actor_global_role: str,
        protected_phone: ProtectedPhone,
        provider: str,
        label: str | None,
        request_id: str | None = None,
    ) -> MessengerAccountOnboardingResult:
        """Create or safely reuse an AppUser-owned MessengerAccount.

        The client never supplies an internal identifier or filesystem path.
        ``BEGIN IMMEDIATE`` plus database uniqueness makes retries and races
        idempotent for the same owner without exposing whether another owner
        already registered the protected identity.
        """

        actor_id = _canonical_uuid(actor_app_user_id)
        if actor_global_role not in {"admin", "user"}:
            raise CoordinatorSchemaError(
                "The AppUser role is invalid.",
                code="messenger_account_actor_role_invalid",
            )
        selected_provider = str(provider or "").strip().lower()
        if not _PROVIDER_ID.fullmatch(selected_provider):
            raise CoordinatorSchemaError(
                "The messaging provider is invalid.",
                code="messenger_account_provider_invalid",
            )
        selected_label = str(label or "").strip() or None
        if selected_label is not None and (
            len(selected_label) > 120
            or any(
                unicodedata.category(character) in {"Cc", "Cs"}
                for character in selected_label
            )
        ):
            raise CoordinatorSchemaError(
                "The messaging account label is invalid.",
                code="messenger_account_label_invalid",
            )
        self._validate_protected_phone(protected_phone)
        self.initialize()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                provider_registration = connection.execute(
                    """
                    SELECT onboarding_enabled,status
                    FROM provider_registrations WHERE provider=?
                    """,
                    (selected_provider,),
                ).fetchone()
                if (
                    provider_registration is None
                    or str(provider_registration["status"]) != "active"
                    or not bool(provider_registration["onboarding_enabled"])
                ):
                    raise CoordinatorSchemaError(
                        "Account onboarding is unavailable for this provider.",
                        safe_context={"provider": selected_provider},
                        code="provider_onboarding_unavailable",
                    )
                actor = connection.execute(
                    "SELECT status,global_role FROM app_users WHERE id=?",
                    (actor_id,),
                ).fetchone()
                if (
                    actor is None
                    or str(actor["status"]) != "active"
                    or str(actor["global_role"]) != actor_global_role
                ):
                    raise CoordinatorSchemaError(
                        "The AppUser account is not active.",
                        code="messenger_account_actor_inactive",
                    )

                phone_row = connection.execute(
                    "SELECT id,status FROM phone_accounts WHERE phone_fingerprint=?",
                    (protected_phone.fingerprint,),
                ).fetchone()
                phone_created = phone_row is None
                membership_created = False
                now = _now()
                if phone_row is None:
                    owned_count = int(
                        connection.execute(
                            """
                            SELECT COUNT(*)
                            FROM messenger_accounts ma
                            JOIN phone_account_memberships pm
                              ON pm.phone_account_id=ma.phone_account_id
                            WHERE pm.app_user_id=? AND pm.role='owner'
                              AND pm.status='active' AND ma.lifecycle_state<>'archived'
                            """,
                            (actor_id,),
                        ).fetchone()[0]
                    )
                    if owned_count >= _MAX_SELF_SERVICE_MESSENGER_ACCOUNTS:
                        self._append_audit(
                            connection,
                            actor_type="app_user",
                            actor_app_user_id=actor_id,
                            actor_global_role=actor_global_role,
                            action="messenger_account.onboarding.rejected",
                            target_type="messenger_account_onboarding",
                            target_id=None,
                            phone_account_id=None,
                            messenger_account_id=None,
                            provider=selected_provider,
                            result="rejected",
                            reason_code="self_service_limit_reached",
                            safe_metadata={"limit": _MAX_SELF_SERVICE_MESSENGER_ACCOUNTS},
                            request_id=request_id,
                        )
                        connection.commit()
                        raise CoordinatorConflictError(
                            "The self-service messaging account limit was reached.",
                            code="messenger_account_self_service_limit_reached",
                        )
                    phone_account_id = _new_uuid()
                    membership_id = _new_uuid()
                    connection.execute(
                        """
                        INSERT INTO phone_accounts(
                            id,phone_ciphertext,phone_key_version,phone_fingerprint,
                            display_hint,status,created_at,updated_at
                        ) VALUES(?,?,?,?,?,'active',?,?)
                        """,
                        (
                            phone_account_id,
                            protected_phone.ciphertext,
                            protected_phone.key_version,
                            protected_phone.fingerprint,
                            protected_phone.display_hint,
                            now,
                            now,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO phone_account_memberships(
                            id,app_user_id,phone_account_id,role,status,
                            created_by_app_user_id,created_at,updated_at
                        ) VALUES(?,?,?,'owner','active',?,?,?)
                        """,
                        (
                            membership_id,
                            actor_id,
                            phone_account_id,
                            actor_id,
                            now,
                            now,
                        ),
                    )
                    membership_created = True
                else:
                    phone_account_id = str(phone_row["id"])
                    membership = connection.execute(
                        """
                        SELECT id,role,status FROM phone_account_memberships
                        WHERE app_user_id=? AND phone_account_id=?
                        """,
                        (actor_id, phone_account_id),
                    ).fetchone()
                    if (
                        str(phone_row["status"]) != "active"
                        or membership is None
                        or str(membership["status"]) != "active"
                        or str(membership["role"]) != "owner"
                    ):
                        self._append_audit(
                            connection,
                            actor_type="app_user",
                            actor_app_user_id=actor_id,
                            actor_global_role=actor_global_role,
                            action="messenger_account.onboarding.rejected",
                            target_type="messenger_account_onboarding",
                            target_id=None,
                            phone_account_id=None,
                            messenger_account_id=None,
                            provider=selected_provider,
                            result="rejected",
                            reason_code="identity_unavailable",
                            safe_metadata={"identity_disclosed": False},
                            request_id=request_id,
                        )
                        connection.commit()
                        raise CoordinatorConflictError(
                            "This account identity cannot be registered.",
                            code="messenger_account_identity_unavailable",
                        )
                    membership_id = str(membership["id"])

                existing = connection.execute(
                    """
                    SELECT ma.id,ma.lifecycle_state,sm.auth_state
                    FROM messenger_accounts ma
                    JOIN messenger_session_metadata sm ON sm.messenger_account_id=ma.id
                    WHERE ma.phone_account_id=? AND ma.provider=?
                    """,
                    (phone_account_id, selected_provider),
                ).fetchone()
                if existing is not None:
                    self._append_audit(
                        connection,
                        actor_type="app_user",
                        actor_app_user_id=actor_id,
                        actor_global_role=actor_global_role,
                        action="messenger_account.onboarding.reused",
                        target_type="messenger_account",
                        target_id=str(existing["id"]),
                        phone_account_id=phone_account_id,
                        messenger_account_id=str(existing["id"]),
                        provider=selected_provider,
                        result="succeeded",
                        reason_code="idempotent_retry",
                        safe_metadata={"created": False},
                        request_id=request_id,
                    )
                    connection.commit()
                    return MessengerAccountOnboardingResult(
                        messenger_account_id=str(existing["id"]),
                        phone_account_id=phone_account_id,
                        membership_id=membership_id,
                        provider=selected_provider,
                        lifecycle_state=str(existing["lifecycle_state"]),
                        auth_state=str(existing["auth_state"]),
                        created=False,
                        phone_account_created=False,
                        membership_created=False,
                    )

                owned_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM messenger_accounts ma
                        JOIN phone_account_memberships pm
                          ON pm.phone_account_id=ma.phone_account_id
                        WHERE pm.app_user_id=? AND pm.role='owner' AND pm.status='active'
                          AND ma.lifecycle_state<>'archived'
                        """,
                        (actor_id,),
                    ).fetchone()[0]
                )
                if owned_count >= _MAX_SELF_SERVICE_MESSENGER_ACCOUNTS:
                    self._append_audit(
                        connection,
                        actor_type="app_user",
                        actor_app_user_id=actor_id,
                        actor_global_role=actor_global_role,
                        action="messenger_account.onboarding.rejected",
                        target_type="messenger_account_onboarding",
                        target_id=None,
                        phone_account_id=None,
                        messenger_account_id=None,
                        provider=selected_provider,
                        result="rejected",
                        reason_code="self_service_limit_reached",
                        safe_metadata={"limit": _MAX_SELF_SERVICE_MESSENGER_ACCOUNTS},
                        request_id=request_id,
                    )
                    connection.commit()
                    raise CoordinatorConflictError(
                        "The self-service messaging account limit was reached.",
                        code="messenger_account_self_service_limit_reached",
                    )

                messenger_account_id = _new_uuid()
                connection.execute(
                    """
                    INSERT INTO messenger_accounts(
                        id,phone_account_id,provider,label,lifecycle_state,
                        desired_worker_state,capability_revision,created_at,updated_at
                    ) VALUES(?,?,?,?,'created','stopped',0,?,?)
                    """,
                    (
                        messenger_account_id,
                        phone_account_id,
                        selected_provider,
                        selected_label,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO messenger_session_metadata(
                        messenger_account_id,auth_state,session_generation,
                        storage_revision,last_auth_transition_at,safe_reason_code,
                        created_at,updated_at
                    ) VALUES(?,'absent',1,1,?,'account_onboarding_created',?,?)
                    """,
                    (messenger_account_id, now, now, now),
                )
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_global_role,
                    action="messenger_account.onboarding.created",
                    target_type="messenger_account",
                    target_id=messenger_account_id,
                    phone_account_id=phone_account_id,
                    messenger_account_id=messenger_account_id,
                    provider=selected_provider,
                    result="succeeded",
                    reason_code="self_service_onboarding",
                    safe_metadata={
                        "identity_record_created": phone_created,
                        "owner_membership_created": membership_created,
                    },
                    request_id=request_id,
                )
                connection.commit()
                return MessengerAccountOnboardingResult(
                    messenger_account_id=messenger_account_id,
                    phone_account_id=phone_account_id,
                    membership_id=membership_id,
                    provider=selected_provider,
                    lifecycle_state="created",
                    auth_state="absent",
                    created=True,
                    phone_account_created=phone_created,
                    membership_created=membership_created,
                )
        except (CoordinatorConflictError, CoordinatorSchemaError):
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The messaging account could not be registered.",
                safe_context={"error_type": type(exc).__name__},
                code="messenger_account_onboarding_failed",
            ) from exc

    def list_accessible_messenger_accounts(
        self,
        *,
        app_user_id: str,
        global_role: str,
    ) -> list[dict[str, object]]:
        """Return safe account cards visible to one active AppUser."""

        actor_id = _canonical_uuid(app_user_id)
        if global_role not in {"admin", "user"}:
            raise CoordinatorSchemaError(
                "The AppUser role is invalid.",
                code="messenger_account_actor_role_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            actor = connection.execute(
                "SELECT status,global_role FROM app_users WHERE id=?",
                (actor_id,),
            ).fetchone()
            if (
                actor is None
                or str(actor["status"]) != "active"
                or str(actor["global_role"]) != global_role
            ):
                raise CoordinatorSchemaError(
                    "The AppUser account is not active.",
                    code="messenger_account_actor_inactive",
                )
            if global_role == "admin":
                rows = connection.execute(
                    self._accessible_accounts_query(admin=True),
                    (actor_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    self._accessible_accounts_query(admin=False),
                    (actor_id,),
                ).fetchall()
        return [self._safe_account_card(row, global_role=global_role) for row in rows]

    def reconcile_provider_registrations(
        self,
        registrations: Collection[Mapping[str, object]],
    ) -> dict[str, object]:
        """Persist safe allowlisted metadata without deleting historical providers."""

        normalized: dict[str, dict[str, object]] = {}
        for registration in registrations:
            item = self._normalize_provider_registration(registration)
            provider = str(item["provider"])
            if provider in normalized:
                raise CoordinatorSchemaError(
                    "The provider registration is duplicated.",
                    safe_context={"provider": provider},
                    code="provider_registration_duplicate",
                )
            normalized[provider] = item
        self.initialize()
        created = updated = unchanged = 0
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = _now()
            for provider in sorted(normalized):
                item = normalized[provider]
                auth_steps_json = json.dumps(
                    list(item["auth_steps"]),
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                capabilities_json = json.dumps(
                    list(item["capabilities"]),
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                values = (
                    str(item["display_name"]),
                    str(item["account_kind"]),
                    str(item["implementation_state"]),
                    item["authorization_basis"],
                    int(bool(item["configured"])),
                    int(bool(item["runtime_enabled"])),
                    int(bool(item["onboarding_enabled"])),
                    item["account_identity_kind"],
                    auth_steps_json,
                    capabilities_json,
                    int(bool(item["catalog_visible"])),
                    int(item["extension_api_version"]),
                    "active",
                )
                existing = connection.execute(
                    """
                    SELECT display_name,account_kind,implementation_state,
                           authorization_basis,configured,runtime_enabled,
                           onboarding_enabled,account_identity_kind,auth_steps_json,
                           capabilities_json,catalog_visible,extension_api_version,status
                    FROM provider_registrations WHERE provider=?
                    """,
                    (provider,),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO provider_registrations(
                            provider,display_name,account_kind,implementation_state,
                            authorization_basis,configured,runtime_enabled,onboarding_enabled,
                            account_identity_kind,auth_steps_json,capabilities_json,
                            catalog_visible,extension_api_version,status,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (provider, *values, now, now),
                    )
                    action = "provider_registration.created"
                    created += 1
                elif tuple(existing) == values:
                    unchanged += 1
                    continue
                else:
                    connection.execute(
                        """
                        UPDATE provider_registrations
                        SET display_name=?,account_kind=?,implementation_state=?,
                            authorization_basis=?,configured=?,runtime_enabled=?,
                            onboarding_enabled=?,account_identity_kind=?,auth_steps_json=?,
                            capabilities_json=?,catalog_visible=?,extension_api_version=?,
                            status=?,updated_at=?
                        WHERE provider=?
                        """,
                        (*values, now, provider),
                    )
                    action = "provider_registration.updated"
                    updated += 1
                self._append_audit(
                    connection,
                    actor_type="system",
                    actor_app_user_id=None,
                    actor_global_role=None,
                    action=action,
                    target_type="provider_registration",
                    target_id=provider,
                    phone_account_id=None,
                    messenger_account_id=None,
                    provider=provider,
                    result="succeeded",
                    reason_code="provider_registry_reconciled",
                    safe_metadata={
                        "account_kind": item["account_kind"],
                        "implementation_state": item["implementation_state"],
                        "runtime_enabled": item["runtime_enabled"],
                        "onboarding_enabled": item["onboarding_enabled"],
                        "capability_count": len(item["capabilities"]),
                    },
                )
            connection.commit()
        return {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "provider_count": len(normalized),
        }

    def list_provider_registrations(self) -> tuple[ProviderRegistrationRecord, ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM provider_registrations ORDER BY provider"
            ).fetchall()
        return tuple(self._provider_registration_record(row) for row in rows)

    def provider_registration(self, provider: str) -> ProviderRegistrationRecord:
        selected = str(provider or "").strip().lower()
        if not _PROVIDER_ID.fullmatch(selected):
            raise CoordinatorSchemaError(
                "The provider registration identifier is invalid.",
                code="provider_registration_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM provider_registrations WHERE provider=?",
                (selected,),
            ).fetchone()
        if row is None:
            raise CoordinatorSchemaError(
                "The provider registration was not found.",
                safe_context={"provider": selected},
                code="provider_registration_not_found",
            )
        return self._provider_registration_record(row)

    def messenger_capability_observations(
        self,
        messenger_account_id: str,
    ) -> dict[str, dict[str, object]]:
        selected_id = _canonical_uuid(messenger_account_id)
        self.initialize()
        with self._connect() as connection:
            account = connection.execute(
                "SELECT 1 FROM messenger_accounts WHERE id=?",
                (selected_id,),
            ).fetchone()
            if account is None:
                raise CoordinatorSchemaError(
                    "The MessengerAccount capability target was not found.",
                    code="messenger_account_runtime_not_found",
                )
            rows = connection.execute(
                """
                SELECT capability,status,reason_code,constraints_json,revision,observed_at
                FROM messenger_capabilities
                WHERE messenger_account_id=? ORDER BY capability
                """,
                (selected_id,),
            ).fetchall()
        return {
            str(row["capability"]): {
                "status": str(row["status"]),
                "reason_code": (
                    str(row["reason_code"]) if row["reason_code"] is not None else None
                ),
                "constraints_present": row["constraints_json"] not in (None, "", "{}"),
                "revision": int(row["revision"]),
                "observed_at": str(row["observed_at"]),
            }
            for row in rows
        }

    @staticmethod
    def _normalize_provider_registration(
        registration: Mapping[str, object],
    ) -> dict[str, object]:
        provider = str(registration.get("provider") or "").strip().lower()
        display_name = str(registration.get("display_name") or "").strip()
        account_kind = str(registration.get("account_kind") or "").strip().lower()
        implementation_state = str(
            registration.get("implementation_state") or ""
        ).strip().lower()
        raw_basis = registration.get("authorization_basis")
        authorization_basis = str(raw_basis).strip().lower() if raw_basis else None
        identity_value = registration.get("account_identity_kind")
        account_identity_kind = (
            str(identity_value).strip().lower() if identity_value else None
        )
        if not _PROVIDER_ID.fullmatch(provider):
            raise CoordinatorSchemaError(
                "The provider registration identifier is invalid.",
                code="provider_registration_invalid",
            )
        if (
            not display_name
            or len(display_name) > 64
            or any(unicodedata.category(character) in {"Cc", "Cs"} for character in display_name)
            or account_kind not in _PROVIDER_ACCOUNT_KINDS
            or implementation_state not in _PROVIDER_IMPLEMENTATION_STATES
            or (
                authorization_basis is not None
                and authorization_basis not in _PROVIDER_AUTHORIZATION_BASES
            )
        ):
            raise CoordinatorSchemaError(
                "The provider registration metadata is invalid.",
                safe_context={"provider": provider},
                code="provider_registration_invalid",
            )
        boolean_fields: dict[str, bool] = {}
        for name in (
            "configured",
            "runtime_enabled",
            "onboarding_enabled",
            "catalog_visible",
        ):
            value = registration.get(name)
            if not isinstance(value, bool):
                raise CoordinatorSchemaError(
                    "The provider registration state is invalid.",
                    safe_context={"provider": provider, "field": name},
                    code="provider_registration_invalid",
                )
            boolean_fields[name] = value
        extension_api_version = registration.get("extension_api_version")
        if (
            isinstance(extension_api_version, bool)
            or not isinstance(extension_api_version, int)
            or extension_api_version <= 0
        ):
            raise CoordinatorSchemaError(
                "The provider extension version is invalid.",
                safe_context={"provider": provider},
                code="provider_registration_invalid",
            )
        raw_steps = registration.get("auth_steps")
        raw_capabilities = registration.get("capabilities")
        if not isinstance(raw_steps, (tuple, list)) or not isinstance(
            raw_capabilities, (tuple, list)
        ):
            raise CoordinatorSchemaError(
                "The provider registration contract is invalid.",
                safe_context={"provider": provider},
                code="provider_registration_invalid",
            )
        auth_steps = tuple(str(value) for value in raw_steps)
        capabilities = tuple(sorted({str(value) for value in raw_capabilities}))
        if (
            len(auth_steps) > 10
            or len(capabilities) > 64
            or any(not _PROVIDER_AUTH_STAGE.fullmatch(value) for value in auth_steps)
            or any(not _PROVIDER_CAPABILITY.fullmatch(value) for value in capabilities)
            or (
                account_identity_kind is not None
                and not _PROVIDER_AUTH_STAGE.fullmatch(account_identity_kind)
            )
        ):
            raise CoordinatorSchemaError(
                "The provider registration contract is invalid.",
                safe_context={"provider": provider},
                code="provider_registration_invalid",
            )
        if boolean_fields["configured"] and (
            implementation_state == "scaffold" or authorization_basis is None
        ):
            raise CoordinatorSchemaError(
                "The provider registration is not authorized.",
                safe_context={"provider": provider},
                code="provider_activation_not_authorized",
            )
        if boolean_fields["runtime_enabled"] and (
            not boolean_fields["configured"]
            or implementation_state not in {"contract_verified", "live_accepted"}
        ):
            raise CoordinatorSchemaError(
                "The provider registration is not verified.",
                safe_context={"provider": provider},
                code="provider_activation_not_verified",
            )
        if boolean_fields["onboarding_enabled"] and (
            not boolean_fields["runtime_enabled"]
            or account_identity_kind is None
            or not auth_steps
        ):
            raise CoordinatorSchemaError(
                "The provider onboarding contract is incomplete.",
                safe_context={"provider": provider},
                code="provider_onboarding_contract_incomplete",
            )
        return {
            "provider": provider,
            "display_name": display_name,
            "account_kind": account_kind,
            "implementation_state": implementation_state,
            "authorization_basis": authorization_basis,
            **boolean_fields,
            "account_identity_kind": account_identity_kind,
            "auth_steps": auth_steps,
            "capabilities": capabilities,
            "extension_api_version": extension_api_version,
        }

    @staticmethod
    def _provider_registration_record(row: sqlite3.Row) -> ProviderRegistrationRecord:
        try:
            auth_steps = tuple(str(value) for value in json.loads(str(row["auth_steps_json"])))
            capabilities = tuple(
                str(value) for value in json.loads(str(row["capabilities_json"]))
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CoordinatorSchemaError(
                "The persisted provider registration is invalid.",
                code="provider_registration_corrupt",
            ) from exc
        return ProviderRegistrationRecord(
            provider=str(row["provider"]),
            display_name=str(row["display_name"]),
            account_kind=str(row["account_kind"]),
            implementation_state=str(row["implementation_state"]),
            authorization_basis=(
                str(row["authorization_basis"])
                if row["authorization_basis"] is not None
                else None
            ),
            configured=bool(row["configured"]),
            runtime_enabled=bool(row["runtime_enabled"]),
            onboarding_enabled=bool(row["onboarding_enabled"]),
            account_identity_kind=(
                str(row["account_identity_kind"])
                if row["account_identity_kind"] is not None
                else None
            ),
            auth_steps=auth_steps,
            capabilities=capabilities,
            catalog_visible=bool(row["catalog_visible"]),
            extension_api_version=int(row["extension_api_version"]),
            status=str(row["status"]),
        )

    def reconcile_wordpress_integrations(
        self,
        sites: Collection[Mapping[str, str]],
    ) -> list[AppIntegrationRecord]:
        """Reconcile safe WordPress metadata without persisting URLs or credentials."""

        normalized: dict[str, str] = {}
        for site in sites:
            key = str(site.get("integration_key") or "").strip()
            name = str(site.get("display_name") or key).strip()
            if not _INTEGRATION_KEY.fullmatch(key):
                raise CoordinatorSchemaError(
                    "The AppIntegration key is invalid.",
                    safe_context={"integration_type": "wordpress"},
                    code="app_integration_key_invalid",
                )
            if not name or len(name) > 120:
                raise CoordinatorSchemaError(
                    "The AppIntegration display name is invalid.",
                    safe_context={"integration_key": key},
                    code="app_integration_display_name_invalid",
                )
            normalized[key] = name
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = _now()
            for key, name in normalized.items():
                existing = connection.execute(
                    """
                    SELECT id,display_name,status FROM app_integrations
                    WHERE integration_type='wordpress' AND integration_key=?
                    """,
                    (key,),
                ).fetchone()
                if existing is None:
                    integration_id = _new_uuid()
                    connection.execute(
                        """
                        INSERT INTO app_integrations(
                            id,integration_type,integration_key,display_name,status,
                            created_at,updated_at
                        ) VALUES(?,'wordpress',?,?,'active',?,?)
                        """,
                        (integration_id, key, name, now, now),
                    )
                    action = "app_integration.created"
                else:
                    integration_id = str(existing["id"])
                    if str(existing["display_name"]) == name:
                        continue
                    connection.execute(
                        "UPDATE app_integrations SET display_name=?,updated_at=? WHERE id=?",
                        (name, now, integration_id),
                    )
                    action = "app_integration.metadata_updated"
                self._append_audit(
                    connection,
                    actor_type="system",
                    actor_app_user_id=None,
                    actor_global_role=None,
                    action=action,
                    target_type="app_integration",
                    target_id=integration_id,
                    phone_account_id=None,
                    messenger_account_id=None,
                    provider=None,
                    result="succeeded",
                    reason_code=None,
                    safe_metadata={"integration_key": key},
                )
            connection.commit()
        return self.list_app_integrations()

    def list_app_integrations(
        self,
        *,
        app_user_id: str | None = None,
        include_inactive: bool = False,
    ) -> list[AppIntegrationRecord]:
        """List shared integration metadata, optionally authorizing an AppUser."""

        actor_id = _canonical_uuid(app_user_id) if app_user_id else None
        self.initialize()
        with self._connect() as connection:
            if actor_id:
                actor = connection.execute(
                    "SELECT status FROM app_users WHERE id=?", (actor_id,)
                ).fetchone()
                if actor is None or str(actor["status"]) != "active":
                    raise CoordinatorSchemaError(
                        "The AppUser account is not active.",
                        code="app_integration_actor_inactive",
                    )
            where = "" if include_inactive else "WHERE status='active'"
            rows = connection.execute(
                f"""
                SELECT id,integration_type,integration_key,display_name,status
                FROM app_integrations {where}
                ORDER BY integration_type,integration_key
                """
            ).fetchall()
        return [self._app_integration_record(row) for row in rows]

    def require_app_integration_access(
        self,
        *,
        app_user_id: str,
        integration_type: str,
        integration_key: str,
        operation: str = "use",
    ) -> AppIntegrationRecord:
        """Authorize shared use for active users and management for admins only."""

        actor_id = _canonical_uuid(app_user_id)
        selected_type = str(integration_type or "").strip()
        selected_key = str(integration_key or "").strip()
        if selected_type != "wordpress" or not _INTEGRATION_KEY.fullmatch(selected_key):
            raise CoordinatorSchemaError(
                "The AppIntegration selector is invalid.",
                code="app_integration_selector_invalid",
            )
        if operation not in {"use", "manage"}:
            raise CoordinatorSchemaError(
                "The AppIntegration operation is invalid.",
                code="app_integration_operation_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            actor = connection.execute(
                "SELECT status,global_role FROM app_users WHERE id=?", (actor_id,)
            ).fetchone()
            if actor is None or str(actor["status"]) != "active":
                raise CoordinatorSchemaError(
                    "The AppUser account is not active.",
                    code="app_integration_actor_inactive",
                )
            if operation == "manage" and str(actor["global_role"]) != "admin":
                raise CoordinatorSchemaError(
                    "Only an administrator may manage AppIntegrations.",
                    code="app_integration_manage_denied",
                )
            row = connection.execute(
                """
                SELECT id,integration_type,integration_key,display_name,status
                FROM app_integrations
                WHERE integration_type=? AND integration_key=?
                """,
                (selected_type, selected_key),
            ).fetchone()
            if row is None or str(row["status"]) != "active":
                raise CoordinatorSchemaError(
                    "The AppIntegration is unavailable.",
                    safe_context={"integration_key": selected_key},
                    code="app_integration_unavailable",
                )
        return self._app_integration_record(row)

    def update_app_integration(
        self,
        integration_id: str,
        *,
        app_user_id: str,
        global_role: str,
        status: str,
        request_id: str | None = None,
    ) -> AppIntegrationRecord:
        """Admin-only metadata state change; URLs and credentials stay in config."""

        selected_id = _canonical_uuid(integration_id)
        actor_id = _canonical_uuid(app_user_id)
        selected_status = str(status or "").strip()
        if selected_status not in {"active", "disabled"}:
            raise CoordinatorSchemaError(
                "The AppIntegration status is invalid.",
                code="app_integration_status_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            actor = connection.execute(
                "SELECT status,global_role FROM app_users WHERE id=?", (actor_id,)
            ).fetchone()
            if (
                actor is None
                or str(actor["status"]) != "active"
                or str(actor["global_role"]) != global_role
                or global_role != "admin"
            ):
                raise CoordinatorSchemaError(
                    "Only an active administrator may manage AppIntegrations.",
                    code="app_integration_manage_denied",
                )
            row = connection.execute(
                """
                SELECT id,integration_type,integration_key,display_name,status
                FROM app_integrations WHERE id=?
                """,
                (selected_id,),
            ).fetchone()
            if row is None or str(row["status"]) == "archived":
                raise CoordinatorSchemaError(
                    "The AppIntegration is unavailable.",
                    code="app_integration_unavailable",
                )
            previous = str(row["status"])
            connection.execute(
                "UPDATE app_integrations SET status=?,updated_at=? WHERE id=?",
                (selected_status, _now(), selected_id),
            )
            self._append_audit(
                connection,
                actor_type="app_user",
                actor_app_user_id=actor_id,
                actor_global_role=global_role,
                action="app_integration.status.updated",
                target_type="app_integration",
                target_id=selected_id,
                phone_account_id=None,
                messenger_account_id=None,
                provider=None,
                result="succeeded",
                reason_code="admin_updated_integration_status",
                request_id=request_id,
                safe_metadata={
                    "integration_type": str(row["integration_type"]),
                    "integration_key": str(row["integration_key"]),
                    "previous_status": previous,
                    "status": selected_status,
                },
            )
            updated = connection.execute(
                """
                SELECT id,integration_type,integration_key,display_name,status
                FROM app_integrations WHERE id=?
                """,
                (selected_id,),
            ).fetchone()
            connection.commit()
        assert updated is not None
        return self._app_integration_record(updated)

    @staticmethod
    def _app_integration_record(row: sqlite3.Row) -> AppIntegrationRecord:
        return AppIntegrationRecord(
            integration_id=str(row["id"]),
            integration_type=str(row["integration_type"]),
            integration_key=str(row["integration_key"]),
            display_name=str(row["display_name"]),
            status=str(row["status"]),
        )

    def require_messenger_account_access(
        self,
        messenger_account_id: str,
        *,
        app_user_id: str,
        global_role: str,
        operation: str,
    ) -> dict[str, object]:
        """Authorize access against the PhoneAccount owning the exact account."""

        selected_id = _canonical_uuid(messenger_account_id)
        if operation not in {"view", "operate", "manage_worker"}:
            raise CoordinatorSchemaError(
                "The MessengerAccount operation is invalid.",
                code="messenger_account_operation_invalid",
            )
        accounts = self.list_accessible_messenger_accounts(
            app_user_id=app_user_id,
            global_role=global_role,
        )
        selected = next(
            (
                account
                for account in accounts
                if account["messenger_account_id"] == selected_id
            ),
            None,
        )
        allowed = bool(selected and selected["permissions"].get(operation))
        if not allowed:
            raise CoordinatorSchemaError(
                "The AppUser cannot access the selected MessengerAccount.",
                safe_context={"messenger_account_id": selected_id},
                code="messenger_account_access_denied",
            )
        return selected

    def request_worker_start(
        self,
        messenger_account_id: str,
        *,
        process_id: int,
        actor_app_user_id: str | None,
        actor_global_role: str | None,
        request_id: str | None = None,
    ) -> tuple[MessengerAccountRuntimeRecord, WorkerInstanceRecord]:
        """Atomically request an allowlisted provider worker and append audit."""

        selected_id = _canonical_uuid(messenger_account_id)
        actor_id = (
            _canonical_uuid(actor_app_user_id) if actor_app_user_id else None
        )
        if not isinstance(process_id, int) or process_id <= 0:
            raise CoordinatorSchemaError(
                "The worker process identifier is invalid.",
                code="worker_process_id_invalid",
            )
        self.initialize()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._worker_account_row(connection, selected_id)
                self._require_provider_runtime_enabled(
                    connection,
                    provider=str(row["provider"]),
                    messenger_account_id=selected_id,
                )
                if str(row["lifecycle_state"]) in {
                    "disabled",
                    "quarantined",
                    "archived",
                }:
                    raise CoordinatorSchemaError(
                        "The MessengerAccount lifecycle blocks worker start.",
                        safe_context={
                            "messenger_account_id": selected_id,
                            "lifecycle_state": str(row["lifecycle_state"]),
                        },
                        code="worker_lifecycle_blocked",
                    )
                now = _now()
                latest = connection.execute(
                    """
                    SELECT retry_not_before FROM worker_instances
                    WHERE messenger_account_id=?
                    ORDER BY generation DESC LIMIT 1
                    """,
                    (selected_id,),
                ).fetchone()
                if (
                    latest is not None
                    and latest["retry_not_before"] is not None
                    and str(latest["retry_not_before"]) > now
                ):
                    raise CoordinatorSchemaError(
                        "The worker restart backoff has not elapsed.",
                        safe_context={
                            "messenger_account_id": selected_id,
                            "retry_not_before": str(latest["retry_not_before"]),
                        },
                        code="worker_restart_backoff_active",
                    )
                active = connection.execute(
                    """
                    SELECT * FROM worker_instances
                    WHERE messenger_account_id=?
                      AND runtime_state IN ('starting','ready','busy','rate_limited','stopping')
                    ORDER BY generation DESC LIMIT 1
                    """,
                    (selected_id,),
                ).fetchone()
                if active is not None:
                    if (
                        str(active["runtime_state"]) != "stopping"
                        and int(active["process_id"] or 0) == process_id
                    ):
                        connection.commit()
                        return self._runtime_record_from_row(row), self._worker_record(active)
                    raise CoordinatorSchemaError(
                        "Another process still owns the active worker record.",
                        safe_context={"messenger_account_id": selected_id},
                        code="worker_instance_already_active",
                    )
                generation = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(generation),0)+1 FROM worker_instances WHERE messenger_account_id=?",
                        (selected_id,),
                    ).fetchone()[0]
                )
                worker_id = _new_uuid()
                connection.execute(
                    """
                    UPDATE messenger_accounts
                    SET lifecycle_state='active',desired_worker_state='running',updated_at=?
                    WHERE id=?
                    """,
                    (now, selected_id),
                )
                connection.execute(
                    """
                    INSERT INTO worker_instances(
                        id,messenger_account_id,generation,runtime_state,process_id,
                        started_at,last_heartbeat_at,created_at,updated_at
                    ) VALUES(?,?,?,'starting',?,?,NULL,?,?)
                    """,
                    (worker_id, selected_id, generation, process_id, now, now, now),
                )
                self._append_audit(
                    connection,
                    actor_type="app_user" if actor_id else "system",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_global_role if actor_id else None,
                    action="messenger_account.worker.start_requested",
                    target_type="worker_instance",
                    target_id=worker_id,
                    phone_account_id=str(row["phone_account_id"]),
                    messenger_account_id=selected_id,
                    provider=str(row["provider"]),
                    result="succeeded",
                    reason_code="worker_start_requested",
                    safe_metadata={"worker_generation": generation},
                    request_id=request_id,
                )
                connection.commit()
                updated = self.messenger_account_runtime(selected_id)
                return updated, WorkerInstanceRecord(
                    worker_instance_id=worker_id,
                    messenger_account_id=selected_id,
                    generation=generation,
                    runtime_state="starting",
                    process_id=process_id,
                    started_at=now,
                    last_heartbeat_at=None,
                    retry_not_before=None,
                    stopped_at=None,
                    exit_code=None,
                    safe_reason_code=None,
                )
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The worker start request failed.",
                safe_context={"error_type": type(exc).__name__},
                code="worker_start_request_failed",
            ) from exc

    def assert_worker_start_allowed(self, messenger_account_id: str) -> None:
        """Fail before spawn when lifecycle or persisted backoff blocks start."""

        selected_id = _canonical_uuid(messenger_account_id)
        self.initialize()
        with self._connect() as connection:
            row = self._worker_account_row(connection, selected_id)
            self._require_provider_runtime_enabled(
                connection,
                provider=str(row["provider"]),
                messenger_account_id=selected_id,
            )
            lifecycle_state = str(row["lifecycle_state"])
            if lifecycle_state in {"disabled", "quarantined", "archived"}:
                raise CoordinatorSchemaError(
                    "The MessengerAccount lifecycle blocks worker start.",
                    safe_context={
                        "messenger_account_id": selected_id,
                        "lifecycle_state": lifecycle_state,
                    },
                    code="worker_lifecycle_blocked",
                )
            latest = connection.execute(
                """
                SELECT retry_not_before FROM worker_instances
                WHERE messenger_account_id=?
                ORDER BY generation DESC LIMIT 1
                """,
                (selected_id,),
            ).fetchone()
            if (
                latest is not None
                and latest["retry_not_before"] is not None
                and str(latest["retry_not_before"]) > _now()
            ):
                raise CoordinatorSchemaError(
                    "The worker restart backoff has not elapsed.",
                    safe_context={
                        "messenger_account_id": selected_id,
                        "retry_not_before": str(latest["retry_not_before"]),
                    },
                    code="worker_restart_backoff_active",
                )

    def mark_worker_ready(self, worker_instance_id: str) -> WorkerInstanceRecord:
        return self._update_worker_runtime_state(
            worker_instance_id,
            expected_states={"starting", "ready"},
            new_state="ready",
            heartbeat=True,
            reason_code="worker_runtime_ready",
        )

    def active_worker_instance(
        self,
        messenger_account_id: str,
    ) -> WorkerInstanceRecord | None:
        selected_id = _canonical_uuid(messenger_account_id)
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM worker_instances
                WHERE messenger_account_id=?
                  AND runtime_state IN ('starting','ready','busy','rate_limited','stopping')
                ORDER BY generation DESC LIMIT 1
                """,
                (selected_id,),
            ).fetchone()
        return self._worker_record(row) if row is not None else None

    def worker_instances(
        self,
        messenger_account_id: str,
    ) -> tuple[WorkerInstanceRecord, ...]:
        selected_id = _canonical_uuid(messenger_account_id)
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM worker_instances
                WHERE messenger_account_id=?
                ORDER BY generation ASC
                """,
                (selected_id,),
            ).fetchall()
        return tuple(self._worker_record(row) for row in rows)

    def recover_dead_worker_instance(
        self,
        worker_instance_id: str,
        *,
        expected_process_id: int,
        request_id: str | None = None,
        reason_code: str = "worker_process_confirmed_dead",
    ) -> None:
        """Fence a stale worker row after its original OS owner is disproved."""

        worker_id = _canonical_uuid(worker_instance_id)
        if reason_code not in {
            "worker_process_confirmed_dead",
            "worker_process_pid_reused",
        }:
            raise CoordinatorSchemaError(
                "The stale worker recovery reason is invalid.",
                code="worker_recovery_reason_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT wi.*,ma.phone_account_id,ma.provider
                FROM worker_instances wi
                JOIN messenger_accounts ma ON ma.id=wi.messenger_account_id
                WHERE wi.id=?
                """,
                (worker_id,),
            ).fetchone()
            if (
                row is None
                or int(row["process_id"] or 0) != expected_process_id
                or str(row["runtime_state"])
                not in {"starting", "ready", "busy", "rate_limited", "stopping"}
            ):
                raise CoordinatorSchemaError(
                    "The worker changed during stale-record recovery.",
                    code="worker_state_conflict",
                )
            now = _now()
            cursor = connection.execute(
                """
                UPDATE worker_instances
                SET runtime_state='crashed',stopped_at=?,
                    safe_reason_code=?,updated_at=?
                WHERE id=? AND process_id=? AND runtime_state=?
                """,
                (
                    now,
                    reason_code,
                    now,
                    worker_id,
                    expected_process_id,
                    str(row["runtime_state"]),
                ),
            )
            if cursor.rowcount != 1:
                raise CoordinatorSchemaError(
                    "The worker changed during stale-record recovery.",
                    code="worker_state_conflict",
                )
            self._append_audit(
                connection,
                actor_type="system",
                actor_app_user_id=None,
                actor_global_role=None,
                action="messenger_account.worker.dead_process_recovered",
                target_type="worker_instance",
                target_id=worker_id,
                phone_account_id=str(row["phone_account_id"]),
                messenger_account_id=str(row["messenger_account_id"]),
                provider=str(row["provider"]),
                result="succeeded",
                reason_code=reason_code,
                safe_metadata={"worker_generation": int(row["generation"])},
                request_id=request_id,
            )
            connection.commit()

    def heartbeat_worker(self, worker_instance_id: str) -> WorkerInstanceRecord:
        return self._update_worker_runtime_state(
            worker_instance_id,
            expected_states={"ready", "busy", "rate_limited"},
            new_state=None,
            heartbeat=True,
            reason_code=None,
        )

    def heartbeat_worker_fenced(
        self,
        worker_instance_id: str,
        *,
        expected_generation: int,
        expected_process_id: int,
    ) -> WorkerInstanceRecord:
        """Record a heartbeat only for the exact active process generation."""

        worker_id = _canonical_uuid(worker_instance_id)
        if (
            isinstance(expected_generation, bool)
            or not isinstance(expected_generation, int)
            or expected_generation <= 0
            or isinstance(expected_process_id, bool)
            or not isinstance(expected_process_id, int)
            or expected_process_id <= 0
        ):
            raise CoordinatorSchemaError(
                "The worker heartbeat fence is invalid.",
                code="worker_heartbeat_fence_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM worker_instances WHERE id=?",
                (worker_id,),
            ).fetchone()
            if (
                row is None
                or int(row["generation"]) != expected_generation
                or int(row["process_id"] or 0) != expected_process_id
                or str(row["runtime_state"])
                not in {"ready", "busy", "rate_limited"}
            ):
                raise CoordinatorSchemaError(
                    "The worker heartbeat was rejected by its fence.",
                    code="worker_heartbeat_fence_mismatch",
                )
            now = _now()
            cursor = connection.execute(
                """
                UPDATE worker_instances
                SET last_heartbeat_at=?,updated_at=?
                WHERE id=? AND generation=? AND process_id=?
                  AND runtime_state=?
                """,
                (
                    now,
                    now,
                    worker_id,
                    expected_generation,
                    expected_process_id,
                    str(row["runtime_state"]),
                ),
            )
            if cursor.rowcount != 1:
                raise CoordinatorSchemaError(
                    "The worker heartbeat was rejected by its fence.",
                    code="worker_heartbeat_fence_mismatch",
                )
            connection.commit()
            updated = connection.execute(
                "SELECT * FROM worker_instances WHERE id=?",
                (worker_id,),
            ).fetchone()
        assert updated is not None
        return self._worker_record(updated)

    def record_worker_crash(
        self,
        worker_instance_id: str,
        *,
        expected_generation: int,
        expected_process_id: int,
        reason_code: str,
        exit_code: int | None,
        restart_window_seconds: int,
        max_restarts: int,
        backoff_initial_seconds: int,
        backoff_max_seconds: int,
        quarantine_seconds: int,
        request_id: str | None = None,
    ) -> WorkerRecoveryDecision:
        """Fence one crashed generation and atomically decide restart/backoff."""

        worker_id = _canonical_uuid(worker_instance_id)
        selected_reason = self._safe_worker_reason(reason_code)
        integer_values = {
            "expected_generation": expected_generation,
            "expected_process_id": expected_process_id,
            "restart_window_seconds": restart_window_seconds,
            "max_restarts": max_restarts,
            "backoff_initial_seconds": backoff_initial_seconds,
            "backoff_max_seconds": backoff_max_seconds,
            "quarantine_seconds": quarantine_seconds,
        }
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in integer_values.values()
        ) or backoff_max_seconds < backoff_initial_seconds:
            raise CoordinatorSchemaError(
                "The worker recovery policy is invalid.",
                code="worker_recovery_policy_invalid",
            )
        if (
            exit_code is not None
            and (
                isinstance(exit_code, bool)
                or not isinstance(exit_code, int)
                or not -2147483648 <= exit_code <= 4294967295
            )
        ):
            raise CoordinatorSchemaError(
                "The worker exit code is invalid.",
                code="worker_exit_code_invalid",
            )
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT wi.*,ma.phone_account_id,ma.provider,
                       ma.lifecycle_state,ma.desired_worker_state
                FROM worker_instances wi
                JOIN messenger_accounts ma ON ma.id=wi.messenger_account_id
                WHERE wi.id=?
                """,
                (worker_id,),
            ).fetchone()
            if (
                row is None
                or int(row["generation"]) != expected_generation
                or int(row["process_id"] or 0) != expected_process_id
                or str(row["runtime_state"])
                not in {"starting", "ready", "busy", "rate_limited"}
            ):
                raise CoordinatorSchemaError(
                    "The worker crash was rejected by its fence.",
                    code="worker_crash_fence_mismatch",
                )
            now_datetime = datetime.now(timezone.utc)
            now = now_datetime.isoformat(timespec="milliseconds")
            cutoff = (now_datetime - timedelta(seconds=restart_window_seconds)).isoformat(
                timespec="milliseconds"
            )
            prior_crashes = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM worker_instances
                    WHERE messenger_account_id=? AND id<>?
                      AND runtime_state='crashed' AND stopped_at>=?
                    """,
                    (str(row["messenger_account_id"]), worker_id, cutoff),
                ).fetchone()[0]
            )
            crash_count = prior_crashes + 1
            quarantined = crash_count > max_restarts
            if quarantined:
                retry_after_seconds = quarantine_seconds
            else:
                retry_after_seconds = min(
                    backoff_max_seconds,
                    backoff_initial_seconds * (2 ** (crash_count - 1)),
                )
            retry_not_before = (
                now_datetime + timedelta(seconds=retry_after_seconds)
            ).isoformat(timespec="milliseconds")
            cursor = connection.execute(
                """
                UPDATE worker_instances
                SET runtime_state='crashed',retry_not_before=?,stopped_at=?,
                    exit_code=?,safe_reason_code=?,updated_at=?
                WHERE id=? AND generation=? AND process_id=? AND runtime_state=?
                """,
                (
                    retry_not_before,
                    now,
                    exit_code,
                    selected_reason,
                    now,
                    worker_id,
                    expected_generation,
                    expected_process_id,
                    str(row["runtime_state"]),
                ),
            )
            if cursor.rowcount != 1:
                raise CoordinatorSchemaError(
                    "The worker crash was rejected by its fence.",
                    code="worker_crash_fence_mismatch",
                )
            if quarantined:
                connection.execute(
                    """
                    UPDATE messenger_accounts
                    SET lifecycle_state='quarantined',desired_worker_state='stopped',
                        updated_at=?
                    WHERE id=?
                    """,
                    (now, str(row["messenger_account_id"])),
                )
            self._append_audit(
                connection,
                actor_type="system",
                actor_app_user_id=None,
                actor_global_role=None,
                action=(
                    "messenger_account.worker.quarantined"
                    if quarantined
                    else "messenger_account.worker.crashed"
                ),
                target_type="worker_instance",
                target_id=worker_id,
                phone_account_id=str(row["phone_account_id"]),
                messenger_account_id=str(row["messenger_account_id"]),
                provider=str(row["provider"]),
                result="failed",
                reason_code=selected_reason,
                safe_metadata={
                    "worker_generation": expected_generation,
                    "crash_count": crash_count,
                    "retry_after_seconds": retry_after_seconds,
                    "quarantined": quarantined,
                    "exit_code": exit_code,
                },
                request_id=request_id,
            )
            connection.commit()
        return WorkerRecoveryDecision(
            worker_instance_id=worker_id,
            messenger_account_id=str(row["messenger_account_id"]),
            restart_allowed=not quarantined,
            quarantined=quarantined,
            crash_count=crash_count,
            retry_after_seconds=retry_after_seconds,
            retry_not_before=retry_not_before,
            safe_reason_code=selected_reason,
            exit_code=exit_code,
        )

    def fail_worker_start(
        self,
        worker_instance_id: str,
        *,
        reason_code: str,
        request_id: str | None = None,
    ) -> None:
        worker_id = _canonical_uuid(worker_instance_id)
        selected_reason = self._safe_worker_reason(reason_code)
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT wi.*,ma.phone_account_id,ma.provider
                FROM worker_instances wi
                JOIN messenger_accounts ma ON ma.id=wi.messenger_account_id
                WHERE wi.id=?
                """,
                (worker_id,),
            ).fetchone()
            if row is None:
                raise CoordinatorSchemaError(
                    "The worker instance was not found.",
                    code="worker_instance_not_found",
                )
            now = _now()
            connection.execute(
                """
                UPDATE worker_instances
                SET runtime_state='crashed',stopped_at=?,safe_reason_code=?,updated_at=?
                WHERE id=? AND runtime_state IN ('starting','ready','busy','rate_limited')
                """,
                (now, selected_reason, now, worker_id),
            )
            connection.execute(
                """
                UPDATE messenger_accounts
                SET lifecycle_state='paused',desired_worker_state='stopped',updated_at=?
                WHERE id=?
                """,
                (now, str(row["messenger_account_id"])),
            )
            self._append_audit(
                connection,
                actor_type="system",
                actor_app_user_id=None,
                actor_global_role=None,
                action="messenger_account.worker.start_failed",
                target_type="worker_instance",
                target_id=worker_id,
                phone_account_id=str(row["phone_account_id"]),
                messenger_account_id=str(row["messenger_account_id"]),
                provider=str(row["provider"]),
                result="failed",
                reason_code=selected_reason,
                safe_metadata={"worker_generation": int(row["generation"])},
                request_id=request_id,
            )
            connection.commit()

    def request_worker_stop(
        self,
        messenger_account_id: str,
        *,
        actor_app_user_id: str,
        actor_global_role: str,
        request_id: str | None = None,
    ) -> WorkerInstanceRecord | None:
        selected_id = _canonical_uuid(messenger_account_id)
        actor_id = _canonical_uuid(actor_app_user_id)
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._worker_account_row(connection, selected_id)
            worker = connection.execute(
                """
                SELECT * FROM worker_instances
                WHERE messenger_account_id=?
                  AND runtime_state IN ('starting','ready','busy','rate_limited','stopping')
                ORDER BY generation DESC LIMIT 1
                """,
                (selected_id,),
            ).fetchone()
            now = _now()
            connection.execute(
                """
                UPDATE messenger_accounts
                SET desired_worker_state='stopped',updated_at=? WHERE id=?
                """,
                (now, selected_id),
            )
            if worker is not None:
                connection.execute(
                    """
                    UPDATE worker_instances
                    SET runtime_state='stopping',safe_reason_code='worker_stop_requested',updated_at=?
                    WHERE id=?
                    """,
                    (now, str(worker["id"])),
                )
            self._append_audit(
                connection,
                actor_type="app_user",
                actor_app_user_id=actor_id,
                actor_global_role=actor_global_role,
                action="messenger_account.worker.stop_requested",
                target_type="messenger_account",
                target_id=selected_id,
                phone_account_id=str(row["phone_account_id"]),
                messenger_account_id=selected_id,
                provider=str(row["provider"]),
                result="succeeded",
                reason_code="worker_stop_requested",
                safe_metadata={
                    "worker_generation": int(worker["generation"]) if worker else None
                },
                request_id=request_id,
            )
            connection.commit()
            if worker is None:
                return None
            current = self._worker_record(worker)
            return WorkerInstanceRecord(
                worker_instance_id=current.worker_instance_id,
                messenger_account_id=current.messenger_account_id,
                generation=current.generation,
                runtime_state="stopping",
                process_id=current.process_id,
                started_at=current.started_at,
                last_heartbeat_at=current.last_heartbeat_at,
                retry_not_before=current.retry_not_before,
                stopped_at=current.stopped_at,
                exit_code=current.exit_code,
                safe_reason_code="worker_stop_requested",
            )

    def complete_worker_stop(
        self,
        messenger_account_id: str,
        *,
        worker_instance_id: str | None,
        reason_code: str,
        pause_account: bool,
    ) -> MessengerAccountRuntimeRecord:
        selected_id = _canonical_uuid(messenger_account_id)
        worker_id = _canonical_uuid(worker_instance_id) if worker_instance_id else None
        selected_reason = self._safe_worker_reason(reason_code)
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._worker_account_row(connection, selected_id)
            now = _now()
            if worker_id is not None:
                connection.execute(
                    """
                    UPDATE worker_instances
                    SET runtime_state='stopped',stopped_at=?,safe_reason_code=?,updated_at=?
                    WHERE id=? AND messenger_account_id=?
                      AND runtime_state IN ('starting','ready','busy','rate_limited','stopping')
                    """,
                    (now, selected_reason, now, worker_id, selected_id),
                )
            if pause_account:
                connection.execute(
                    """
                    UPDATE messenger_accounts
                    SET lifecycle_state='paused',desired_worker_state='stopped',updated_at=?
                    WHERE id=?
                    """,
                    (now, selected_id),
                )
            connection.commit()
        return self.messenger_account_runtime(selected_id)

    @staticmethod
    def _accessible_accounts_query(*, admin: bool) -> str:
        membership_join = (
            "LEFT JOIN phone_account_memberships pm "
            "ON pm.phone_account_id=ma.phone_account_id "
            "AND pm.app_user_id=? AND pm.status='active'"
            if admin
            else "JOIN phone_account_memberships pm "
            "ON pm.phone_account_id=ma.phone_account_id "
            "AND pm.app_user_id=? AND pm.status='active'"
        )
        return f"""
            SELECT
                ma.id AS messenger_account_id,ma.phone_account_id,ma.provider,ma.label,
                ma.lifecycle_state,ma.desired_worker_state,pa.display_hint,
                sm.auth_state,sm.session_generation,sm.storage_revision,
                pm.role AS membership_role,
                wi.id AS worker_instance_id,wi.generation AS worker_generation,
                wi.runtime_state,wi.process_id,wi.last_heartbeat_at,wi.safe_reason_code
            FROM messenger_accounts ma
            JOIN phone_accounts pa ON pa.id=ma.phone_account_id AND pa.status='active'
            JOIN messenger_session_metadata sm ON sm.messenger_account_id=ma.id
            {membership_join}
            LEFT JOIN worker_instances wi ON wi.id=(
                SELECT newest.id FROM worker_instances newest
                WHERE newest.messenger_account_id=ma.id
                ORDER BY newest.generation DESC LIMIT 1
            )
            WHERE ma.lifecycle_state<>'archived'
            ORDER BY ma.created_at,ma.id
        """

    @staticmethod
    def _safe_account_card(row: sqlite3.Row, *, global_role: str) -> dict[str, object]:
        membership_role = (
            "admin" if global_role == "admin" else str(row["membership_role"])
        )
        can_operate = global_role == "admin" or membership_role in {"owner", "operator"}
        worker = None
        if row["worker_instance_id"] is not None:
            worker = {
                "worker_instance_id": str(row["worker_instance_id"]),
                "generation": int(row["worker_generation"]),
                "runtime_state": str(row["runtime_state"]),
                "process_id": int(row["process_id"]) if row["process_id"] is not None else None,
                "last_heartbeat_at": (
                    str(row["last_heartbeat_at"])
                    if row["last_heartbeat_at"] is not None
                    else None
                ),
                "safe_reason_code": (
                    str(row["safe_reason_code"])
                    if row["safe_reason_code"] is not None
                    else None
                ),
            }
        return {
            "messenger_account_id": str(row["messenger_account_id"]),
            "phone_account_id": str(row["phone_account_id"]),
            "provider": str(row["provider"]),
            "label": str(row["label"]) if row["label"] is not None else None,
            "phone_hint": str(row["display_hint"] or ""),
            "membership_role": membership_role,
            "lifecycle_state": str(row["lifecycle_state"]),
            "desired_worker_state": str(row["desired_worker_state"]),
            "auth_state": str(row["auth_state"]),
            "session_generation": int(row["session_generation"]),
            "storage_revision": int(row["storage_revision"]),
            "worker": worker,
            "permissions": {
                "view": True,
                "operate": can_operate,
                "manage_worker": can_operate,
            },
        }

    @staticmethod
    def _worker_account_row(
        connection: sqlite3.Connection,
        messenger_account_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT
                ma.id AS messenger_account_id,ma.phone_account_id,ma.provider,
                ma.lifecycle_state,ma.desired_worker_state,sm.auth_state,
                sm.session_generation,sm.storage_revision
            FROM messenger_accounts ma
            JOIN messenger_session_metadata sm ON sm.messenger_account_id=ma.id
            WHERE ma.id=?
            """,
            (messenger_account_id,),
        ).fetchone()
        if row is None:
            raise CoordinatorSchemaError(
                "The MessengerAccount runtime record was not found.",
                code="messenger_account_runtime_not_found",
            )
        return row

    @staticmethod
    def _require_provider_runtime_enabled(
        connection: sqlite3.Connection,
        *,
        provider: str,
        messenger_account_id: str,
    ) -> None:
        registration = connection.execute(
            """
            SELECT configured,runtime_enabled,status
            FROM provider_registrations WHERE provider=?
            """,
            (provider,),
        ).fetchone()
        if (
            registration is None
            or str(registration["status"]) != "active"
            or not bool(registration["configured"])
            or not bool(registration["runtime_enabled"])
        ):
            raise CoordinatorSchemaError(
                "No worker adapter is configured for this provider.",
                safe_context={
                    "messenger_account_id": messenger_account_id,
                    "provider": provider,
                },
                code="worker_provider_unsupported",
            )

    @staticmethod
    def _runtime_record_from_row(row: sqlite3.Row) -> MessengerAccountRuntimeRecord:
        return MessengerAccountRuntimeRecord(
            messenger_account_id=str(row["messenger_account_id"]),
            phone_account_id=str(row["phone_account_id"]),
            provider=str(row["provider"]),
            lifecycle_state=str(row["lifecycle_state"]),
            desired_worker_state=str(row["desired_worker_state"]),
            auth_state=str(row["auth_state"]),
            session_generation=int(row["session_generation"]),
            storage_revision=int(row["storage_revision"]),
        )

    @staticmethod
    def _worker_record(row: sqlite3.Row) -> WorkerInstanceRecord:
        return WorkerInstanceRecord(
            worker_instance_id=str(row["id"]),
            messenger_account_id=str(row["messenger_account_id"]),
            generation=int(row["generation"]),
            runtime_state=str(row["runtime_state"]),
            process_id=int(row["process_id"]) if row["process_id"] is not None else None,
            started_at=str(row["started_at"]),
            last_heartbeat_at=(
                str(row["last_heartbeat_at"])
                if row["last_heartbeat_at"] is not None
                else None
            ),
            retry_not_before=(
                str(row["retry_not_before"])
                if row["retry_not_before"] is not None
                else None
            ),
            stopped_at=str(row["stopped_at"]) if row["stopped_at"] is not None else None,
            exit_code=int(row["exit_code"]) if row["exit_code"] is not None else None,
            safe_reason_code=(
                str(row["safe_reason_code"])
                if row["safe_reason_code"] is not None
                else None
            ),
        )

    def _update_worker_runtime_state(
        self,
        worker_instance_id: str,
        *,
        expected_states: set[str],
        new_state: str | None,
        heartbeat: bool,
        reason_code: str | None,
    ) -> WorkerInstanceRecord:
        worker_id = _canonical_uuid(worker_instance_id)
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM worker_instances WHERE id=?",
                (worker_id,),
            ).fetchone()
            if row is None:
                raise CoordinatorSchemaError(
                    "The worker instance was not found.",
                    code="worker_instance_not_found",
                )
            current = str(row["runtime_state"])
            if current not in expected_states:
                raise CoordinatorSchemaError(
                    "The worker state changed concurrently.",
                    code="worker_state_conflict",
                )
            selected_state = new_state or current
            now = _now()
            connection.execute(
                """
                UPDATE worker_instances
                SET runtime_state=?,last_heartbeat_at=CASE WHEN ? THEN ? ELSE last_heartbeat_at END,
                    safe_reason_code=?,updated_at=?
                WHERE id=? AND runtime_state=?
                """,
                (
                    selected_state,
                    1 if heartbeat else 0,
                    now,
                    reason_code,
                    now,
                    worker_id,
                    current,
                ),
            )
            connection.commit()
            updated = connection.execute(
                "SELECT * FROM worker_instances WHERE id=?",
                (worker_id,),
            ).fetchone()
        assert updated is not None
        return self._worker_record(updated)

    @staticmethod
    def _safe_worker_reason(value: str) -> str:
        selected = str(value)
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,80}", selected):
            raise CoordinatorSchemaError(
                "The worker reason code is invalid.",
                code="worker_reason_invalid",
            )
        return selected

    def transition_messenger_auth(
        self,
        messenger_account_id: str,
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
        """Compare-and-swap session metadata and its audit event in one transaction."""

        selected_id = _canonical_uuid(messenger_account_id)
        selected_expected = frozenset(str(item) for item in expected_states)
        if not selected_expected or not selected_expected.issubset(_AUTH_STATES):
            raise CoordinatorSchemaError(
                "The expected MessengerAccount auth states are invalid.",
                code="messenger_auth_expected_state_invalid",
            )
        if new_state not in _AUTH_STATES:
            raise CoordinatorSchemaError(
                "The target MessengerAccount auth state is invalid.",
                code="messenger_auth_target_state_invalid",
            )
        if not isinstance(expected_generation, int) or expected_generation < 0:
            raise CoordinatorSchemaError(
                "The expected MessengerAccount session generation is invalid.",
                code="messenger_auth_generation_invalid",
            )
        selected_reason = self._safe_auth_reason(reason_code)
        selected_action = self._safe_auth_action(action)
        metadata = self._safe_auth_metadata(safe_metadata or {})
        actor_id = _canonical_uuid(actor_app_user_id) if actor_app_user_id else None
        actor_type = "app_user" if actor_id is not None else "system"
        self.initialize()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT
                        ma.id AS messenger_account_id,
                        ma.phone_account_id,
                        ma.provider,
                        ma.lifecycle_state,
                        ma.desired_worker_state,
                        sm.auth_state,
                        sm.session_generation,
                        sm.storage_revision,
                        sm.last_auth_transition_at
                    FROM messenger_accounts ma
                    JOIN messenger_session_metadata sm
                      ON sm.messenger_account_id=ma.id
                    WHERE ma.id=?
                    """,
                    (selected_id,),
                ).fetchone()
                if row is None:
                    raise CoordinatorSchemaError(
                        "The MessengerAccount auth metadata was not found.",
                        code="messenger_auth_metadata_not_found",
                    )
                current_state = str(row["auth_state"])
                current_generation = int(row["session_generation"])
                if (
                    current_state not in selected_expected
                    or current_generation != expected_generation
                ):
                    raise CoordinatorSchemaError(
                        "The MessengerAccount auth state changed concurrently.",
                        safe_context={
                            "messenger_account_id": selected_id,
                            "actual_auth_state": current_state,
                            "actual_session_generation": current_generation,
                        },
                        code="messenger_auth_transition_conflict",
                    )
                if new_state not in _AUTH_TRANSITIONS[current_state]:
                    raise CoordinatorSchemaError(
                        "The MessengerAccount auth transition is not allowed.",
                        safe_context={
                            "messenger_account_id": selected_id,
                            "from_auth_state": current_state,
                            "to_auth_state": new_state,
                        },
                        code="messenger_auth_transition_not_allowed",
                    )
                new_generation = current_generation + (1 if increment_generation else 0)
                changed = new_state != current_state or new_generation != current_generation
                now = _now()
                transition_at = now if changed else str(row["last_auth_transition_at"])
                cursor = connection.execute(
                    """
                    UPDATE messenger_session_metadata
                    SET auth_state=?,session_generation=?,last_validated_at=CASE
                            WHEN ? THEN ? ELSE last_validated_at END,
                        last_auth_transition_at=?,safe_reason_code=?,updated_at=?
                    WHERE messenger_account_id=?
                      AND auth_state=? AND session_generation=?
                    """,
                    (
                        new_state,
                        new_generation,
                        1 if mark_validated else 0,
                        now,
                        transition_at,
                        selected_reason,
                        now,
                        selected_id,
                        current_state,
                        current_generation,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CoordinatorSchemaError(
                        "The MessengerAccount auth transition lost its compare-and-swap.",
                        code="messenger_auth_transition_conflict",
                    )
                if changed or audit_when_unchanged:
                    self._append_audit(
                        connection,
                        actor_type=actor_type,
                        actor_app_user_id=actor_id,
                        actor_global_role=actor_global_role if actor_id else None,
                        action=selected_action,
                        target_type="messenger_session",
                        target_id=selected_id,
                        phone_account_id=str(row["phone_account_id"]),
                        messenger_account_id=selected_id,
                        provider=str(row["provider"]),
                        result="succeeded",
                        reason_code=selected_reason,
                        safe_metadata={
                            "from_auth_state": current_state,
                            "to_auth_state": new_state,
                            "from_session_generation": current_generation,
                            "to_session_generation": new_generation,
                            **metadata,
                        },
                        request_id=request_id,
                    )
                connection.commit()
                return MessengerAccountRuntimeRecord(
                    messenger_account_id=selected_id,
                    phone_account_id=str(row["phone_account_id"]),
                    provider=str(row["provider"]),
                    lifecycle_state=str(row["lifecycle_state"]),
                    desired_worker_state=str(row["desired_worker_state"]),
                    auth_state=new_state,
                    session_generation=new_generation,
                    storage_revision=int(row["storage_revision"]),
                )
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The MessengerAccount auth transition failed.",
                safe_context={
                    "messenger_account_id": selected_id,
                    "error_type": type(exc).__name__,
                },
                code="messenger_auth_transition_failed",
            ) from exc

    def audit_messenger_auth_event(
        self,
        messenger_account_id: str,
        *,
        action: str,
        result: str,
        reason_code: str,
        actor_app_user_id: str | None = None,
        actor_global_role: str | None = None,
        request_id: str | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Append an account auth outcome without changing session metadata."""

        selected_id = _canonical_uuid(messenger_account_id)
        if result not in {"succeeded", "failed", "denied"}:
            raise CoordinatorSchemaError(
                "The MessengerAccount auth audit result is invalid.",
                code="messenger_auth_audit_result_invalid",
            )
        selected_action = self._safe_auth_action(action)
        selected_reason = self._safe_auth_reason(reason_code)
        metadata = self._safe_auth_metadata(safe_metadata or {})
        actor_id = _canonical_uuid(actor_app_user_id) if actor_app_user_id else None
        self.initialize()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT phone_account_id,provider
                    FROM messenger_accounts WHERE id=?
                    """,
                    (selected_id,),
                ).fetchone()
                if row is None:
                    raise CoordinatorSchemaError(
                        "The MessengerAccount auth audit target was not found.",
                        code="messenger_auth_metadata_not_found",
                    )
                self._append_audit(
                    connection,
                    actor_type="app_user" if actor_id else "system",
                    actor_app_user_id=actor_id,
                    actor_global_role=actor_global_role if actor_id else None,
                    action=selected_action,
                    target_type="messenger_session",
                    target_id=selected_id,
                    phone_account_id=str(row["phone_account_id"]),
                    messenger_account_id=selected_id,
                    provider=str(row["provider"]),
                    result=result,
                    reason_code=selected_reason,
                    safe_metadata=metadata,
                    request_id=request_id,
                )
                connection.commit()
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The MessengerAccount auth audit could not be recorded.",
                safe_context={
                    "messenger_account_id": selected_id,
                    "error_type": type(exc).__name__,
                },
                code="messenger_auth_audit_failed",
            ) from exc

    @staticmethod
    def _safe_auth_action(value: str) -> str:
        selected = str(value or "")
        if not _AUTH_AUDIT_ACTION.fullmatch(selected):
            raise CoordinatorSchemaError(
                "The MessengerAccount auth audit action is invalid.",
                code="messenger_auth_audit_action_invalid",
            )
        return selected

    @staticmethod
    def _safe_auth_reason(value: str) -> str:
        selected = str(value or "")
        if not re.fullmatch(r"[a-z0-9_.-]{1,100}", selected):
            raise CoordinatorSchemaError(
                "The MessengerAccount auth reason is invalid.",
                code="messenger_auth_reason_invalid",
            )
        return selected

    @staticmethod
    def _safe_auth_metadata(values: Mapping[str, Any]) -> dict[str, Any]:
        selected: dict[str, Any] = {}
        for key, value in values.items():
            name = str(key)
            lowered = name.lower()
            if (
                not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
                or any(part in lowered for part in _UNSAFE_AUTH_METADATA_KEY_PARTS)
            ):
                raise CoordinatorSchemaError(
                    "Unsafe MessengerAccount auth audit metadata was rejected.",
                    code="messenger_auth_audit_metadata_unsafe",
                )
            if value is not None and not isinstance(value, (bool, int, float, str)):
                raise CoordinatorSchemaError(
                    "MessengerAccount auth audit metadata must be scalar.",
                    code="messenger_auth_audit_metadata_invalid",
                )
            if isinstance(value, str) and len(value) > 200:
                raise CoordinatorSchemaError(
                    "MessengerAccount auth audit metadata is too long.",
                    code="messenger_auth_audit_metadata_invalid",
                )
            selected[name] = value
        return selected

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _verify_schema(
        connection: sqlite3.Connection,
        *,
        expected_version: int = COORDINATOR_SCHEMA_VERSION,
    ) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != expected_version or expected_version not in SCHEMA_CHECKSUMS:
            raise CoordinatorSchemaError(
                "The coordinator schema version is unsupported.",
                safe_context={
                    "database_version": version,
                    "supported_version": expected_version,
                },
                code="coordinator_schema_version_invalid",
            )
        for migration_version in range(1, expected_version + 1):
            row = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version=?",
                (migration_version,),
            ).fetchone()
            if (
                row is None
                or str(row["checksum"]) != SCHEMA_CHECKSUMS.get(migration_version)
            ):
                raise CoordinatorSchemaError(
                    "The coordinator schema checksum does not match.",
                    safe_context={"migration_version": migration_version},
                    code="coordinator_schema_checksum_mismatch",
                )
        tables = {
            str(item["name"])
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required_tables = (
            REQUIRED_TABLES_V1
            if expected_version == 1
            else (
                REQUIRED_TABLES_V2
                if expected_version == 2
                else (
                    REQUIRED_TABLES_V3
                    if expected_version == 3
                    else (
                        REQUIRED_TABLES_V4
                        if expected_version == 4
                        else (
                            REQUIRED_TABLES_V5
                            if expected_version == 5
                            else (
                                REQUIRED_TABLES_V6
                                if expected_version == 6
                                else REQUIRED_TABLES
                            )
                        )
                    )
                )
            )
        )
        missing = sorted(required_tables - tables)
        if missing:
            raise CoordinatorSchemaError(
                "The coordinator schema is incomplete.",
                safe_context={"missing_table_count": len(missing)},
                code="coordinator_schema_incomplete",
            )
        integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        if integrity.lower() != "ok":
            raise CoordinatorSchemaError(
                "The coordinator database integrity check failed.",
                code="coordinator_integrity_failed",
            )
        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise CoordinatorSchemaError(
                "The coordinator database foreign-key check failed.",
                safe_context={"violation_count": len(foreign_key_violations)},
                code="coordinator_foreign_key_check_failed",
            )

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        *,
        actor_type: str,
        actor_app_user_id: str | None,
        actor_global_role: str | None,
        action: str,
        target_type: str,
        target_id: str | None,
        phone_account_id: str | None,
        messenger_account_id: str | None,
        provider: str | None,
        result: str,
        reason_code: str | None,
        safe_metadata: Mapping[str, Any],
        request_id: str | None = None,
    ) -> None:
        previous = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous is not None else None
        event_id = _new_uuid()
        at = _now()
        redacted_metadata = redact(dict(safe_metadata))
        metadata_json = json.dumps(
            redacted_metadata if isinstance(redacted_metadata, dict) else {},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        canonical = json.dumps(
            {
                "id": event_id,
                "schema_version": 1,
                "at": at,
                "actor_type": actor_type,
                "actor_app_user_id": actor_app_user_id,
                "actor_global_role": actor_global_role,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "phone_account_id": phone_account_id,
                "messenger_account_id": messenger_account_id,
                "provider": provider,
                "result": result,
                "reason_code": reason_code,
                "request_id": request_id,
                "safe_metadata_json": metadata_json,
                "previous_event_hash": previous_hash,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        connection.execute(
            """
            INSERT INTO audit_events(
                id,schema_version,at,actor_type,actor_app_user_id,actor_global_role,
                action,target_type,target_id,phone_account_id,messenger_account_id,
                provider,result,reason_code,request_id,safe_metadata_json,
                previous_event_hash,event_hash
            ) VALUES(?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                at,
                actor_type,
                actor_app_user_id,
                actor_global_role,
                action,
                target_type,
                target_id,
                phone_account_id,
                messenger_account_id,
                provider,
                result,
                reason_code,
                request_id,
                metadata_json,
                previous_hash,
                event_hash,
            ),
        )
