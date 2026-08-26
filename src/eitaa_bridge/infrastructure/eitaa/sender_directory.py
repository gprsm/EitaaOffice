"""Persist human-readable message authors exposed by Eitaa history responses."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable, Sequence

from eitaa_core.infrastructure.codec.tl import TLReader
from eitaa_core.infrastructure.contacts import constructors as contact_constructors
from eitaa_core.infrastructure.contacts.codec import ContactsCodec
from eitaa_core.infrastructure.history.response import HistoryResponseCodec

from ..data_scope import ProviderAccountScope


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteSenderDirectory:
    """Minimal local directory keyed by provider, account, and user ID."""

    def __init__(
        self,
        path: Path | str,
        *,
        scope: ProviderAccountScope | None = None,
    ):
        self.path = Path(path)
        self.scope = scope or ProviderAccountScope.legacy()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(sender_profiles)")
            }
            if columns and "provider" not in columns:
                self._backup_connection(connection)
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "ALTER TABLE sender_profiles RENAME TO sender_profiles_legacy"
                )
                connection.execute(
                    """
                    CREATE TABLE sender_profiles (
                        provider TEXT NOT NULL,
                        messenger_account_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        display_name TEXT NOT NULL DEFAULT '',
                        username TEXT NOT NULL DEFAULT '',
                        is_eitaa_contact INTEGER NOT NULL DEFAULT 0
                            CHECK(is_eitaa_contact IN (0,1)),
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(provider,messenger_account_id,user_id)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX idx_sender_profiles_account
                        ON sender_profiles(provider,messenger_account_id,user_id)
                    """
                )
                connection.execute(
                    """
                    INSERT INTO sender_profiles(
                        provider,messenger_account_id,user_id,display_name,username,
                        is_eitaa_contact,updated_at
                    )
                    SELECT ?,?,user_id,display_name,username,is_eitaa_contact,updated_at
                    FROM sender_profiles_legacy
                    """,
                    (self.scope.provider, self.scope.messenger_account_id),
                )
                connection.execute("DROP TABLE sender_profiles_legacy")
                connection.execute("PRAGMA user_version=2")
                connection.commit()
            elif not columns:
                connection.executescript(
                    """
                    CREATE TABLE sender_profiles (
                        provider TEXT NOT NULL,
                        messenger_account_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        display_name TEXT NOT NULL DEFAULT '',
                        username TEXT NOT NULL DEFAULT '',
                        is_eitaa_contact INTEGER NOT NULL DEFAULT 0
                            CHECK(is_eitaa_contact IN (0,1)),
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(provider,messenger_account_id,user_id)
                    );
                    CREATE INDEX idx_sender_profiles_account
                        ON sender_profiles(provider,messenger_account_id,user_id);
                    PRAGMA user_version=2;
                    """
                )

    def upsert_users(self, users: Iterable[Any]) -> int:
        rows: list[tuple[str, str, int, str, str, int, str]] = []
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
                self.scope.provider,
                self.scope.messenger_account_id,
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
                INSERT INTO sender_profiles(
                    provider,messenger_account_id,user_id,display_name,username,
                    is_eitaa_contact,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(provider,messenger_account_id,user_id) DO UPDATE SET
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
                    f"""
                    SELECT * FROM sender_profiles
                    WHERE provider=? AND messenger_account_id=?
                      AND user_id IN ({placeholders})
                    """,
                    (self.scope.provider, self.scope.messenger_account_id, *chunk),
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

    def _backup_connection(self, connection: sqlite3.Connection) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = self.path.with_name(
            f"{self.path.stem}.schema1.{stamp}.bak.sqlite3"
        )
        with sqlite3.connect(backup_path) as backup:
            connection.backup(backup)
        return backup_path


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
_legacy_store: SQLiteSenderDirectory | None = None
_scoped_store: ContextVar[SQLiteSenderDirectory | None] = ContextVar(
    "eitaa_sender_directory_store",
    default=None,
)
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
    store = _scoped_store.get()
    if store is None:
        with _patch_lock:
            store = _legacy_store
    if store is not None and users:
        store.upsert_users(users)
    return page


def configure_sender_directory(
    path: Path | str,
    *,
    legacy_default: bool = True,
    scope: ProviderAccountScope | None = None,
) -> SQLiteSenderDirectory:
    """Create a store and install the pinned-Core history hook once.

    Account runtimes pass ``legacy_default=False`` and bind the returned store
    through :func:`sender_directory_scope`. The fallback is retained only for
    the explicit single-session Legacy runtime.
    """

    global _legacy_store, _patch_installed
    store = SQLiteSenderDirectory(path, scope=scope)
    with _patch_lock:
        if legacy_default:
            _legacy_store = store
        if not _patch_installed:
            HistoryResponseCodec.parse = staticmethod(_patched_history_parse)
            _patch_installed = True
    return store


@contextmanager
def sender_directory_scope(store: SQLiteSenderDirectory):
    """Bind history sender persistence to the current account operation."""

    token = _scoped_store.set(store)
    try:
        yield
    finally:
        _scoped_store.reset(token)


def current_sender_directory() -> SQLiteSenderDirectory | None:
    """Return the scoped store, or the explicit Legacy fallback for diagnostics."""

    selected = _scoped_store.get()
    if selected is not None:
        return selected
    with _patch_lock:
        return _legacy_store


def clear_legacy_sender_directory(store: SQLiteSenderDirectory) -> None:
    """Clear the Legacy fallback only when it is still owned by ``store``."""

    global _legacy_store
    with _patch_lock:
        if _legacy_store is store:
            _legacy_store = None
