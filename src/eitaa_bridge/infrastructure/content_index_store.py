"""Bridge-owned SQLite storage for local index suggestions and feedback."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from ..errors import LocalContentIndexStoreError
from .data_scope import DataScopeError, ProviderAccountScope


CONTENT_INDEX_SCHEMA = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteContentIndexStore:
    """Thread-safe-by-connection store that never contains raw message text."""

    def __init__(
        self,
        path: str | Path,
        *,
        scope: ProviderAccountScope | None = None,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.scope = scope or ProviderAccountScope.legacy()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > CONTENT_INDEX_SCHEMA:
                    raise LocalContentIndexStoreError(
                        "Content-index database is newer than this application.",
                        safe_context={
                            "database_version": version,
                            "supported_version": CONTENT_INDEX_SCHEMA,
                        },
                    )
                if version == 0:
                    connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE index_results (
                            site_key TEXT NOT NULL,
                            peer_type TEXT NOT NULL,
                            peer_id INTEGER NOT NULL,
                            message_id INTEGER NOT NULL,
                            text_hash TEXT NOT NULL,
                            model_version TEXT NOT NULL,
                            predictions_json TEXT NOT NULL,
                            indexed_at TEXT NOT NULL,
                            PRIMARY KEY (site_key, peer_type, peer_id, message_id)
                        );
                        CREATE INDEX idx_index_results_peer
                            ON index_results(site_key, peer_type, peer_id, message_id);

                        CREATE TABLE index_feedback (
                            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            site_key TEXT NOT NULL,
                            source_key TEXT NOT NULL,
                            label_id INTEGER NOT NULL,
                            label_name TEXT NOT NULL,
                            decision TEXT NOT NULL CHECK (decision IN ('accept', 'reject')),
                            created_at TEXT NOT NULL
                        );
                        CREATE INDEX idx_index_feedback_site
                            ON index_feedback(site_key, feedback_id);

                        CREATE TABLE index_runs (
                            job_id TEXT PRIMARY KEY,
                            site_key TEXT NOT NULL,
                            peer_type TEXT NOT NULL,
                            peer_id INTEGER NOT NULL,
                            state TEXT NOT NULL,
                            model_version TEXT,
                            labels_json TEXT NOT NULL,
                            summary_json TEXT NOT NULL,
                            started_at TEXT NOT NULL,
                            completed_at TEXT
                        );

                        CREATE TABLE index_staging_results (
                            job_id TEXT NOT NULL,
                            site_key TEXT NOT NULL,
                            peer_type TEXT NOT NULL,
                            peer_id INTEGER NOT NULL,
                            message_id INTEGER NOT NULL,
                            text_hash TEXT NOT NULL,
                            model_version TEXT NOT NULL,
                            predictions_json TEXT NOT NULL,
                            indexed_at TEXT NOT NULL,
                            PRIMARY KEY (job_id, message_id),
                            FOREIGN KEY (job_id) REFERENCES index_runs(job_id)
                                ON DELETE CASCADE
                        );
                        CREATE INDEX idx_index_staging_job
                            ON index_staging_results(job_id, message_id);
                        CREATE TABLE content_index_scopes (
                            scope_key TEXT PRIMARY KEY,
                            provider TEXT NOT NULL,
                            messenger_account_id TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            UNIQUE(provider,messenger_account_id)
                        );
                        CREATE TABLE custom_indexes (
                            site_key TEXT NOT NULL,
                            id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            aliases_json TEXT NOT NULL,
                            kind TEXT NOT NULL DEFAULT 'custom',
                            wordpress_category_id INTEGER,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            PRIMARY KEY (site_key, id)
                        );
                        CREATE INDEX idx_custom_indexes_site
                            ON custom_indexes(site_key, id);
                        PRAGMA user_version = 4;
                        COMMIT;
                        """
                    )
                elif version == 1:
                    self._backup_connection(connection, version=1)
                    connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE index_staging_results (
                            job_id TEXT NOT NULL,
                            site_key TEXT NOT NULL,
                            peer_type TEXT NOT NULL,
                            peer_id INTEGER NOT NULL,
                            message_id INTEGER NOT NULL,
                            text_hash TEXT NOT NULL,
                            model_version TEXT NOT NULL,
                            predictions_json TEXT NOT NULL,
                            indexed_at TEXT NOT NULL,
                            PRIMARY KEY (job_id, message_id),
                            FOREIGN KEY (job_id) REFERENCES index_runs(job_id)
                                ON DELETE CASCADE
                        );
                        CREATE INDEX idx_index_staging_job
                            ON index_staging_results(job_id, message_id);
                        PRAGMA user_version = 2;
                        COMMIT;
                        """
                    )
                    self._upgrade_scope_schema(connection, source_version=2)
                    self._upgrade_custom_indexes_schema(connection)
                elif version == 2:
                    self._backup_connection(connection, version=2)
                    self._upgrade_scope_schema(connection, source_version=2)
                    self._upgrade_custom_indexes_schema(connection)
                elif version == 3:
                    self._backup_connection(connection, version=3)
                    self._upgrade_custom_indexes_schema(connection)
                self._register_scope(connection)
        except LocalContentIndexStoreError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise LocalContentIndexStoreError(
                "Content-index database could not be initialized.",
                safe_context={"error_type": type(exc).__name__, "file_name": self.path.name},
            ) from exc

    def stage_results(
        self,
        *,
        job_id: str,
        site_key: str,
        peer_type: str,
        peer_id: int,
        model_version: str,
        rows: Iterable[Mapping[str, object]],
    ) -> int:
        """Store an incomplete run without exposing it as the active result set."""

        selected = list(rows)
        if not selected:
            return 0
        try:
            with self._connect() as connection:
                now = _now()
                scoped_job_id = self._job_key(job_id)
                scoped_site_key = self._site_key(site_key)
                connection.executemany(
                    """
                    INSERT INTO index_staging_results (
                        job_id,site_key,peer_type,peer_id,message_id,text_hash,
                        model_version,predictions_json,indexed_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(job_id,message_id) DO UPDATE SET
                        text_hash=excluded.text_hash,
                        model_version=excluded.model_version,
                        predictions_json=excluded.predictions_json,
                        indexed_at=excluded.indexed_at
                    """,
                    [
                        (
                            scoped_job_id,
                            scoped_site_key,
                            peer_type,
                            peer_id,
                            int(row["message_id"]),
                            str(row["text_hash"]),
                            model_version,
                            json.dumps(
                                row.get("predictions", []),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                            now,
                        )
                        for row in selected
                    ],
                )
            return len(selected)
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            raise LocalContentIndexStoreError(
                "Content-index staging results could not be saved.",
                safe_context={"error_type": type(exc).__name__, "row_count": len(selected)},
            ) from exc

    def promote_staged_results(
        self,
        *,
        job_id: str,
        site_key: str,
        peer_type: str,
        peer_id: int,
        state: str,
        model_version: str,
        summary: Mapping[str, object],
    ) -> int:
        """Atomically replace visible results with one completed/cancelled run."""

        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                scoped_job_id = self._job_key(job_id)
                scoped_site_key = self._site_key(site_key)
                staged = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM index_staging_results
                        WHERE job_id=? AND site_key=? AND peer_type=? AND peer_id=?
                        """,
                        (scoped_job_id, scoped_site_key, peer_type, peer_id),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    DELETE FROM index_results
                    WHERE site_key=? AND peer_type=? AND peer_id=?
                    """,
                    (scoped_site_key, peer_type, peer_id),
                )
                connection.execute(
                    """
                    INSERT INTO index_results (
                        site_key,peer_type,peer_id,message_id,text_hash,
                        model_version,predictions_json,indexed_at
                    )
                    SELECT site_key,peer_type,peer_id,message_id,text_hash,
                           model_version,predictions_json,indexed_at
                    FROM index_staging_results
                    WHERE job_id=? AND site_key=? AND peer_type=? AND peer_id=?
                    """,
                    (scoped_job_id, scoped_site_key, peer_type, peer_id),
                )
                connection.execute(
                    "DELETE FROM index_staging_results WHERE job_id=?", (scoped_job_id,)
                )
                connection.execute(
                    """
                    UPDATE index_runs
                    SET state=?,model_version=?,summary_json=?,completed_at=?
                    WHERE job_id=?
                    """,
                    (
                        state,
                        model_version,
                        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                        _now(),
                        scoped_job_id,
                    ),
                )
                connection.commit()
                return staged
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index staging results could not be promoted.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def discard_staged_results(self, *, job_id: str) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM index_staging_results WHERE job_id=?",
                    (self._job_key(job_id),),
                )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index staging results could not be discarded.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def save_results(
        self,
        *,
        site_key: str,
        peer_type: str,
        peer_id: int,
        model_version: str,
        rows: Iterable[Mapping[str, object]],
    ) -> int:
        selected = list(rows)
        if not selected:
            return 0
        try:
            with self._connect() as connection:
                now = _now()
                scoped_site_key = self._site_key(site_key)
                connection.executemany(
                    """
                    INSERT INTO index_results (
                        site_key,peer_type,peer_id,message_id,text_hash,
                        model_version,predictions_json,indexed_at
                    ) VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(site_key,peer_type,peer_id,message_id) DO UPDATE SET
                        text_hash=excluded.text_hash,
                        model_version=excluded.model_version,
                        predictions_json=excluded.predictions_json,
                        indexed_at=excluded.indexed_at
                    """,
                    [
                        (
                            scoped_site_key,
                            peer_type,
                            peer_id,
                            int(row["message_id"]),
                            str(row["text_hash"]),
                            model_version,
                            json.dumps(
                                row.get("predictions", []),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                            now,
                        )
                        for row in selected
                    ],
                )
            return len(selected)
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            raise LocalContentIndexStoreError(
                "Content-index results could not be saved.",
                safe_context={"error_type": type(exc).__name__, "row_count": len(selected)},
            ) from exc

    def list_results(
        self,
        *,
        site_key: str,
        peer_type: str,
        peer_id: int,
        limit: int = 50_000,
    ) -> tuple[dict[str, object], ...]:
        if not 1 <= limit <= 50_000:
            raise ValueError("Content-index result limit must be between 1 and 50000.")
        try:
            with self._connect() as connection:
                scoped_site_key = self._site_key(site_key)
                rows = connection.execute(
                    """
                    SELECT message_id,text_hash,model_version,predictions_json,indexed_at
                    FROM index_results
                    WHERE site_key=? AND peer_type=? AND peer_id=?
                    ORDER BY message_id DESC
                    LIMIT ?
                    """,
                    (scoped_site_key, peer_type, peer_id, limit),
                ).fetchall()
            return tuple(
                {
                    "message_id": int(row["message_id"]),
                    "text_hash": str(row["text_hash"]),
                    "model_version": str(row["model_version"]),
                    "predictions": json.loads(str(row["predictions_json"])),
                    "indexed_at": str(row["indexed_at"]),
                }
                for row in rows
            )
        except (json.JSONDecodeError, sqlite3.Error) as exc:
            raise LocalContentIndexStoreError(
                "Content-index results could not be read.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def list_auto_index_targets(self) -> tuple[dict[str, object], ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT DISTINCT site_key, peer_type, peer_id
                    FROM index_results
                    WHERE peer_type != 'user'
                    """
                ).fetchall()
            return tuple(
                {
                    "site_key": self.scope.strip("content-site", str(row["site_key"])),
                    "peer_type": str(row["peer_type"]),
                    "peer_id": int(row["peer_id"]),
                }
                for row in rows
            )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index targets could not be read.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def get_latest_run_labels(
        self, *, site_key: str, peer_type: str, peer_id: int
    ) -> Sequence[Mapping[str, object]] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT labels_json
                    FROM index_runs
                    WHERE site_key=? AND peer_type=? AND peer_id=?
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (self._site_key(site_key), peer_type, peer_id),
                ).fetchone()
            if row is None:
                return None
            return list(json.loads(str(row["labels_json"])))
        except (json.JSONDecodeError, sqlite3.Error):
            return None

    def add_feedback(
        self,
        *,
        site_key: str,
        source_key: str,
        label_id: int,
        label_name: str,
        decision: str,
    ) -> int:
        if decision not in {"accept", "reject"}:
            raise ValueError("Feedback decision must be accept or reject.")
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO index_feedback (
                        site_key,source_key,label_id,label_name,decision,created_at
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        self._site_key(site_key),
                        self._source_key(source_key),
                        label_id,
                        label_name,
                        decision,
                        _now(),
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index feedback could not be saved.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def list_feedback(
        self, *, site_key: str, limit: int = 10_000, newest_first: bool = False
    ) -> tuple[dict[str, object], ...]:
        if not 1 <= limit <= 10_000:
            raise ValueError("Feedback limit must be between 1 and 10000.")
        try:
            with self._connect() as connection:
                order = "DESC" if newest_first else "ASC"
                rows = connection.execute(
                    f"""
                    SELECT feedback_id,source_key,label_id,label_name,decision,created_at
                    FROM index_feedback
                    WHERE site_key=?
                    ORDER BY feedback_id {order}
                    LIMIT ?
                    """,
                    (self._site_key(site_key), limit),
                ).fetchall()
            return tuple(
                {
                    **dict(row),
                    "source_key": self.scope.strip(
                        "content-source", str(row["source_key"])
                    ),
                }
                for row in rows
            )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index feedback could not be read.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def start_run(
        self,
        *,
        job_id: str,
        site_key: str,
        peer_type: str,
        peer_id: int,
        labels: Sequence[Mapping[str, object]],
        summary: Mapping[str, object],
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO index_runs (
                        job_id,site_key,peer_type,peer_id,state,model_version,
                        labels_json,summary_json,started_at,completed_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,NULL)
                    """,
                    (
                        self._job_key(job_id),
                        self._site_key(site_key),
                        peer_type,
                        peer_id,
                        "running",
                        None,
                        json.dumps(labels, ensure_ascii=False, separators=(",", ":")),
                        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                        _now(),
                    ),
                )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index run could not be started.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def finish_run(
        self,
        *,
        job_id: str,
        state: str,
        model_version: str | None,
        summary: Mapping[str, object],
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE index_runs
                    SET state=?,model_version=?,summary_json=?,completed_at=?
                    WHERE job_id=?
                    """,
                    (
                        state,
                        model_version,
                        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                        _now(),
                        self._job_key(job_id),
                    ),
                )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index run could not be completed.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def list_custom_indexes(
        self,
        *,
        site_key: str,
    ) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                scoped_site_key = self._site_key(site_key)
                rows = connection.execute(
                    """
                    SELECT id, name, aliases_json, kind, wordpress_category_id, created_at, updated_at
                    FROM custom_indexes
                    WHERE site_key = ?
                    ORDER BY id ASC
                    """,
                    (scoped_site_key,),
                ).fetchall()
                results: list[dict[str, Any]] = []
                for row in rows:
                    raw_id = row["id"]
                    try:
                        item_id: int | str = int(raw_id) if str(raw_id).lstrip("-").isdigit() else str(raw_id)
                    except (ValueError, TypeError):
                        item_id = str(raw_id)
                    try:
                        aliases = json.loads(row["aliases_json"])
                    except (ValueError, TypeError):
                        aliases = []
                    results.append({
                        "id": item_id,
                        "name": str(row["name"]),
                        "aliases": aliases,
                        "kind": str(row["kind"]),
                        "wordpress_category_id": row["wordpress_category_id"],
                        "created_at": str(row["created_at"]),
                        "updated_at": str(row["updated_at"]),
                    })
                results.sort(key=lambda x: (0 if isinstance(x["id"], int) else 1, x["id"]))
                return results
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Custom indexes could not be retrieved.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def save_custom_index(
        self,
        *,
        site_key: str,
        index_id: str | int,
        name: str,
        aliases: Sequence[str],
        kind: str = "custom",
        wordpress_category_id: int | None = None,
    ) -> dict[str, Any]:
        str_id = str(index_id).strip()
        str_name = str(name).strip()
        cleaned_aliases = [str(a).strip() for a in aliases if str(a).strip()]
        aliases_json = json.dumps(cleaned_aliases, ensure_ascii=False, separators=(",", ":"))
        now = _now()
        try:
            with self._connect() as connection:
                scoped_site_key = self._site_key(site_key)
                connection.execute(
                    """
                    INSERT INTO custom_indexes (
                        site_key, id, name, aliases_json, kind, wordpress_category_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(site_key, id) DO UPDATE SET
                        name = excluded.name,
                        aliases_json = excluded.aliases_json,
                        kind = excluded.kind,
                        wordpress_category_id = excluded.wordpress_category_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        scoped_site_key,
                        str_id,
                        str_name,
                        aliases_json,
                        str(kind),
                        wordpress_category_id,
                        now,
                        now,
                    ),
                )
                try:
                    res_id: int | str = int(str_id) if str_id.lstrip("-").isdigit() else str_id
                except (ValueError, TypeError):
                    res_id = str_id
                return {
                    "id": res_id,
                    "name": str_name,
                    "aliases": cleaned_aliases,
                    "kind": str(kind),
                    "wordpress_category_id": wordpress_category_id,
                    "updated_at": now,
                }
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Custom index could not be saved.",
                safe_context={"error_type": type(exc).__name__, "index_id": str_id},
            ) from exc

    def delete_custom_index(
        self,
        *,
        site_key: str,
        index_id: str | int,
    ) -> bool:
        str_id = str(index_id).strip()
        try:
            with self._connect() as connection:
                scoped_site_key = self._site_key(site_key)
                cursor = connection.execute(
                    """
                    DELETE FROM custom_indexes
                    WHERE site_key = ? AND id = ?
                    """,
                    (scoped_site_key, str_id),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Custom index could not be deleted.",
                safe_context={"error_type": type(exc).__name__, "index_id": str_id},
            ) from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _backup_connection(self, connection: sqlite3.Connection, *, version: int) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = self.path.with_name(
            f"{self.path.stem}.schema{version}.{stamp}.bak.sqlite3"
        )
        try:
            with sqlite3.connect(backup_path) as backup:
                connection.backup(backup)
            return backup_path
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index backup could not be created before migration.",
                safe_context={
                    "error_type": type(exc).__name__,
                    "backup_file_name": backup_path.name,
                },
            ) from exc

    def _upgrade_scope_schema(
        self,
        connection: sqlite3.Connection,
        *,
        source_version: int,
    ) -> None:
        """Atomically namespace pre-Phase-8 rows to the opening account."""

        if source_version != 2:
            raise LocalContentIndexStoreError(
                "The content-index scope migration source is unsupported.",
                safe_context={"database_version": source_version},
            )
        site_prefix = self.scope.prefix("content-site")
        source_prefix = self.scope.prefix("content-source")
        job_prefix = self.scope.prefix("content-job")
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE content_index_scopes (
                    scope_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    messenger_account_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(provider,messenger_account_id)
                )
                """
            )
            for table in (
                "index_results",
                "index_feedback",
                "index_runs",
                "index_staging_results",
            ):
                connection.execute(
                    f"UPDATE {table} SET site_key=? || site_key",
                    (site_prefix,),
                )
            connection.execute(
                "UPDATE index_feedback SET source_key=? || source_key",
                (source_prefix,),
            )
            # Child rows are updated before the parent while FK checks are
            # disabled; the complete transaction is validated after commit.
            connection.execute(
                "UPDATE index_staging_results SET job_id=? || job_id",
                (job_prefix,),
            )
            connection.execute(
                "UPDATE index_runs SET job_id=? || job_id",
                (job_prefix,),
            )
            connection.execute(
                """
                INSERT INTO content_index_scopes(
                    scope_key,provider,messenger_account_id,created_at
                ) VALUES(?,?,?,?)
                """,
                (
                    self.scope.scope_key,
                    self.scope.provider,
                    self.scope.messenger_account_id,
                    _now(),
                ),
            )
            connection.execute("PRAGMA user_version=3")
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise LocalContentIndexStoreError(
                "The content-index scope migration violated repository integrity.",
                safe_context={"violation_count": len(violations)},
            )

    def _upgrade_custom_indexes_schema(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS custom_indexes (
                    site_key TEXT NOT NULL,
                    id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'custom',
                    wordpress_category_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (site_key, id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_custom_indexes_site
                    ON custom_indexes(site_key, id)
                """
            )
            connection.execute(f"PRAGMA user_version = {CONTENT_INDEX_SCHEMA}")
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise

    def _register_scope(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute(
                """
                INSERT INTO content_index_scopes(
                    scope_key,provider,messenger_account_id,created_at
                ) VALUES(?,?,?,?)
                ON CONFLICT(scope_key) DO NOTHING
                """,
                (
                    self.scope.scope_key,
                    self.scope.provider,
                    self.scope.messenger_account_id,
                    _now(),
                ),
            )
            row = connection.execute(
                """
                SELECT provider,messenger_account_id
                FROM content_index_scopes WHERE scope_key=?
                """,
                (self.scope.scope_key,),
            ).fetchone()
            if row is None or (
                str(row["provider"]), str(row["messenger_account_id"])
            ) != (self.scope.provider, self.scope.messenger_account_id):
                raise DataScopeError(
                    "The content-index scope registry is inconsistent.",
                    code="content_index_scope_mismatch",
                )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "The content-index account scope could not be registered.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def _site_key(self, site_key: str) -> str:
        return self.scope.key("content-site", str(site_key))

    def _source_key(self, source_key: str) -> str:
        return self.scope.key("content-source", str(source_key))

    def _job_key(self, job_id: str) -> str:
        return self.scope.key("content-job", str(job_id))
