"""Bridge-owned SQLite storage for local index suggestions and feedback."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping, Sequence

from ..errors import LocalContentIndexStoreError


CONTENT_INDEX_SCHEMA = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteContentIndexStore:
    """Thread-safe-by-connection store that never contains raw message text."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

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
                        PRAGMA user_version = 2;
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
                            job_id,
                            site_key,
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
                staged = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM index_staging_results
                        WHERE job_id=? AND site_key=? AND peer_type=? AND peer_id=?
                        """,
                        (job_id, site_key, peer_type, peer_id),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    DELETE FROM index_results
                    WHERE site_key=? AND peer_type=? AND peer_id=?
                    """,
                    (site_key, peer_type, peer_id),
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
                    (job_id, site_key, peer_type, peer_id),
                )
                connection.execute(
                    "DELETE FROM index_staging_results WHERE job_id=?", (job_id,)
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
                        job_id,
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
                    "DELETE FROM index_staging_results WHERE job_id=?", (job_id,)
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
                            site_key,
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
                rows = connection.execute(
                    """
                    SELECT message_id,text_hash,model_version,predictions_json,indexed_at
                    FROM index_results
                    WHERE site_key=? AND peer_type=? AND peer_id=?
                    ORDER BY message_id DESC
                    LIMIT ?
                    """,
                    (site_key, peer_type, peer_id, limit),
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
                    (site_key, source_key, label_id, label_name, decision, _now()),
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
                    (site_key, limit),
                ).fetchall()
            return tuple(dict(row) for row in rows)
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
                        job_id,
                        site_key,
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
                        job_id,
                    ),
                )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index run could not be completed.",
                safe_context={"error_type": type(exc).__name__},
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
