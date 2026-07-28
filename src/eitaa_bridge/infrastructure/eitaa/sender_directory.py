"""Persist human-readable message authors exposed by Eitaa history responses."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable, Sequence

from eitaa_core.infrastructure.codec.tl import TLReader
from eitaa_core.infrastructure.contacts import constructors as contact_constructors
from eitaa_core.infrastructure.contacts.codec import ContactsCodec
from eitaa_core.infrastructure.history.response import HistoryResponseCodec


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteSenderDirectory:
    """Minimal local directory keyed by Eitaa user ID."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sender_profiles (
                    user_id INTEGER PRIMARY KEY,
                    display_name TEXT NOT NULL DEFAULT '',
                    username TEXT NOT NULL DEFAULT '',
                    is_eitaa_contact INTEGER NOT NULL DEFAULT 0 CHECK(is_eitaa_contact IN (0,1)),
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_users(self, users: Iterable[Any]) -> int:
        rows: list[tuple[int, str, str, int, str]] = []
        timestamp = _now()
        for user in users:
            user_id = int(user.peer.id)
            display_name = str(user.display_name or "").strip()
            username = str(user.username or "").strip()
            if user_id <= 0 or (
                (not display_name or display_name == str(user_id)) and not username
            ):
                continue
            rows.append((
                user_id,
                display_name if display_name != str(user_id) else username,
                username,
                int(bool(user.is_contact)),
                timestamp,
            ))
        if not rows:
            return 0
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO sender_profiles(user_id,display_name,username,is_eitaa_contact,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    username=excluded.username,
                    is_eitaa_contact=excluded.is_eitaa_contact,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def profiles(self, user_ids: Sequence[int]) -> dict[int, dict[str, Any]]:
        selected = tuple(dict.fromkeys(int(value) for value in user_ids if int(value) > 0))
        if not selected:
            return {}
        found: dict[int, dict[str, Any]] = {}
        with self._connect() as connection:
            for start in range(0, len(selected), 500):
                chunk = selected[start:start + 500]
                placeholders = ",".join("?" for _ in chunk)
                rows = connection.execute(
                    f"SELECT * FROM sender_profiles WHERE user_id IN ({placeholders})",
                    chunk,
                ).fetchall()
                for row in rows:
                    user_id = int(row["user_id"])
                    found[user_id] = {
                        "display_name": str(row["display_name"]).strip() or None,
                        "username": str(row["username"]).strip() or None,
                        "is_eitaa_contact": bool(row["is_eitaa_contact"]),
                        "resolution": "history_user",
                    }
        return found


def extract_sender_users(data: bytes, sender_ids: set[int]) -> tuple[Any, ...]:
    """Find and validate only history User objects referenced by parsed messages."""
    if not sender_ids:
        return ()
    needle = contact_constructors.USER.to_bytes(4, "little")
    users: dict[int, Any] = {}
    position = 0
    while True:
        candidate = data.find(needle, position)
        if candidate < 0:
            break
        try:
            # Core 0.6.0.dev19 is pinned by the bridge compatibility binding.
            # Reusing its complete User parser keeps history/contact decoding aligned.
            user = ContactsCodec._parse_user(TLReader(data, candidate))
            user_id = int(user.peer.id)
            if user_id in sender_ids:
                users[user_id] = user
        except Exception:
            # Constructor bytes can occur inside arbitrary message/media data.
            # Full User parsing plus sender-ID matching makes those candidates harmless.
            pass
        position = candidate + 4
    return tuple(users.values())


_patch_lock = threading.RLock()
_active_store: SQLiteSenderDirectory | None = None
_original_history_parse = HistoryResponseCodec.parse
_patch_installed = False


def _patched_history_parse(data: bytes, peer: Any) -> Any:
    page = _original_history_parse(data, peer)
    sender_ids = {
        int(message.from_peer.id)
        for message in page.messages
        if message.from_peer is not None and message.from_peer.type.value == "user"
    }
    users = extract_sender_users(data, sender_ids)
    with _patch_lock:
        store = _active_store
    if store is not None and users:
        store.upsert_users(users)
    return page


def configure_sender_directory(path: Path | str) -> SQLiteSenderDirectory:
    """Select the active store and install the pinned-Core history hook once."""
    global _active_store, _patch_installed
    store = SQLiteSenderDirectory(path)
    with _patch_lock:
        _active_store = store
        if not _patch_installed:
            HistoryResponseCodec.parse = staticmethod(_patched_history_parse)
            _patch_installed = True
    return store
