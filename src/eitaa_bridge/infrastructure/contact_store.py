"""Bridge-owned local contact directory with conservative deduplication."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from ..errors import ContactDirectoryError


CONTACT_SCHEMA = 1
_PHONE_CLEAN = re.compile(r"[^\d+]")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def initialize(self) -> None:
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
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        backup = self.path.with_name(f"{self.path.stem}.schema0.{stamp}.bak.sqlite3")
                        backup_connection = sqlite3.connect(backup)
                        try:
                            connection.backup(backup_connection)
                        finally:
                            backup_connection.close()
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
                            archived_at TEXT
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
                            updated_at TEXT NOT NULL
                        );
                        CREATE TABLE contact_category_members (
                            contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                            category_id INTEGER NOT NULL REFERENCES contact_categories(category_id) ON DELETE CASCADE,
                            PRIMARY KEY(contact_id, category_id)
                        );
                        CREATE INDEX idx_contact_category_members_category
                            ON contact_category_members(category_id, contact_id);
                        PRAGMA user_version=1;
                        COMMIT;
                        """
                    )
        except ContactDirectoryError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise ContactDirectoryError(
                "Contact database could not be initialized.",
                safe_context={"error_type": type(exc).__name__, "file_name": self.path.name},
            ) from exc

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
            "updated_at": str(row["updated_at"]),
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
    ) -> tuple[dict[str, Any], ...]:
        """Return local contacts matching Eitaa user IDs or normalized phone numbers."""

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
                FROM contact_categories c
                LEFT JOIN contact_category_members m ON m.category_id=c.category_id
                LEFT JOIN contacts p ON p.contact_id=m.contact_id AND p.archived_at IS NULL
                GROUP BY c.category_id,c.name ORDER BY c.name
                """
            ).fetchall()
        return tuple(
            {"id": int(row["category_id"]), "name": str(row["name"]), "member_count": int(row["member_count"])}
            for row in rows
        )

    def save_category(self, *, name: str, category_id: int | None = None) -> dict[str, Any]:
        self.initialize()
        selected = name.strip()
        if not selected or len(selected) > 120:
            raise ValueError("Category name must contain 1 to 120 characters.")
        now = _now()
        try:
            with self._connect() as connection:
                if category_id is None:
                    cursor = connection.execute(
                        "INSERT INTO contact_categories(name,created_at,updated_at) VALUES(?,?,?)",
                        (selected, now, now),
                    )
                    category_id = int(cursor.lastrowid)
                else:
                    cursor = connection.execute(
                        "UPDATE contact_categories SET name=?,updated_at=? WHERE category_id=?",
                        (selected, now, int(category_id)),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("Contact category was not found.")
            return next(item for item in self.list_categories() if item["id"] == category_id)
        except sqlite3.IntegrityError as exc:
            raise ValueError("A category with this name already exists.") from exc

    def delete_category(self, category_id: int) -> None:
        """Delete only the local category; contacts survive by foreign-key design."""

        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM contact_categories WHERE category_id=?", (int(category_id),)
            )
            if cursor.rowcount != 1:
                raise ValueError("Contact category was not found.")

    def upsert_contact(
        self,
        payload: Mapping[str, Any],
        *,
        duplicate_policy: str = "skip",
        category_policy: str = "replace",
        status_policy: str = "replace",
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
                duplicate_ids = {int(row["contact_id"]) for row in duplicate_rows}
                if eitaa_user_id is not None:
                    eitaa_row = connection.execute(
                        "SELECT contact_id FROM contacts WHERE eitaa_user_id=?",
                        (eitaa_user_id,),
                    ).fetchone()
                    if eitaa_row is not None:
                        duplicate_ids.add(int(eitaa_row["contact_id"]))
                if len(duplicate_ids) > 1:
                    raise ValueError(
                        "The phone number and Eitaa user ID belong to different existing contacts."
                    )
                duplicate_id = next(iter(duplicate_ids), None)
                if requested_id is None and duplicate_id is not None and duplicate_policy == "skip":
                    row = connection.execute(
                        "SELECT * FROM contacts WHERE contact_id=?", (duplicate_id,)
                    ).fetchone()
                    connection.rollback()
                    result = self._contact_dict(connection, row)
                    result["duplicate"] = True
                    return result
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
                    "opt_out": bool_field("opt_out", False),
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
                            created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (*fields.values(), now, now),
                    )
                    contact_id = int(cursor.lastrowid)
                else:
                    if duplicate_id is not None and requested_id is not None and duplicate_id != requested_id:
                        raise ValueError("A phone number is already assigned to another contact.")
                    values = list(fields.values())
                    cursor = connection.execute(
                        """
                        UPDATE contacts SET first_name=?,last_name=?,username=?,eitaa_user_id=?,
                            access_hash=?,organization=?,notes=?,source=?,sendable=?,opt_out=?,
                            last_resolved_at=?,updated_at=?,archived_at=NULL WHERE contact_id=?
                        """,
                        (*values, now, contact_id),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("Contact was not found.")
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
                connection.commit()
                row = connection.execute(
                    "SELECT * FROM contacts WHERE contact_id=?", (contact_id,)
                ).fetchone()
                result = self._contact_dict(connection, row)
                if duplicate_id is not None:
                    result["merged"] = True
                return result
        except sqlite3.IntegrityError as exc:
            raise ValueError("Contact conflicts with an existing unique phone or Eitaa ID.") from exc

    def update_contact_categories(
        self,
        contact_id: int,
        category_ids: Sequence[int],
        *,
        operation: str,
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
                "UPDATE contacts SET updated_at=? WHERE contact_id=?",
                (now, int(contact_id)),
            )
            connection.commit()
            refreshed = connection.execute(
                "SELECT * FROM contacts WHERE contact_id=?",
                (int(contact_id),),
            ).fetchone()
            return self._contact_dict(connection, refreshed)

    def archive_contact(self, contact_id: int) -> None:
        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE contacts SET archived_at=?,updated_at=? WHERE contact_id=? AND archived_at IS NULL",
                (_now(), _now(), int(contact_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Contact was not found or was already archived.")

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
