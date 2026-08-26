"""Bridge-owned local contact directory with conservative deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Iterable, Mapping, Sequence
import uuid

from ..errors import ContactDirectoryError


CONTACT_SCHEMA = 3
_PHONE_CLEAN = re.compile(r"[^\d+]")
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ContactMutationContext:
    """Trusted server-side actor/account context for one shared-directory write."""

    actor_app_user_id: str | None = None
    messenger_account_id: str | None = None
    provider: str | None = None
    request_id: str | None = None


def provider_subject_fingerprint(provider: str, provider_user_id: object) -> str:
    """Return a stable, non-reversible key for an account-scoped provider subject."""

    selected_provider = str(provider or "").strip().lower()
    selected_subject = str(provider_user_id or "").strip()
    if not _PROVIDER_ID.fullmatch(selected_provider) or not selected_subject:
        raise ValueError("Provider identity is not valid.")
    return hashlib.sha256(
        f"contact-provider-subject-v1\x00{selected_provider}\x00{selected_subject}".encode(
            "utf-8"
        )
    ).hexdigest()


def normalize_phone(value: object) -> str:
    """Return a stable E.164-like key, defaulting Iranian local mobile numbers."""

    raw = _PHONE_CLEAN.sub("", str(value or "").strip())
    if raw.startswith("0098"):
        raw = f"+98{raw[4:]}"
    elif raw.startswith("98") and not raw.startswith("+"):
        raw = f"+{raw}"
    elif raw.startswith("09"):
        raw = f"+98{raw[1:]}"
    elif len(raw) == 10 and raw.startswith("9"):
        raw = f"+98{raw}"
    if not raw.startswith("+") or not raw[1:].isdigit() or not 8 <= len(raw[1:]) <= 15:
        raise ValueError("Phone number is not valid.")
    return raw


class SQLiteContactStore:
    """Local-only contact data; no method in this class performs an Eitaa RPC."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self._initialize_lock = threading.RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def initialize(self) -> None:
        with self._initialize_lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                existed = self.path.exists() and self.path.stat().st_size > 0
                with self._connect() as connection:
                    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                    if version > CONTACT_SCHEMA:
                        raise ContactDirectoryError(
                            "Contact database is newer than this application.",
                            safe_context={"database_version": version, "supported_version": CONTACT_SCHEMA},
                        )
                    if version == 0:
                        if existed:
                            self._backup_schema(connection, version=0)
                        connection.executescript(
                            """
                        BEGIN IMMEDIATE;
                        CREATE TABLE contacts (
                            contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            first_name TEXT NOT NULL DEFAULT '',
                            last_name TEXT NOT NULL DEFAULT '',
                            username TEXT NOT NULL DEFAULT '',
                            eitaa_user_id INTEGER,
                            access_hash TEXT NOT NULL DEFAULT '',
                            organization TEXT NOT NULL DEFAULT '',
                            notes TEXT NOT NULL DEFAULT '',
                            source TEXT NOT NULL DEFAULT 'manual',
                            sendable INTEGER NOT NULL DEFAULT 1 CHECK(sendable IN (0,1)),
                            opt_out INTEGER NOT NULL DEFAULT 0 CHECK(opt_out IN (0,1)),
                            last_resolved_at TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            archived_at TEXT,
                            created_by_app_user_id TEXT,
                            updated_by_app_user_id TEXT,
                            revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0)
                        );
                        CREATE UNIQUE INDEX idx_contacts_eitaa_user
                            ON contacts(eitaa_user_id) WHERE eitaa_user_id IS NOT NULL;
                        CREATE TABLE contact_phones (
                            phone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                            normalized_phone TEXT NOT NULL UNIQUE,
                            label TEXT NOT NULL DEFAULT '',
                            created_at TEXT NOT NULL
                        );
                        CREATE INDEX idx_contact_phones_contact ON contact_phones(contact_id);
                        CREATE TABLE contact_categories (
                            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            created_by_app_user_id TEXT,
                            updated_by_app_user_id TEXT
                        );
                        CREATE TABLE contact_category_members (
                            contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                            category_id INTEGER NOT NULL REFERENCES contact_categories(category_id) ON DELETE CASCADE,
                            PRIMARY KEY(contact_id, category_id)
                        );
                        CREATE INDEX idx_contact_category_members_category
                            ON contact_category_members(category_id, contact_id);
                        CREATE TABLE contact_provider_registrations (
                            provider TEXT PRIMARY KEY,
                            account_kind TEXT NOT NULL,
                            status TEXT NOT NULL CHECK(status IN ('active','disabled','retired')),
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        INSERT INTO contact_provider_registrations(
                            provider,account_kind,status,created_at,updated_at
                        ) VALUES
                            ('eitaa','personal','active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            ('bale','personal','active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'));
                        CREATE TABLE contact_account_bindings (
                            binding_id TEXT PRIMARY KEY,
                            contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                            messenger_account_id TEXT NOT NULL,
                            provider TEXT NOT NULL REFERENCES contact_provider_registrations(provider),
                            provider_subject_fingerprint TEXT,
                            reachability TEXT NOT NULL DEFAULT 'unknown'
                                CHECK(reachability IN ('unknown','reachable','unreachable','blocked')),
                            safe_reason_code TEXT,
                            last_resolved_at TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            created_by_app_user_id TEXT,
                            updated_by_app_user_id TEXT,
                            UNIQUE(messenger_account_id, provider, contact_id)
                        );
                        CREATE UNIQUE INDEX idx_contact_binding_subject
                            ON contact_account_bindings(
                                messenger_account_id,provider,provider_subject_fingerprint
                            ) WHERE provider_subject_fingerprint IS NOT NULL;
                        CREATE INDEX idx_contact_bindings_contact
                            ON contact_account_bindings(contact_id,messenger_account_id,provider);
                        CREATE TABLE contact_audit_events (
                            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL UNIQUE,
                            occurred_at TEXT NOT NULL,
                            actor_app_user_id TEXT,
                            messenger_account_id TEXT,
                            provider TEXT,
                            action TEXT NOT NULL,
                            entity_type TEXT NOT NULL,
                            entity_id INTEGER,
                            request_id TEXT,
                            safe_metadata_json TEXT NOT NULL,
                            previous_event_hash TEXT,
                            event_hash TEXT NOT NULL UNIQUE
                        );
                        CREATE INDEX idx_contact_audit_entity
                            ON contact_audit_events(entity_type,entity_id,sequence DESC);
                        PRAGMA user_version=3;
                        COMMIT;
                        """
                        )
                    elif version == 1:
                        self._backup_schema(connection, version=1)
                        connection.executescript(
                            """
                        BEGIN IMMEDIATE;
                        ALTER TABLE contacts ADD COLUMN created_by_app_user_id TEXT;
                        ALTER TABLE contacts ADD COLUMN updated_by_app_user_id TEXT;
                        ALTER TABLE contacts ADD COLUMN revision INTEGER NOT NULL DEFAULT 1
                            CHECK(revision > 0);
                        ALTER TABLE contact_categories ADD COLUMN created_by_app_user_id TEXT;
                        ALTER TABLE contact_categories ADD COLUMN updated_by_app_user_id TEXT;
                        CREATE TABLE contact_provider_registrations (
                            provider TEXT PRIMARY KEY,
                            account_kind TEXT NOT NULL,
                            status TEXT NOT NULL CHECK(status IN ('active','disabled','retired')),
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        INSERT INTO contact_provider_registrations(
                            provider,account_kind,status,created_at,updated_at
                        ) VALUES
                            ('eitaa','personal','active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            ('bale','personal','active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'));
                        CREATE TABLE contact_account_bindings (
                            binding_id TEXT PRIMARY KEY,
                            contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                            messenger_account_id TEXT NOT NULL,
                            provider TEXT NOT NULL REFERENCES contact_provider_registrations(provider),
                            provider_subject_fingerprint TEXT,
                            reachability TEXT NOT NULL DEFAULT 'unknown'
                                CHECK(reachability IN ('unknown','reachable','unreachable','blocked')),
                            safe_reason_code TEXT,
                            last_resolved_at TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            created_by_app_user_id TEXT,
                            updated_by_app_user_id TEXT,
                            UNIQUE(messenger_account_id, provider, contact_id)
                        );
                        CREATE UNIQUE INDEX idx_contact_binding_subject
                            ON contact_account_bindings(
                                messenger_account_id,provider,provider_subject_fingerprint
                            ) WHERE provider_subject_fingerprint IS NOT NULL;
                        CREATE INDEX idx_contact_bindings_contact
                            ON contact_account_bindings(contact_id,messenger_account_id,provider);
                        CREATE TABLE contact_audit_events (
                            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL UNIQUE,
                            occurred_at TEXT NOT NULL,
                            actor_app_user_id TEXT,
                            messenger_account_id TEXT,
                            provider TEXT,
                            action TEXT NOT NULL,
                            entity_type TEXT NOT NULL,
                            entity_id INTEGER,
                            request_id TEXT,
                            safe_metadata_json TEXT NOT NULL,
                            previous_event_hash TEXT,
                            event_hash TEXT NOT NULL UNIQUE
                        );
                        CREATE INDEX idx_contact_audit_entity
                            ON contact_audit_events(entity_type,entity_id,sequence DESC);
                        PRAGMA user_version=3;
                        COMMIT;
                        """
                        )
                    elif version == 2:
                        self._backup_schema(connection, version=2)
                        connection.executescript(
                            """
                        PRAGMA foreign_keys=OFF;
                        BEGIN IMMEDIATE;
                        CREATE TABLE contact_provider_registrations (
                            provider TEXT PRIMARY KEY,
                            account_kind TEXT NOT NULL,
                            status TEXT NOT NULL CHECK(status IN ('active','disabled','retired')),
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        INSERT INTO contact_provider_registrations(
                            provider,account_kind,status,created_at,updated_at
                        ) VALUES
                            ('eitaa','personal','active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            ('bale','personal','active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'));
                        CREATE TABLE contact_account_bindings_v3 (
                            binding_id TEXT PRIMARY KEY,
                            contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                            messenger_account_id TEXT NOT NULL,
                            provider TEXT NOT NULL REFERENCES contact_provider_registrations(provider),
                            provider_subject_fingerprint TEXT,
                            reachability TEXT NOT NULL DEFAULT 'unknown'
                                CHECK(reachability IN ('unknown','reachable','unreachable','blocked')),
                            safe_reason_code TEXT,
                            last_resolved_at TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            created_by_app_user_id TEXT,
                            updated_by_app_user_id TEXT,
                            UNIQUE(messenger_account_id, provider, contact_id)
                        );
                        INSERT INTO contact_account_bindings_v3
                            SELECT * FROM contact_account_bindings;
                        DROP TABLE contact_account_bindings;
                        ALTER TABLE contact_account_bindings_v3 RENAME TO contact_account_bindings;
                        CREATE UNIQUE INDEX idx_contact_binding_subject
                            ON contact_account_bindings(
                                messenger_account_id,provider,provider_subject_fingerprint
                            ) WHERE provider_subject_fingerprint IS NOT NULL;
                        CREATE INDEX idx_contact_bindings_contact
                            ON contact_account_bindings(contact_id,messenger_account_id,provider);
                        PRAGMA user_version=3;
                        COMMIT;
                        PRAGMA foreign_keys=ON;
                        """
                        )
                    current_version = int(
                        connection.execute("PRAGMA user_version").fetchone()[0]
                    )
                    if current_version != CONTACT_SCHEMA:
                        raise ContactDirectoryError(
                            "Contact database schema migration did not complete.",
                            safe_context={
                                "database_version": current_version,
                                "supported_version": CONTACT_SCHEMA,
                            },
                        )
                    integrity = str(
                        connection.execute("PRAGMA quick_check").fetchone()[0]
                    )
                    foreign_key_rows = connection.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchall()
                    if integrity != "ok" or foreign_key_rows:
                        raise ContactDirectoryError(
                            "Contact database integrity verification failed.",
                            safe_context={
                                "quick_check": integrity,
                                "foreign_key_violation_count": len(foreign_key_rows),
                            },
                        )
                    self._initialized = True
            except ContactDirectoryError:
                raise
            except (OSError, sqlite3.Error) as exc:
                raise ContactDirectoryError(
                    "Contact database could not be initialized.",
                    safe_context={"error_type": type(exc).__name__, "file_name": self.path.name},
                ) from exc

    def _backup_schema(self, connection: sqlite3.Connection, *, version: int) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self.path.with_name(
            f"{self.path.stem}.schema{version}.{stamp}.{uuid.uuid4().hex[:8]}.bak.sqlite3"
        )
        backup_connection = sqlite3.connect(backup)
        try:
            connection.backup(backup_connection)
        finally:
            backup_connection.close()
        return backup

    def reconcile_provider_registrations(
        self, registrations: Iterable[Mapping[str, object]]
    ) -> dict[str, int]:
        """Persist the composition-root provider set without deleting old bindings."""

        self.initialize()
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for registration in registrations:
            provider = str(registration.get("provider") or "").strip().lower()
            account_kind = str(registration.get("account_kind") or "").strip().lower()
            if not _PROVIDER_ID.fullmatch(provider):
                raise ValueError("Provider registration is not valid.")
            if account_kind not in {"personal", "bot", "service", "test", "legacy"}:
                raise ValueError("Provider account kind is not valid.")
            if provider in seen:
                raise ValueError("Provider registration is duplicated.")
            seen.add(provider)
            normalized.append((provider, account_kind))
        if not normalized:
            raise ValueError("At least one provider registration is required.")

        created = updated = unchanged = 0
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for provider, account_kind in normalized:
                existing = connection.execute(
                    "SELECT account_kind,status FROM contact_provider_registrations WHERE provider=?",
                    (provider,),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        """INSERT INTO contact_provider_registrations(
                            provider,account_kind,status,created_at,updated_at
                        ) VALUES(?,?,'active',?,?)""",
                        (provider, account_kind, now, now),
                    )
                    created += 1
                elif str(existing["account_kind"]) != account_kind or str(existing["status"]) != "active":
                    connection.execute(
                        """UPDATE contact_provider_registrations
                            SET account_kind=?,status='active',updated_at=? WHERE provider=?""",
                        (account_kind, now, provider),
                    )
                    updated += 1
                else:
                    unchanged += 1
            connection.commit()
        return {"created": created, "updated": updated, "unchanged": unchanged}

    @staticmethod
    def _context(context: ContactMutationContext | None) -> ContactMutationContext:
        return context or ContactMutationContext()

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        *,
        context: ContactMutationContext | None,
        action: str,
        entity_type: str,
        entity_id: int | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        selected = SQLiteContactStore._context(context)
        previous = connection.execute(
            "SELECT event_hash FROM contact_audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous is not None else None
        event_id = str(uuid.uuid4())
        occurred_at = _now()
        safe_metadata_json = json.dumps(
            dict(metadata or {}),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        canonical = json.dumps(
            {
                "event_id": event_id,
                "occurred_at": occurred_at,
                "actor_app_user_id": selected.actor_app_user_id,
                "messenger_account_id": selected.messenger_account_id,
                "provider": selected.provider,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "request_id": selected.request_id,
                "safe_metadata_json": safe_metadata_json,
                "previous_event_hash": previous_hash,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        connection.execute(
            """
            INSERT INTO contact_audit_events(
                event_id,occurred_at,actor_app_user_id,messenger_account_id,provider,
                action,entity_type,entity_id,request_id,safe_metadata_json,
                previous_event_hash,event_hash
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                occurred_at,
                selected.actor_app_user_id,
                selected.messenger_account_id,
                selected.provider,
                action,
                entity_type,
                entity_id,
                selected.request_id,
                safe_metadata_json,
                previous_hash,
                event_hash,
            ),
        )

    def list_audit_events(
        self,
        *,
        contact_id: int | None = None,
        limit: int = 200,
    ) -> tuple[dict[str, Any], ...]:
        """Return the safe append-only audit trail without contact PII."""

        self.initialize()
        if not 1 <= int(limit) <= 2_000:
            raise ValueError("Audit limit must be between 1 and 2000.")
        where = "WHERE entity_type='contact' AND entity_id=?" if contact_id is not None else ""
        params: tuple[object, ...] = (
            (int(contact_id), int(limit)) if contact_id is not None else (int(limit),)
        )
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM contact_audit_events {where}
                    ORDER BY sequence DESC LIMIT ?""",
                params,
            ).fetchall()
        return tuple(
            {
                "sequence": int(row["sequence"]),
                "event_id": str(row["event_id"]),
                "occurred_at": str(row["occurred_at"]),
                "actor_app_user_id": row["actor_app_user_id"],
                "messenger_account_id": row["messenger_account_id"],
                "provider": row["provider"],
                "action": str(row["action"]),
                "entity_type": str(row["entity_type"]),
                "entity_id": row["entity_id"],
                "request_id": row["request_id"],
                "safe_metadata": json.loads(str(row["safe_metadata_json"])),
                "previous_event_hash": row["previous_event_hash"],
                "event_hash": str(row["event_hash"]),
            }
            for row in rows
        )

    def verify_audit_chain(self) -> bool:
        """Verify ordering and hashes for the complete shared-directory audit chain."""

        self.initialize()
        previous_hash: str | None = None
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM contact_audit_events ORDER BY sequence"
            ).fetchall()
        for row in rows:
            if row["previous_event_hash"] != previous_hash:
                return False
            canonical = json.dumps(
                {
                    "event_id": str(row["event_id"]),
                    "occurred_at": str(row["occurred_at"]),
                    "actor_app_user_id": row["actor_app_user_id"],
                    "messenger_account_id": row["messenger_account_id"],
                    "provider": row["provider"],
                    "action": str(row["action"]),
                    "entity_type": str(row["entity_type"]),
                    "entity_id": row["entity_id"],
                    "request_id": row["request_id"],
                    "safe_metadata_json": str(row["safe_metadata_json"]),
                    "previous_event_hash": row["previous_event_hash"],
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != row["event_hash"]:
                return False
            previous_hash = str(row["event_hash"])
        return True

    @staticmethod
    def _contact_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        contact_id = int(row["contact_id"])
        phones = [
            str(item["normalized_phone"])
            for item in connection.execute(
                "SELECT normalized_phone FROM contact_phones WHERE contact_id=? ORDER BY phone_id",
                (contact_id,),
            )
        ]
        categories = [
            {"id": int(item["category_id"]), "name": str(item["name"])}
            for item in connection.execute(
                """
                SELECT c.category_id,c.name FROM contact_categories c
                JOIN contact_category_members m ON m.category_id=c.category_id
                WHERE m.contact_id=? ORDER BY c.name
                """,
                (contact_id,),
            )
        ]
        return {
            "id": contact_id,
            "first_name": str(row["first_name"]),
            "last_name": str(row["last_name"]),
            "phones": phones,
            "username": str(row["username"]),
            "eitaa_user_id": row["eitaa_user_id"],
            "access_hash_present": bool(row["access_hash"]),
            "organization": str(row["organization"]),
            "notes": str(row["notes"]),
            "source": str(row["source"]),
            "sendable": bool(row["sendable"]),
            "opt_out": bool(row["opt_out"]),
            "last_resolved_at": row["last_resolved_at"],
            "categories": categories,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "created_by_app_user_id": row["created_by_app_user_id"],
            "updated_by_app_user_id": row["updated_by_app_user_id"],
            "created_by": row["created_by_app_user_id"],
            "updated_by": row["updated_by_app_user_id"],
            "revision": int(row["revision"]),
        }

    def list_contacts(
        self,
        *,
        search: str = "",
        category_ids: Sequence[int] = (),
        include_archived: bool = False,
        limit: int = 2_000,
        offset: int = 0,
    ) -> tuple[dict[str, Any], ...]:
        self.initialize()
        if not 1 <= limit <= 50_000:
            raise ValueError("Contact limit must be between 1 and 50000.")
        if offset < 0:
            raise ValueError("Contact offset cannot be negative.")
        clauses = ["1=1" if include_archived else "c.archived_at IS NULL"]
        params: list[object] = []
        if search.strip():
            clauses.append(
                """(c.first_name LIKE ? OR c.last_name LIKE ? OR c.username LIKE ?
                OR c.organization LIKE ? OR c.notes LIKE ?
                OR EXISTS (SELECT 1 FROM contact_phones p
                           WHERE p.contact_id=c.contact_id AND p.normalized_phone LIKE ?))"""
            )
            pattern = f"%{search.strip()}%"
            params.extend([pattern] * 6)
        if category_ids:
            placeholders = ",".join("?" for _ in category_ids)
            clauses.append(
                f"""EXISTS (SELECT 1 FROM contact_category_members m
                    WHERE m.contact_id=c.contact_id AND m.category_id IN ({placeholders}))"""
            )
            params.extend(int(value) for value in category_ids)
        params.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT c.* FROM contacts c WHERE {' AND '.join(clauses)} ORDER BY c.updated_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return tuple(self._contact_dict(connection, row) for row in rows)

    def get_contacts(self, contact_ids: Sequence[int]) -> tuple[dict[str, Any], ...]:
        """Return selected non-archived contacts in caller order."""

        self.initialize()
        ordered = tuple(dict.fromkeys(int(value) for value in contact_ids if int(value) > 0))
        if not ordered:
            return ()
        placeholders = ",".join("?" for _ in ordered)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM contacts WHERE archived_at IS NULL AND contact_id IN ({placeholders})",
                ordered,
            ).fetchall()
            by_id = {int(row["contact_id"]): self._contact_dict(connection, row) for row in rows}
        return tuple(by_id[value] for value in ordered if value in by_id)

    def find_contacts_by_eitaa_identity(
        self,
        *,
        eitaa_user_ids: Sequence[int] = (),
        phones: Sequence[object] = (),
        messenger_account_id: str | None = None,
        include_legacy_global_identity: bool = False,
    ) -> tuple[dict[str, Any], ...]:
        """Return shared contacts matching phones or the selected account's Eitaa IDs."""

        self.initialize()
        user_ids = tuple(dict.fromkeys(
            int(value) for value in eitaa_user_ids if int(value) > 0
        ))
        normalized_phones: list[str] = []
        for value in phones:
            try:
                normalized = normalize_phone(value)
            except ValueError:
                continue
            if normalized not in normalized_phones:
                normalized_phones.append(normalized)
        if not user_ids and not normalized_phones:
            return ()

        identity_clauses: list[str] = []
        params: list[object] = []
        if user_ids:
            placeholders = ",".join("?" for _ in user_ids)
            if messenger_account_id:
                if include_legacy_global_identity:
                    identity_clauses.append(
                        f"c.eitaa_user_id IN ({placeholders})"
                    )
                    params.extend(user_ids)
                fingerprints = [
                    provider_subject_fingerprint("eitaa", value) for value in user_ids
                ]
                identity_clauses.append(
                    f"""EXISTS (
                        SELECT 1 FROM contact_account_bindings b
                        WHERE b.contact_id=c.contact_id
                        AND b.messenger_account_id=? AND b.provider='eitaa'
                        AND b.provider_subject_fingerprint IN ({placeholders})
                    )"""
                )
                params.append(str(messenger_account_id))
                params.extend(fingerprints)
            else:
                identity_clauses.append(f"c.eitaa_user_id IN ({placeholders})")
                params.extend(user_ids)
        if normalized_phones:
            placeholders = ",".join("?" for _ in normalized_phones)
            identity_clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM contact_phones p
                    WHERE p.contact_id=c.contact_id
                    AND p.normalized_phone IN ({placeholders})
                )"""
            )
            params.extend(normalized_phones)
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT c.* FROM contacts c
                    WHERE c.archived_at IS NULL
                    AND ({' OR '.join(identity_clauses)})
                    ORDER BY c.updated_at DESC""",
                params,
            ).fetchall()
            return tuple(self._contact_dict(connection, row) for row in rows)

    def count_contacts(
        self,
        *,
        search: str = "",
        category_ids: Sequence[int] = (),
        include_archived: bool = False,
    ) -> int:
        """Count contacts using the same local filters as :meth:`list_contacts`."""

        self.initialize()
        clauses = ["1=1" if include_archived else "c.archived_at IS NULL"]
        params: list[object] = []
        if search.strip():
            clauses.append(
                """(c.first_name LIKE ? OR c.last_name LIKE ? OR c.username LIKE ?
                OR c.organization LIKE ? OR c.notes LIKE ?
                OR EXISTS (SELECT 1 FROM contact_phones p
                           WHERE p.contact_id=c.contact_id AND p.normalized_phone LIKE ?))"""
            )
            pattern = f"%{search.strip()}%"
            params.extend([pattern] * 6)
        if category_ids:
            placeholders = ",".join("?" for _ in category_ids)
            clauses.append(
                f"""EXISTS (SELECT 1 FROM contact_category_members m
                    WHERE m.contact_id=c.contact_id AND m.category_id IN ({placeholders}))"""
            )
            params.extend(int(value) for value in category_ids)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS total FROM contacts c WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
        return int(row["total"] if row else 0)

    def list_categories(self) -> tuple[dict[str, Any], ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.category_id,c.name,COUNT(p.contact_id) AS member_count
                    ,c.created_at,c.updated_at,c.created_by_app_user_id,c.updated_by_app_user_id
                FROM contact_categories c
                LEFT JOIN contact_category_members m ON m.category_id=c.category_id
                LEFT JOIN contacts p ON p.contact_id=m.contact_id AND p.archived_at IS NULL
                GROUP BY c.category_id,c.name ORDER BY c.name
                """
            ).fetchall()
        return tuple(
            {
                "id": int(row["category_id"]),
                "name": str(row["name"]),
                "member_count": int(row["member_count"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "created_by_app_user_id": row["created_by_app_user_id"],
                "updated_by_app_user_id": row["updated_by_app_user_id"],
            }
            for row in rows
        )

    def save_category(
        self,
        *,
        name: str,
        category_id: int | None = None,
        context: ContactMutationContext | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        selected = name.strip()
        if not selected or len(selected) > 120:
            raise ValueError("Category name must contain 1 to 120 characters.")
        now = _now()
        selected_context = self._context(context)
        try:
            with self._connect() as connection:
                if category_id is None:
                    cursor = connection.execute(
                        """INSERT INTO contact_categories(
                            name,created_at,updated_at,created_by_app_user_id,updated_by_app_user_id
                        ) VALUES(?,?,?,?,?)""",
                        (
                            selected,
                            now,
                            now,
                            selected_context.actor_app_user_id,
                            selected_context.actor_app_user_id,
                        ),
                    )
                    category_id = int(cursor.lastrowid)
                    action = "category.created"
                else:
                    cursor = connection.execute(
                        """UPDATE contact_categories
                            SET name=?,updated_at=?,updated_by_app_user_id=COALESCE(?,updated_by_app_user_id)
                            WHERE category_id=?""",
                        (selected, now, selected_context.actor_app_user_id, int(category_id)),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("Contact category was not found.")
                    action = "category.updated"
                self._append_audit(
                    connection,
                    context=selected_context,
                    action=action,
                    entity_type="category",
                    entity_id=int(category_id),
                )
            return next(item for item in self.list_categories() if item["id"] == category_id)
        except sqlite3.IntegrityError as exc:
            raise ValueError("A category with this name already exists.") from exc

    def delete_category(
        self,
        category_id: int,
        *,
        context: ContactMutationContext | None = None,
    ) -> None:
        """Delete only the local category; contacts survive by foreign-key design."""

        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM contact_categories WHERE category_id=?", (int(category_id),)
            )
            if cursor.rowcount != 1:
                raise ValueError("Contact category was not found.")
            self._append_audit(
                connection,
                context=context,
                action="category.deleted",
                entity_type="category",
                entity_id=int(category_id),
            )

    def _merge_duplicate_contacts(
        self,
        connection: sqlite3.Connection,
        contact_ids: Sequence[int],
        *,
        context: ContactMutationContext | None,
    ) -> tuple[int, tuple[int, ...]]:
        """Merge contacts bridged by one imported row into the oldest numeric record."""

        ordered = tuple(sorted({int(value) for value in contact_ids}))
        winner_id = ordered[0]
        loser_ids = ordered[1:]
        for loser_id in loser_ids:
            winner = connection.execute(
                "SELECT * FROM contacts WHERE contact_id=?", (winner_id,)
            ).fetchone()
            loser = connection.execute(
                "SELECT * FROM contacts WHERE contact_id=?", (loser_id,)
            ).fetchone()
            if winner is None or loser is None:
                raise ValueError("A duplicate contact disappeared during merge.")

            merged_text: dict[str, str] = {}
            for field in (
                "first_name",
                "last_name",
                "username",
                "organization",
                "notes",
                "source",
            ):
                winner_value = str(winner[field] or "")
                loser_value = str(loser[field] or "")
                merged_text[field] = winner_value or loser_value
            winner_eitaa_id = winner["eitaa_user_id"]
            loser_eitaa_id = loser["eitaa_user_id"]
            merged_eitaa_id = winner_eitaa_id or loser_eitaa_id
            merged_access_hash = str(winner["access_hash"] or "") or str(
                loser["access_hash"] or ""
            )
            # Release a legacy global identity before moving it to the winner.
            if winner_eitaa_id is None and loser_eitaa_id is not None:
                connection.execute(
                    "UPDATE contacts SET eitaa_user_id=NULL,access_hash='' WHERE contact_id=?",
                    (loser_id,),
                )
            connection.execute(
                """
                UPDATE contacts SET
                    first_name=?,last_name=?,username=?,organization=?,notes=?,source=?,
                    eitaa_user_id=?,access_hash=?,sendable=?,opt_out=?,
                    last_resolved_at=COALESCE(last_resolved_at,?),
                    created_at=CASE WHEN created_at <= ? THEN created_at ELSE ? END,
                    created_by_app_user_id=COALESCE(created_by_app_user_id,?),
                    updated_at=?,updated_by_app_user_id=COALESCE(?,updated_by_app_user_id),
                    revision=revision+1
                WHERE contact_id=?
                """,
                (
                    merged_text["first_name"],
                    merged_text["last_name"],
                    merged_text["username"],
                    merged_text["organization"],
                    merged_text["notes"],
                    merged_text["source"],
                    merged_eitaa_id,
                    merged_access_hash,
                    1 if bool(winner["sendable"]) or bool(loser["sendable"]) else 0,
                    1 if bool(winner["opt_out"]) or bool(loser["opt_out"]) else 0,
                    loser["last_resolved_at"],
                    str(loser["created_at"]),
                    str(loser["created_at"]),
                    loser["created_by_app_user_id"],
                    _now(),
                    self._context(context).actor_app_user_id,
                    winner_id,
                ),
            )
            connection.execute(
                "UPDATE contact_phones SET contact_id=? WHERE contact_id=?",
                (winner_id, loser_id),
            )
            connection.execute(
                """INSERT OR IGNORE INTO contact_category_members(contact_id,category_id)
                    SELECT ?,category_id FROM contact_category_members WHERE contact_id=?""",
                (winner_id, loser_id),
            )
            bindings = connection.execute(
                "SELECT * FROM contact_account_bindings WHERE contact_id=?",
                (loser_id,),
            ).fetchall()
            for binding in bindings:
                existing = connection.execute(
                    """SELECT * FROM contact_account_bindings
                        WHERE contact_id=? AND messenger_account_id=? AND provider=?""",
                    (
                        winner_id,
                        binding["messenger_account_id"],
                        binding["provider"],
                    ),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "UPDATE contact_account_bindings SET contact_id=? WHERE binding_id=?",
                        (winner_id, binding["binding_id"]),
                    )
                    continue
                connection.execute(
                    "DELETE FROM contact_account_bindings WHERE binding_id=?",
                    (binding["binding_id"],),
                )
                subject = existing["provider_subject_fingerprint"] or binding[
                    "provider_subject_fingerprint"
                ]
                reachability = (
                    "reachable"
                    if "reachable" in {existing["reachability"], binding["reachability"]}
                    else str(existing["reachability"])
                )
                connection.execute(
                    """UPDATE contact_account_bindings
                        SET provider_subject_fingerprint=?,reachability=?,updated_at=?,
                            updated_by_app_user_id=COALESCE(?,updated_by_app_user_id)
                        WHERE binding_id=?""",
                    (
                        subject,
                        reachability,
                        _now(),
                        self._context(context).actor_app_user_id,
                        existing["binding_id"],
                    ),
                )
            connection.execute("DELETE FROM contacts WHERE contact_id=?", (loser_id,))
        if loser_ids:
            self._append_audit(
                connection,
                context=context,
                action="contact.records_merged",
                entity_type="contact",
                entity_id=winner_id,
                metadata={"merged_contact_ids": list(loser_ids), "merged_count": len(loser_ids)},
            )
        return winner_id, loser_ids

    def upsert_contact(
        self,
        payload: Mapping[str, Any],
        *,
        duplicate_policy: str = "skip",
        category_policy: str = "replace",
        status_policy: str = "replace",
        context: ContactMutationContext | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        if duplicate_policy not in {"skip", "update"}:
            raise ValueError("Duplicate policy must be skip or update.")
        if category_policy not in {"replace", "merge"}:
            raise ValueError("Category policy must be replace or merge.")
        if status_policy not in {"replace", "preserve"}:
            raise ValueError("Status policy must be replace or preserve.")
        phones: list[str] = []
        for value in payload.get("phones", []):
            phone = normalize_phone(value)
            if phone not in phones:
                phones.append(phone)
        requested_id = int(payload["id"]) if payload.get("id") is not None else None
        supplied_eitaa_user_id = payload.get("eitaa_user_id")
        eitaa_user_id = (
            int(supplied_eitaa_user_id)
            if supplied_eitaa_user_id not in (None, "")
            else None
        )
        if eitaa_user_id is not None and eitaa_user_id <= 0:
            raise ValueError("Eitaa user ID must be positive.")
        if (
            not phones
            and not str(payload.get("username") or "").strip()
            and eitaa_user_id is None
            and requested_id is None
        ):
            raise ValueError("At least one phone number, username, or Eitaa user ID is required.")
        category_ids = tuple(dict.fromkeys(int(value) for value in payload.get("category_ids", [])))
        now = _now()
        selected_context = self._context(context)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                duplicate_rows = []
                if phones:
                    placeholders = ",".join("?" for _ in phones)
                    duplicate_rows = connection.execute(
                        f"SELECT DISTINCT contact_id FROM contact_phones WHERE normalized_phone IN ({placeholders})",
                        phones,
                    ).fetchall()
                phone_duplicate_ids = {
                    int(row["contact_id"]) for row in duplicate_rows
                }
                duplicate_ids = set(phone_duplicate_ids)
                eitaa_duplicate_id: int | None = None
                if eitaa_user_id is not None:
                    eitaa_row = connection.execute(
                        "SELECT contact_id FROM contacts WHERE eitaa_user_id=?",
                        (eitaa_user_id,),
                    ).fetchone()
                    if eitaa_row is not None:
                        eitaa_duplicate_id = int(eitaa_row["contact_id"])
                        duplicate_ids.add(eitaa_duplicate_id)
                if (
                    eitaa_duplicate_id is not None
                    and phone_duplicate_ids
                    and any(
                        value != eitaa_duplicate_id for value in phone_duplicate_ids
                    )
                ):
                    raise ValueError(
                        "The phone number and Eitaa user ID belong to different existing contacts."
                    )
                duplicate_id = min(duplicate_ids) if duplicate_ids else None
                if requested_id is None and duplicate_id is not None and duplicate_policy == "skip":
                    row = connection.execute(
                        "SELECT * FROM contacts WHERE contact_id=?", (duplicate_id,)
                    ).fetchone()
                    connection.rollback()
                    result = self._contact_dict(connection, row)
                    result["duplicate"] = True
                    return result
                merged_contact_ids: tuple[int, ...] = ()
                if requested_id is None and len(duplicate_ids) > 1:
                    duplicate_id, merged_contact_ids = self._merge_duplicate_contacts(
                        connection,
                        tuple(duplicate_ids),
                        context=selected_context,
                    )
                contact_id = requested_id or duplicate_id
                existing_row = (
                    connection.execute(
                        "SELECT * FROM contacts WHERE contact_id=?", (contact_id,)
                    ).fetchone()
                    if contact_id is not None
                    else None
                )

                def text_field(name: str, maximum: int, default: str = "") -> str:
                    if name in payload:
                        return str(payload.get(name) or "").strip()[:maximum]
                    if existing_row is not None:
                        return str(existing_row[name])
                    return default

                def bool_field(name: str, default: bool) -> int:
                    if name in payload:
                        return 1 if bool(payload.get(name)) else 0
                    if existing_row is not None:
                        return int(existing_row[name])
                    return 1 if default else 0

                fields = {
                    "first_name": text_field("first_name", 200),
                    "last_name": text_field("last_name", 200),
                    "username": text_field("username", 200).lstrip("@"),
                    "eitaa_user_id": (
                        eitaa_user_id
                        if eitaa_user_id is not None
                        else existing_row["eitaa_user_id"] if existing_row is not None else None
                    ),
                    "access_hash": (
                        str(payload.get("access_hash") or "").strip()[:300]
                        if "access_hash" in payload
                        else str(existing_row["access_hash"]) if existing_row is not None else ""
                    ),
                    "organization": text_field("organization", 300),
                    "notes": text_field("notes", 2_000),
                    "source": (
                        str(payload.get("source") or "manual").strip()[:120]
                        if "source" in payload
                        else str(existing_row["source"]) if existing_row is not None else "manual"
                    ),
                    "sendable": (
                        int(existing_row["sendable"])
                        if status_policy == "preserve" and existing_row is not None
                        else bool_field("sendable", True)
                    ),
                    "opt_out": (
                        int(existing_row["opt_out"])
                        if status_policy == "preserve" and existing_row is not None
                        else bool_field("opt_out", False)
                    ),
                    "last_resolved_at": (
                        payload.get("last_resolved_at")
                        if "last_resolved_at" in payload
                        else existing_row["last_resolved_at"] if existing_row is not None else None
                    ),
                }
                if contact_id is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO contacts(
                            first_name,last_name,username,eitaa_user_id,access_hash,
                            organization,notes,source,sendable,opt_out,last_resolved_at,
                            created_at,updated_at,created_by_app_user_id,
                            updated_by_app_user_id,revision
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                        """,
                        (
                            *fields.values(),
                            now,
                            now,
                            selected_context.actor_app_user_id,
                            selected_context.actor_app_user_id,
                        ),
                    )
                    contact_id = int(cursor.lastrowid)
                    action = "contact.created"
                else:
                    if duplicate_id is not None and requested_id is not None and duplicate_id != requested_id:
                        raise ValueError("A phone number is already assigned to another contact.")
                    values = list(fields.values())
                    cursor = connection.execute(
                        """
                        UPDATE contacts SET first_name=?,last_name=?,username=?,eitaa_user_id=?,
                            access_hash=?,organization=?,notes=?,source=?,sendable=?,opt_out=?,
                            last_resolved_at=?,updated_at=?,archived_at=NULL,
                            updated_by_app_user_id=COALESCE(?,updated_by_app_user_id),
                            revision=revision+1 WHERE contact_id=?
                        """,
                        (*values, now, selected_context.actor_app_user_id, contact_id),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("Contact was not found.")
                    action = "contact.updated"
                for phone in phones:
                    connection.execute(
                        "INSERT OR IGNORE INTO contact_phones(contact_id,normalized_phone,created_at) VALUES(?,?,?)",
                        (contact_id, phone, now),
                    )
                if category_ids:
                    existing = {
                        int(row["category_id"])
                        for row in connection.execute(
                            f"SELECT category_id FROM contact_categories WHERE category_id IN ({','.join('?' for _ in category_ids)})",
                            category_ids,
                        )
                    }
                    if len(existing) != len(category_ids):
                        raise ValueError("One or more contact categories were not found.")
                if category_policy == "replace":
                    connection.execute(
                        "DELETE FROM contact_category_members WHERE contact_id=?", (contact_id,)
                    )
                connection.executemany(
                    "INSERT OR IGNORE INTO contact_category_members(contact_id,category_id) VALUES(?,?)",
                    [(contact_id, category_id) for category_id in category_ids],
                )
                self._append_audit(
                    connection,
                    context=selected_context,
                    action=action,
                    entity_type="contact",
                    entity_id=int(contact_id),
                    metadata={
                        "category_count": len(category_ids),
                        "duplicate_match": duplicate_id is not None,
                        "merged_record_count": len(merged_contact_ids),
                        "phone_count": len(phones),
                    },
                )
                connection.commit()
                row = connection.execute(
                    "SELECT * FROM contacts WHERE contact_id=?", (contact_id,)
                ).fetchone()
                result = self._contact_dict(connection, row)
                if duplicate_id is not None:
                    result["merged"] = True
                if merged_contact_ids:
                    result["merged_contact_ids"] = list(merged_contact_ids)
                return result
        except sqlite3.IntegrityError as exc:
            raise ValueError("Contact conflicts with an existing unique phone or Eitaa ID.") from exc

    def update_contact_categories(
        self,
        contact_id: int,
        category_ids: Sequence[int],
        *,
        operation: str,
        context: ContactMutationContext | None = None,
    ) -> dict[str, Any]:
        """Add, remove, or replace a local contact's category memberships."""

        self.initialize()
        if operation not in {"add", "remove", "replace"}:
            raise ValueError("Category operation must be add, remove, or replace.")
        selected_ids = tuple(dict.fromkeys(int(value) for value in category_ids))
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM contacts WHERE contact_id=? AND archived_at IS NULL",
                (int(contact_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Contact was not found.")
            if selected_ids:
                placeholders = ",".join("?" for _ in selected_ids)
                existing = {
                    int(item["category_id"])
                    for item in connection.execute(
                        f"SELECT category_id FROM contact_categories WHERE category_id IN ({placeholders})",
                        selected_ids,
                    )
                }
                if len(existing) != len(selected_ids):
                    raise ValueError("One or more contact categories were not found.")
            if operation == "replace":
                connection.execute(
                    "DELETE FROM contact_category_members WHERE contact_id=?",
                    (int(contact_id),),
                )
            elif operation == "remove" and selected_ids:
                placeholders = ",".join("?" for _ in selected_ids)
                connection.execute(
                    f"""DELETE FROM contact_category_members
                        WHERE contact_id=? AND category_id IN ({placeholders})""",
                    (int(contact_id), *selected_ids),
                )
            if operation in {"add", "replace"}:
                connection.executemany(
                    "INSERT OR IGNORE INTO contact_category_members(contact_id,category_id) VALUES(?,?)",
                    [(int(contact_id), category_id) for category_id in selected_ids],
                )
            connection.execute(
                """UPDATE contacts SET updated_at=?,
                    updated_by_app_user_id=COALESCE(?,updated_by_app_user_id),
                    revision=revision+1 WHERE contact_id=?""",
                (now, self._context(context).actor_app_user_id, int(contact_id)),
            )
            self._append_audit(
                connection,
                context=context,
                action="contact.categories_updated",
                entity_type="contact",
                entity_id=int(contact_id),
                metadata={"category_count": len(selected_ids), "operation": operation},
            )
            connection.commit()
            refreshed = connection.execute(
                "SELECT * FROM contacts WHERE contact_id=?",
                (int(contact_id),),
            ).fetchone()
            return self._contact_dict(connection, refreshed)

    def archive_contact(
        self,
        contact_id: int,
        *,
        context: ContactMutationContext | None = None,
    ) -> None:
        self.initialize()
        with self._connect() as connection:
            now = _now()
            cursor = connection.execute(
                """UPDATE contacts SET archived_at=?,updated_at=?,
                    updated_by_app_user_id=COALESCE(?,updated_by_app_user_id),
                    revision=revision+1 WHERE contact_id=? AND archived_at IS NULL""",
                (now, now, self._context(context).actor_app_user_id, int(contact_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Contact was not found or was already archived.")
            self._append_audit(
                connection,
                context=context,
                action="contact.archived",
                entity_type="contact",
                entity_id=int(contact_id),
            )

    def import_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        category_ids: Sequence[int] = (),
        duplicate_policy: str = "skip",
        category_policy: str = "replace",
        status_policy: str = "replace",
        cancel_event: Any | None = None,
        progress: Any | None = None,
        context: ContactMutationContext | None = None,
    ) -> dict[str, Any]:
        imported = updated = duplicates = errors = processed = 0
        contact_ids: list[int] = []
        for row in rows:
            if cancel_event is not None and cancel_event.is_set():
                return {
                    "processed": processed,
                    "imported": imported,
                    "updated": updated,
                    "duplicates": duplicates,
                    "errors": errors,
                    "contact_ids": contact_ids,
                    "cancelled": True,
                }
            processed += 1
            try:
                payload = dict(row)
                payload["category_ids"] = list(dict.fromkeys([*category_ids, *payload.get("category_ids", [])]))
                result = self.upsert_contact(
                    payload,
                    duplicate_policy=duplicate_policy,
                    category_policy=category_policy,
                    status_policy=status_policy,
                    context=context,
                )
                contact_id = int(result["id"])
                if contact_id not in contact_ids:
                    contact_ids.append(contact_id)
                if result.get("duplicate"):
                    duplicates += 1
                elif result.get("merged"):
                    updated += 1
                else:
                    imported += 1
            except (TypeError, ValueError):
                errors += 1
            if progress is not None and (processed % 25 == 0):
                progress(
                    {
                        "processed": processed,
                        "imported": imported,
                        "updated": updated,
                        "duplicates": duplicates,
                        "errors": errors,
                    }
                )
        return {
            "processed": processed,
            "imported": imported,
            "updated": updated,
            "duplicates": duplicates,
            "errors": errors,
            "contact_ids": contact_ids,
            "cancelled": False,
        }

    @staticmethod
    def _binding_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "binding_id": str(row["binding_id"]),
            "contact_id": int(row["contact_id"]),
            "messenger_account_id": str(row["messenger_account_id"]),
            "provider": str(row["provider"]),
            "provider_subject_present": bool(row["provider_subject_fingerprint"]),
            "reachability": str(row["reachability"]),
            "safe_reason_code": row["safe_reason_code"],
            "last_resolved_at": row["last_resolved_at"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def record_account_binding(
        self,
        *,
        contact_id: int,
        messenger_account_id: str,
        provider: str,
        provider_user_id: object | None = None,
        reachability: str = "reachable",
        safe_reason_code: str | None = None,
        last_resolved_at: str | None = None,
        context: ContactMutationContext | None = None,
    ) -> dict[str, Any]:
        """Upsert one provider identity without storing credentials or raw provider IDs."""

        self.initialize()
        account_id = str(messenger_account_id or "").strip()
        selected_provider = str(provider or "").strip().lower()
        if not account_id:
            raise ValueError("Messenger account is required for a contact binding.")
        try:
            parsed_account_id = uuid.UUID(account_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Messenger account is not valid.") from exc
        if parsed_account_id.version != 4 or str(parsed_account_id) != account_id:
            raise ValueError("Messenger account is not valid.")
        if not _PROVIDER_ID.fullmatch(selected_provider):
            raise ValueError("Contact binding provider is not valid.")
        if reachability not in {"unknown", "reachable", "unreachable", "blocked"}:
            raise ValueError("Contact binding reachability is not valid.")
        fingerprint = (
            provider_subject_fingerprint(selected_provider, provider_user_id)
            if provider_user_id not in (None, "")
            else None
        )
        selected_context = self._context(context)
        if (
            selected_context.messenger_account_id
            and selected_context.messenger_account_id != account_id
        ):
            raise ValueError("Contact binding does not match the trusted account context.")
        if selected_context.provider and selected_context.provider != selected_provider:
            raise ValueError("Contact binding does not match the trusted provider context.")
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            registered_provider = connection.execute(
                """SELECT provider FROM contact_provider_registrations
                    WHERE provider=? AND status='active'""",
                (selected_provider,),
            ).fetchone()
            if registered_provider is None:
                raise ValueError("Contact binding provider is not registered.")
            contact = connection.execute(
                "SELECT contact_id FROM contacts WHERE contact_id=? AND archived_at IS NULL",
                (int(contact_id),),
            ).fetchone()
            if contact is None:
                raise ValueError("Contact was not found.")
            canonical_contact_id = int(contact_id)
            if fingerprint:
                subject_binding = connection.execute(
                    """SELECT contact_id FROM contact_account_bindings
                        WHERE messenger_account_id=? AND provider=?
                        AND provider_subject_fingerprint=?""",
                    (account_id, selected_provider, fingerprint),
                ).fetchone()
                if (
                    subject_binding is not None
                    and int(subject_binding["contact_id"]) != canonical_contact_id
                ):
                    canonical_contact_id, _ = self._merge_duplicate_contacts(
                        connection,
                        (canonical_contact_id, int(subject_binding["contact_id"])),
                        context=selected_context,
                    )
            existing = connection.execute(
                """SELECT * FROM contact_account_bindings
                    WHERE contact_id=? AND messenger_account_id=? AND provider=?""",
                (canonical_contact_id, account_id, selected_provider),
            ).fetchone()
            if existing is None:
                binding_id = str(uuid.uuid4())
                connection.execute(
                    """INSERT INTO contact_account_bindings(
                        binding_id,contact_id,messenger_account_id,provider,
                        provider_subject_fingerprint,reachability,safe_reason_code,
                        last_resolved_at,created_at,updated_at,
                        created_by_app_user_id,updated_by_app_user_id
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        binding_id,
                        canonical_contact_id,
                        account_id,
                        selected_provider,
                        fingerprint,
                        reachability,
                        str(safe_reason_code or "")[:120] or None,
                        last_resolved_at,
                        now,
                        now,
                        selected_context.actor_app_user_id,
                        selected_context.actor_app_user_id,
                    ),
                )
                action = "contact.account_binding_created"
            else:
                binding_id = str(existing["binding_id"])
                connection.execute(
                    """UPDATE contact_account_bindings SET
                        provider_subject_fingerprint=COALESCE(?,provider_subject_fingerprint),
                        reachability=?,safe_reason_code=?,
                        last_resolved_at=COALESCE(?,last_resolved_at),updated_at=?,
                        updated_by_app_user_id=COALESCE(?,updated_by_app_user_id)
                        WHERE binding_id=?""",
                    (
                        fingerprint,
                        reachability,
                        str(safe_reason_code or "")[:120] or None,
                        last_resolved_at,
                        now,
                        selected_context.actor_app_user_id,
                        binding_id,
                    ),
                )
                action = "contact.account_binding_updated"
            self._append_audit(
                connection,
                context=selected_context,
                action=action,
                entity_type="contact",
                entity_id=canonical_contact_id,
                metadata={
                    "provider_subject_present": fingerprint is not None,
                    "reachability": reachability,
                    "safe_reason_code": str(safe_reason_code or "")[:120] or None,
                },
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM contact_account_bindings WHERE binding_id=?",
                (binding_id,),
            ).fetchone()
            return self._binding_dict(row)

    def selected_account_bindings(
        self,
        contact_ids: Sequence[int],
        *,
        messenger_account_id: str,
        provider: str,
    ) -> dict[int, dict[str, Any]]:
        """Return only bindings for the already-authorized selected account."""

        self.initialize()
        selected_ids = tuple(dict.fromkeys(int(value) for value in contact_ids))
        if not selected_ids:
            return {}
        selected_provider = str(provider or "").strip().lower()
        if not _PROVIDER_ID.fullmatch(selected_provider):
            raise ValueError("Contact binding provider is not valid.")
        placeholders = ",".join("?" for _ in selected_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM contact_account_bindings
                    WHERE messenger_account_id=? AND provider=?
                    AND contact_id IN ({placeholders})""",
                (str(messenger_account_id), selected_provider, *selected_ids),
            ).fetchall()
        return {int(row["contact_id"]): self._binding_dict(row) for row in rows}

    def build_targets(
        self,
        *,
        category_ids: Sequence[int] = (),
        include_contact_ids: Sequence[int] = (),
        exclude_contact_ids: Sequence[int] = (),
        max_targets: int = 10_000,
    ) -> dict[str, Any]:
        if max_targets < 1 or max_targets > 10_000:
            raise ValueError("max_targets must be between 1 and 10000.")
        contacts = self.list_contacts(category_ids=category_ids, limit=50_000)
        include = {int(value) for value in include_contact_ids}
        exclude = {int(value) for value in exclude_contact_ids}
        if include:
            known = {int(item["id"]): item for item in contacts}
            for item in self.list_contacts(limit=50_000):
                if int(item["id"]) in include:
                    known[int(item["id"])] = item
            contacts = tuple(known.values())
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        omitted = {"opt_out": 0, "not_sendable": 0, "no_phone": 0, "excluded": 0, "duplicate_phone": 0}
        for contact in contacts:
            contact_id = int(contact["id"])
            if contact_id in exclude:
                omitted["excluded"] += 1
                continue
            if contact["opt_out"]:
                omitted["opt_out"] += 1
                continue
            if not contact["sendable"]:
                omitted["not_sendable"] += 1
                continue
            phones = list(contact["phones"])
            if not phones:
                omitted["no_phone"] += 1
                continue
            for phone in phones:
                if phone in seen:
                    omitted["duplicate_phone"] += 1
                    continue
                if len(targets) >= max_targets:
                    return {
                        "targets": targets,
                        "target_count": len(targets),
                        "omitted": omitted,
                        "truncated": True,
                        "max_targets": max_targets,
                    }
                seen.add(phone)
                targets.append({"contact_id": contact_id, "phone": phone, "name": f"{contact['first_name']} {contact['last_name']}".strip()})
        return {
            "targets": targets,
            "target_count": len(targets),
            "omitted": omitted,
            "truncated": False,
            "max_targets": max_targets,
        }
