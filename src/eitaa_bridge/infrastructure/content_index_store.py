"""Bridge-owned SQLite storage for local index suggestions and feedback."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Iterator, Mapping, Sequence
import uuid

from ..errors import LocalContentIndexStoreError
from .data_scope import DataScopeError, ProviderAccountScope


CONTENT_INDEX_SCHEMA = 5


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
                            operator_id TEXT NOT NULL DEFAULT '',
                            operator_name TEXT NOT NULL DEFAULT '',
                            operator_role TEXT NOT NULL DEFAULT '',
                            review_status TEXT NOT NULL DEFAULT 'pending',
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
                            operator_id TEXT NOT NULL DEFAULT '',
                            operator_name TEXT NOT NULL DEFAULT '',
                            operator_role TEXT NOT NULL DEFAULT '',
                            review_status TEXT NOT NULL DEFAULT 'pending',
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

                        CREATE TABLE index_actions (
                            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            site_key TEXT NOT NULL,
                            peer_type TEXT NOT NULL,
                            peer_id INTEGER NOT NULL,
                            message_id INTEGER NOT NULL,
                            label_id INTEGER NOT NULL,
                            label_name TEXT NOT NULL,
                            previous_decision TEXT NOT NULL DEFAULT '',
                            new_decision TEXT NOT NULL,
                            operator_id TEXT NOT NULL DEFAULT '',
                            operator_name TEXT NOT NULL DEFAULT '',
                            operator_role TEXT NOT NULL DEFAULT 'user',
                            is_manager_override INTEGER NOT NULL DEFAULT 0,
                            overridden_operator_id TEXT NOT NULL DEFAULT '',
                            created_at TEXT NOT NULL
                        );
                        CREATE INDEX idx_index_actions_op
                            ON index_actions(operator_id, created_at);
                        CREATE INDEX idx_index_actions_msg
                            ON index_actions(peer_type, peer_id, message_id);

                        CREATE TABLE staff_tasks (
                            task_id TEXT PRIMARY KEY,
                            peer_type TEXT NOT NULL DEFAULT '',
                            peer_id INTEGER NOT NULL DEFAULT 0,
                            message_id INTEGER NOT NULL DEFAULT 0,
                            event_id TEXT NOT NULL DEFAULT '',
                            title TEXT NOT NULL,
                            description TEXT NOT NULL DEFAULT '',
                            defect_type TEXT NOT NULL DEFAULT 'general',
                            priority TEXT NOT NULL DEFAULT 'medium',
                            status TEXT NOT NULL DEFAULT 'open',
                            assigned_to_user_id TEXT NOT NULL DEFAULT '',
                            assigned_to_name TEXT NOT NULL DEFAULT '',
                            created_by_user_id TEXT NOT NULL DEFAULT '',
                            created_by_name TEXT NOT NULL DEFAULT '',
                            due_date TEXT,
                            resolution_notes TEXT NOT NULL DEFAULT '',
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            resolved_at TEXT,
                            closed_at TEXT,
                            macro_category TEXT NOT NULL DEFAULT 'workbook_approved',
                            program_codes_json TEXT NOT NULL DEFAULT '[]',
                            custom_topic TEXT NOT NULL DEFAULT '',
                            task_kind TEXT NOT NULL DEFAULT 'general',
                            unit_scope TEXT NOT NULL DEFAULT 'provincial_hq',
                            unit_name TEXT NOT NULL DEFAULT '',
                            checklist_json TEXT NOT NULL DEFAULT '[]',
                            requires_manager_approval INTEGER NOT NULL DEFAULT 1,
                            reassigned_from_user_id TEXT NOT NULL DEFAULT '',
                            reassigned_from_name TEXT NOT NULL DEFAULT '',
                            is_escalated INTEGER NOT NULL DEFAULT 0,
                            escalated_at TEXT,
                            escalation_notes TEXT NOT NULL DEFAULT ''
                        );
                        CREATE INDEX idx_staff_tasks_assigned
                            ON staff_tasks(assigned_to_user_id, status);
                        CREATE INDEX idx_staff_tasks_status
                            ON staff_tasks(status);
                        CREATE INDEX idx_staff_tasks_macro
                            ON staff_tasks(macro_category);
                        CREATE INDEX idx_staff_tasks_reassigned
                            ON staff_tasks(reassigned_from_user_id);

                        CREATE TABLE content_index_settings (
                            setting_key TEXT PRIMARY KEY,
                            setting_value TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        PRAGMA user_version = 5;
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
                    self._upgrade_v5_schema(connection)
                elif version == 2:
                    self._backup_connection(connection, version=2)
                    self._upgrade_scope_schema(connection, source_version=2)
                    self._upgrade_custom_indexes_schema(connection)
                    self._upgrade_v5_schema(connection)
                elif version == 3:
                    self._backup_connection(connection, version=3)
                    self._upgrade_custom_indexes_schema(connection)
                    self._upgrade_v5_schema(connection)
                elif version == 4:
                    self._backup_connection(connection, version=4)
                    self._upgrade_v5_schema(connection)
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
                scope_prefix = f"{self.scope.scope_key}:content-site:%"
                rows = connection.execute(
                    """
                    SELECT message_id, text_hash, model_version, predictions_json, indexed_at,
                           operator_id, operator_name, operator_role, review_status, site_key
                    FROM index_results
                    WHERE site_key LIKE ? AND peer_type=? AND peer_id=?
                    ORDER BY message_id DESC, (CASE WHEN site_key=? THEN 0 ELSE 1 END) ASC, indexed_at DESC
                    LIMIT ?
                    """,
                    (scope_prefix, peer_type, peer_id, scoped_site_key, limit),
                ).fetchall()
                results: list[dict[str, object]] = []
                seen_message_ids: set[int] = set()
                for row in rows:
                    msg_id = int(row["message_id"])
                    if msg_id in seen_message_ids:
                        continue
                    seen_message_ids.add(msg_id)
                    try:
                        predictions = json.loads(str(row["predictions_json"]))
                    except (json.JSONDecodeError, TypeError):
                        predictions = []
                    op_id = str(row["operator_id"] or "")
                    op_name = str(row["operator_name"] or "")
                    op_role = str(row["operator_role"] or "")
                    rev_status = str(row["review_status"] or "pending")
                    for pred in predictions:
                        if isinstance(pred, dict):
                            if op_id and "operator_id" not in pred:
                                pred["operator_id"] = op_id
                            if op_name and "operator_name" not in pred:
                                pred["operator_name"] = op_name
                            if op_role and "operator_role" not in pred:
                                pred["operator_role"] = op_role
                            if rev_status and "review_status" not in pred:
                                pred["review_status"] = rev_status
                    results.append(
                        {
                            "message_id": msg_id,
                            "text_hash": str(row["text_hash"]),
                            "model_version": str(row["model_version"]),
                            "predictions": predictions,
                            "indexed_at": str(row["indexed_at"]),
                            "operator_id": op_id,
                            "operator_name": op_name,
                            "operator_role": op_role,
                            "review_status": rev_status,
                        }
                    )
                return tuple(results)
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
        peer_type: str = "",
        peer_id: int = 0,
        message_id: int = 0,
        operator_id: str = "",
        operator_name: str = "",
        operator_role: str = "user",
    ) -> int:
        if decision not in {"accept", "reject"}:
            raise ValueError("Feedback decision must be accept or reject.")
        if (not peer_type or not peer_id or not message_id) and source_key:
            parts = source_key.split(":")
            if len(parts) == 3:
                try:
                    peer_type = str(parts[0])
                    peer_id = int(parts[1])
                    message_id = int(parts[2])
                except (ValueError, TypeError):
                    pass
        now = _now()
        scoped_site_key = self._site_key(site_key)
        clean_source_key = self._source_key(source_key) if source_key else f"{peer_type}:{peer_id}:{message_id}"
        role = "admin" if str(operator_role).strip().lower() == "admin" else "user"
        try:
            with self._connect() as connection:
                is_override = 0
                overridden_op_id = ""
                prev_decision = ""
                if peer_type and peer_id and message_id:
                    last_action = connection.execute(
                        """
                        SELECT action_id, new_decision, operator_id, operator_role
                        FROM index_actions
                        WHERE peer_type=? AND peer_id=? AND message_id=? AND label_id=?
                        ORDER BY action_id DESC
                        LIMIT 1
                        """,
                        (peer_type, peer_id, message_id, label_id),
                    ).fetchone()
                    if last_action:
                        prev_decision = str(last_action["new_decision"])
                        prev_role = str(last_action["operator_role"])
                        prev_op_id = str(last_action["operator_id"])
                        if role == "admin" and prev_decision != decision and (prev_role == "user" or prev_op_id != operator_id):
                            is_override = 1
                            overridden_op_id = prev_op_id

                # 1. Insert into index_feedback for backwards-compatibility & training
                cursor = connection.execute(
                    """
                    INSERT INTO index_feedback (
                        site_key,source_key,label_id,label_name,decision,created_at
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        scoped_site_key,
                        clean_source_key,
                        label_id,
                        label_name,
                        decision,
                        now,
                    ),
                )
                feedback_id = int(cursor.lastrowid)

                # 2. Insert into index_actions for audit & staff performance
                if peer_type and peer_id and message_id:
                    connection.execute(
                        """
                        INSERT INTO index_actions (
                            site_key, peer_type, peer_id, message_id, label_id, label_name,
                            previous_decision, new_decision, operator_id, operator_name,
                            operator_role, is_manager_override, overridden_operator_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            scoped_site_key,
                            peer_type,
                            peer_id,
                            message_id,
                            label_id,
                            label_name,
                            prev_decision,
                            decision,
                            operator_id,
                            operator_name,
                            role,
                            is_override,
                            overridden_op_id,
                            now,
                        ),
                    )

                    # 3. Live-update or insert into index_results so the change reflects immediately
                    existing = connection.execute(
                        """
                        SELECT predictions_json, model_version, text_hash, operator_id, operator_name
                        FROM index_results
                        WHERE peer_type=? AND peer_id=? AND message_id=?
                        ORDER BY (CASE WHEN site_key=? THEN 0 ELSE 1 END) ASC
                        LIMIT 1
                        """,
                        (peer_type, peer_id, message_id, scoped_site_key),
                    ).fetchone()
                    preds: list[dict[str, Any]] = []
                    model_ver = "manual_override"
                    txt_hash = "manual"
                    review_status = "approved" if role == "admin" else ("overridden" if is_override else "pending")
                    if existing:
                        try:
                            preds = list(json.loads(str(existing["predictions_json"])))
                        except (json.JSONDecodeError, TypeError):
                            preds = []
                        model_ver = str(existing["model_version"] or "manual_override")
                        txt_hash = str(existing["text_hash"] or "manual")

                    # Filter out this label
                    preds = [p for p in preds if int(p.get("label_id", -1)) != label_id]
                    if decision == "accept":
                        preds.append({
                            "label_id": label_id,
                            "label_name": label_name,
                            "score": 1.0,
                            "evidence": [f"توسط: {operator_name}"] if operator_name else ["دستی"],
                            "manual": True,
                            "operator_id": operator_id,
                            "operator_name": operator_name,
                            "operator_role": role,
                            "review_status": review_status,
                            "updated_at": now,
                        })

                    preds_json = json.dumps(preds, ensure_ascii=False, separators=(",", ":"))
                    scope_prefix = f"{self.scope.scope_key}:content-site:%"
                    updated_cnt = connection.execute(
                        """
                        UPDATE index_results SET
                            predictions_json = ?,
                            indexed_at = ?,
                            operator_id = ?,
                            operator_name = ?,
                            operator_role = ?,
                            review_status = ?
                        WHERE site_key LIKE ? AND peer_type = ? AND peer_id = ? AND message_id = ?
                        """,
                        (
                            preds_json,
                            now,
                            operator_id,
                            operator_name,
                            role,
                            review_status,
                            scope_prefix,
                            peer_type,
                            peer_id,
                            message_id,
                        ),
                    ).rowcount
                    if updated_cnt == 0:
                        connection.execute(
                            """
                            INSERT INTO index_results (
                                site_key, peer_type, peer_id, message_id, text_hash,
                                model_version, predictions_json, indexed_at,
                                operator_id, operator_name, operator_role, review_status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(site_key, peer_type, peer_id, message_id) DO UPDATE SET
                                predictions_json = excluded.predictions_json,
                                indexed_at = excluded.indexed_at,
                                operator_id = excluded.operator_id,
                                operator_name = excluded.operator_name,
                                operator_role = excluded.operator_role,
                                review_status = excluded.review_status
                            """,
                            (
                                scoped_site_key,
                                peer_type,
                                peer_id,
                                message_id,
                                txt_hash,
                                model_ver,
                                preds_json,
                                now,
                                operator_id,
                                operator_name,
                                role,
                                review_status,
                            ),
                        )
                return feedback_id
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
                local_site_key = self._site_key("local")
                if scoped_site_key == local_site_key:
                    rows = connection.execute(
                        """
                        SELECT id, name, aliases_json, kind, wordpress_category_id, created_at, updated_at
                        FROM custom_indexes
                        WHERE site_key = ?
                        ORDER BY id ASC
                        """,
                        (scoped_site_key,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT id, name, aliases_json, kind, wordpress_category_id, created_at, updated_at
                        FROM custom_indexes
                        WHERE site_key = ? OR site_key = ?
                        ORDER BY id ASC
                        """,
                        (scoped_site_key, local_site_key),
                    ).fetchall()
                results: list[dict[str, Any]] = []
                seen_ids: set[str] = set()
                for row in rows:
                    raw_id = row["id"]
                    str_id = str(raw_id)
                    if str_id in seen_ids:
                        continue
                    seen_ids.add(str_id)
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

    def save_custom_indexes_batch(
        self,
        *,
        site_key: str,
        items: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        if not items:
            return []
        now = _now()
        scoped_site_key = self._site_key(site_key)
        saved: list[dict[str, Any]] = []
        try:
            with self._connect() as connection:
                for item in items:
                    raw_id = item.get("id")
                    if raw_id is None or str(raw_id).strip() == "":
                        continue
                    str_id = str(raw_id).strip()
                    name = str(item.get("name") or "").strip()
                    if not name:
                        continue
                    raw_aliases = item.get("aliases", ())
                    if not isinstance(raw_aliases, (list, tuple)):
                        aliases = []
                    else:
                        aliases = [str(a).strip() for a in raw_aliases if str(a).strip()]
                    aliases_json = json.dumps(aliases, ensure_ascii=False, separators=(",", ":"))
                    kind = str(item.get("kind") or "custom").strip()
                    wp_cat_id = item.get("wordpress_category_id")
                    wp_id: int | None = None
                    if wp_cat_id is not None and str(wp_cat_id).strip() != "":
                        try:
                            wp_id = int(wp_cat_id)
                        except (ValueError, TypeError):
                            wp_id = None
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
                            name,
                            aliases_json,
                            kind,
                            wp_id,
                            now,
                            now,
                        ),
                    )
                    try:
                        res_id: int | str = int(str_id) if str_id.lstrip("-").isdigit() else str_id
                    except (ValueError, TypeError):
                        res_id = str_id
                    saved.append({
                        "id": res_id,
                        "name": name,
                        "aliases": aliases,
                        "kind": kind,
                        "wordpress_category_id": wp_id,
                        "created_at": now,
                        "updated_at": now,
                    })
            return saved
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Batch custom indexes could not be saved.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def list_historical_labels(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT labels_json
                    FROM index_runs
                    ORDER BY started_at DESC
                    """
                ).fetchall()
                seen_names: set[str] = set()
                items: list[dict[str, Any]] = []
                for row in rows:
                    raw = row["labels_json"]
                    try:
                        labels = json.loads(str(raw)) if raw else []
                    except (json.JSONDecodeError, TypeError):
                        continue
                    for label in labels:
                        if not isinstance(label, Mapping):
                            continue
                        name = str(label.get("name") or "").strip()
                        if not name or name.lower() in seen_names:
                            continue
                        seen_names.add(name.lower())
                        aliases = [str(a).strip() for a in label.get("aliases", ()) if str(a).strip()]
                        items.append({
                            "name": name,
                            "aliases": aliases,
                            "kind": "custom",
                        })
                return items
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Historical labels could not be retrieved.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

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
            connection.execute("PRAGMA user_version = 4")
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise

    def _upgrade_v5_schema(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_cols = {
                row[1] for row in connection.execute("PRAGMA table_info(index_results)")
            }
            if "operator_id" not in existing_cols:
                connection.execute("ALTER TABLE index_results ADD COLUMN operator_id TEXT NOT NULL DEFAULT ''")
            if "operator_name" not in existing_cols:
                connection.execute("ALTER TABLE index_results ADD COLUMN operator_name TEXT NOT NULL DEFAULT ''")
            if "operator_role" not in existing_cols:
                connection.execute("ALTER TABLE index_results ADD COLUMN operator_role TEXT NOT NULL DEFAULT ''")
            if "review_status" not in existing_cols:
                connection.execute("ALTER TABLE index_results ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'")

            staging_cols = {
                row[1] for row in connection.execute("PRAGMA table_info(index_staging_results)")
            }
            if "operator_id" not in staging_cols:
                connection.execute("ALTER TABLE index_staging_results ADD COLUMN operator_id TEXT NOT NULL DEFAULT ''")
            if "operator_name" not in staging_cols:
                connection.execute("ALTER TABLE index_staging_results ADD COLUMN operator_name TEXT NOT NULL DEFAULT ''")
            if "operator_role" not in staging_cols:
                connection.execute("ALTER TABLE index_staging_results ADD COLUMN operator_role TEXT NOT NULL DEFAULT ''")
            if "review_status" not in staging_cols:
                connection.execute("ALTER TABLE index_staging_results ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS index_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_key TEXT NOT NULL,
                    peer_type TEXT NOT NULL,
                    peer_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    label_id INTEGER NOT NULL,
                    label_name TEXT NOT NULL,
                    previous_decision TEXT NOT NULL DEFAULT '',
                    new_decision TEXT NOT NULL,
                    operator_id TEXT NOT NULL DEFAULT '',
                    operator_name TEXT NOT NULL DEFAULT '',
                    operator_role TEXT NOT NULL DEFAULT 'user',
                    is_manager_override INTEGER NOT NULL DEFAULT 0,
                    overridden_operator_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_actions_op
                    ON index_actions(operator_id, created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_actions_overridden
                    ON index_actions(overridden_operator_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_actions_msg
                    ON index_actions(peer_type, peer_id, message_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS staff_tasks (
                    task_id TEXT PRIMARY KEY,
                    peer_type TEXT NOT NULL DEFAULT '',
                    peer_id INTEGER NOT NULL DEFAULT 0,
                    message_id INTEGER NOT NULL DEFAULT 0,
                    event_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    defect_type TEXT NOT NULL DEFAULT 'general',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'open',
                    assigned_to_user_id TEXT NOT NULL DEFAULT '',
                    assigned_to_name TEXT NOT NULL DEFAULT '',
                    created_by_user_id TEXT NOT NULL DEFAULT '',
                    created_by_name TEXT NOT NULL DEFAULT '',
                    due_date TEXT,
                    resolution_notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    closed_at TEXT,
                    macro_category TEXT NOT NULL DEFAULT 'workbook_approved',
                    program_codes_json TEXT NOT NULL DEFAULT '[]',
                    custom_topic TEXT NOT NULL DEFAULT '',
                    task_kind TEXT NOT NULL DEFAULT 'general',
                    unit_scope TEXT NOT NULL DEFAULT 'provincial_hq',
                    unit_name TEXT NOT NULL DEFAULT '',
                    checklist_json TEXT NOT NULL DEFAULT '[]',
                    requires_manager_approval INTEGER NOT NULL DEFAULT 1,
                    reassigned_from_user_id TEXT NOT NULL DEFAULT '',
                    reassigned_from_name TEXT NOT NULL DEFAULT '',
                    is_escalated INTEGER NOT NULL DEFAULT 0,
                    escalated_at TEXT,
                    escalation_notes TEXT NOT NULL DEFAULT ''
                )
                """
            )
            task_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(staff_tasks)").fetchall()
            }
            if "macro_category" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN macro_category TEXT NOT NULL DEFAULT 'workbook_approved'")
            if "program_codes_json" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN program_codes_json TEXT NOT NULL DEFAULT '[]'")
            if "custom_topic" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN custom_topic TEXT NOT NULL DEFAULT ''")
            if "task_kind" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN task_kind TEXT NOT NULL DEFAULT 'general'")
            if "unit_scope" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN unit_scope TEXT NOT NULL DEFAULT 'provincial_hq'")
            if "unit_name" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN unit_name TEXT NOT NULL DEFAULT ''")
            if "checklist_json" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN checklist_json TEXT NOT NULL DEFAULT '[]'")
            if "requires_manager_approval" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN requires_manager_approval INTEGER NOT NULL DEFAULT 1")
            if "reassigned_from_user_id" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN reassigned_from_user_id TEXT NOT NULL DEFAULT ''")
            if "reassigned_from_name" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN reassigned_from_name TEXT NOT NULL DEFAULT ''")
            if "is_escalated" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN is_escalated INTEGER NOT NULL DEFAULT 0")
            if "escalated_at" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN escalated_at TEXT")
            if "escalation_notes" not in task_columns:
                connection.execute("ALTER TABLE staff_tasks ADD COLUMN escalation_notes TEXT NOT NULL DEFAULT ''")

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_staff_tasks_assigned
                    ON staff_tasks(assigned_to_user_id, status)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_staff_tasks_status
                    ON staff_tasks(status)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_staff_tasks_macro
                    ON staff_tasks(macro_category)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_staff_tasks_reassigned
                    ON staff_tasks(reassigned_from_user_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS content_index_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
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

    def get_setting(self, setting_key: str, default: str = "") -> str:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT setting_value FROM content_index_settings WHERE setting_key = ?",
                    (setting_key,),
                ).fetchone()
                if row is not None:
                    return str(row["setting_value"])
                return default
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index setting could not be retrieved.",
                safe_context={"setting_key": setting_key, "error_type": type(exc).__name__},
            ) from exc

    def set_setting(self, setting_key: str, setting_value: str) -> None:
        now = _now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO content_index_settings (setting_key, setting_value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(setting_key) DO UPDATE SET
                        setting_value = excluded.setting_value,
                        updated_at = excluded.updated_at
                    """,
                    (setting_key, str(setting_value), now),
                )
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Content-index setting could not be updated.",
                safe_context={"setting_key": setting_key, "error_type": type(exc).__name__},
            ) from exc

    def list_actions(
        self,
        *,
        operator_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if operator_id:
            clauses.append("operator_id = ?")
            params.append(operator_id)
        if from_date:
            clauses.append("created_at >= ?")
            params.append(from_date)
        if to_date:
            clauses.append("created_at <= ?")
            params.append(to_date)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT action_id, site_key, peer_type, peer_id, message_id, label_id, label_name,
                   previous_decision, new_decision, operator_id, operator_name, operator_role,
                   is_manager_override, created_at
            FROM index_actions
            {where_clause}
            ORDER BY action_id DESC
            LIMIT ?
        """
        params.append(max(1, min(limit, 5000)))
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, tuple(params)).fetchall()
                return [
                    {
                        "action_id": int(r["action_id"]),
                        "site_key": str(r["site_key"]),
                        "peer_type": str(r["peer_type"]),
                        "peer_id": int(r["peer_id"]),
                        "message_id": int(r["message_id"]),
                        "label_id": int(r["label_id"]),
                        "label_name": str(r["label_name"]),
                        "previous_decision": str(r["previous_decision"]),
                        "new_decision": str(r["new_decision"]),
                        "operator_id": str(r["operator_id"]),
                        "operator_name": str(r["operator_name"]),
                        "operator_role": str(r["operator_role"]),
                        "is_manager_override": bool(r["is_manager_override"]),
                        "created_at": str(r["created_at"]),
                    }
                    for r in rows
                ]
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Index actions could not be retrieved.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def get_staff_performance(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = ["operator_id != ''"]
        params: list[Any] = []
        if from_date:
            clauses.append("created_at >= ?")
            params.append(from_date)
        if to_date:
            clauses.append("created_at <= ?")
            params.append(to_date)
        where_clause = f"WHERE {' AND '.join(clauses)}"
        sql = f"""
            SELECT operator_id, operator_name, operator_role,
                   COUNT(*) as total_actions,
                   SUM(CASE WHEN new_decision = 'accept' THEN 1 ELSE 0 END) as accept_count,
                   SUM(CASE WHEN new_decision = 'reject' THEN 1 ELSE 0 END) as reject_count,
                   SUM(CASE WHEN is_manager_override = 1 THEN 1 ELSE 0 END) as override_count
            FROM index_actions
            {where_clause}
            GROUP BY operator_id, operator_name, operator_role
            ORDER BY total_actions DESC
        """
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, tuple(params)).fetchall()

                # Get overrides suffered per operator (where manager overruled this operator)
                override_clauses: list[str] = ["overridden_operator_id != ''"]
                override_params: list[Any] = []
                if from_date:
                    override_clauses.append("created_at >= ?")
                    override_params.append(from_date)
                if to_date:
                    override_clauses.append("created_at <= ?")
                    override_params.append(to_date)
                overrides_suffered_rows = connection.execute(
                    f"""
                    SELECT overridden_operator_id, COUNT(*) as cnt
                    FROM index_actions
                    WHERE {' AND '.join(override_clauses)}
                    GROUP BY overridden_operator_id
                    """,
                    tuple(override_params),
                ).fetchall()
                overrides_suffered = {str(r["overridden_operator_id"]): int(r["cnt"] or 0) for r in overrides_suffered_rows}

                # Also get task stats for these operators
                task_stats: dict[str, dict[str, int]] = {}
                task_clauses: list[str] = ["assigned_to_user_id != ''"]
                task_params: list[Any] = []
                if from_date:
                    task_clauses.append("created_at >= ?")
                    task_params.append(from_date)
                if to_date:
                    task_clauses.append("created_at <= ?")
                    task_params.append(to_date)

                now_iso = _now()
                task_rows = connection.execute(
                    f"""
                    SELECT assigned_to_user_id,
                           COUNT(*) as total_tasks,
                           SUM(CASE WHEN status IN ('resolved', 'closed') THEN 1 ELSE 0 END) as resolved_tasks,
                           SUM(CASE WHEN status NOT IN ('resolved', 'closed') AND due_date IS NOT NULL AND due_date != '' AND due_date < ? THEN 1 ELSE 0 END) as overdue_tasks
                    FROM staff_tasks
                    WHERE {' AND '.join(task_clauses)}
                    GROUP BY assigned_to_user_id
                    """,
                    tuple([now_iso] + task_params),
                ).fetchall()
                for tr in task_rows:
                    task_stats[str(tr["assigned_to_user_id"])] = {
                        "total_tasks": int(tr["total_tasks"] or 0),
                        "resolved_tasks": int(tr["resolved_tasks"] or 0),
                        "overdue_tasks": int(tr["overdue_tasks"] or 0),
                        "revoked_tasks": 0,
                    }

                # Query revoked / reassigned tasks where this operator failed/had task revoked
                revoked_clauses: list[str] = ["reassigned_from_user_id != ''"]
                revoked_params: list[Any] = []
                if from_date:
                    revoked_clauses.append("updated_at >= ?")
                    revoked_params.append(from_date)
                if to_date:
                    revoked_clauses.append("updated_at <= ?")
                    revoked_params.append(to_date)
                revoked_rows = connection.execute(
                    f"""
                    SELECT reassigned_from_user_id, COUNT(*) as revoked_cnt
                    FROM staff_tasks
                    WHERE {' AND '.join(revoked_clauses)}
                    GROUP BY reassigned_from_user_id
                    """,
                    tuple(revoked_params),
                ).fetchall()
                for rr in revoked_rows:
                    rev_id = str(rr["reassigned_from_user_id"])
                    if rev_id not in task_stats:
                        task_stats[rev_id] = {
                            "total_tasks": 0,
                            "resolved_tasks": 0,
                            "overdue_tasks": 0,
                            "revoked_tasks": int(rr["revoked_cnt"] or 0),
                        }
                    else:
                        task_stats[rev_id]["revoked_tasks"] = int(rr["revoked_cnt"] or 0)

                summaries: list[dict[str, Any]] = []
                seen_ops: set[str] = set()
                for r in rows:
                    op_id = str(r["operator_id"])
                    seen_ops.add(op_id)
                    op_role = str(r["operator_role"] or "user")
                    total_acts = int(r["total_actions"] or 0)
                    accept_cnt = int(r["accept_count"] or 0)
                    reject_cnt = int(r["reject_count"] or 0)
                    mgr_overrides_done = int(r["override_count"] or 0)

                    # For staff: override_count is how many of their decisions were overruled by a manager
                    # For manager: override_count is how many decisions they corrected/overruled
                    if op_role == "admin":
                        override_cnt = mgr_overrides_done
                        accuracy = 100.0
                    else:
                        override_cnt = overrides_suffered.get(op_id, 0)
                        accuracy = 100.0
                        if total_acts > 0:
                            accuracy = round(max(0.0, (total_acts - override_cnt) / total_acts * 100), 1)

                    ts = task_stats.get(op_id, {"total_tasks": 0, "resolved_tasks": 0, "overdue_tasks": 0, "revoked_tasks": 0})
                    effective_total = ts["total_tasks"] + ts["revoked_tasks"]
                    if effective_total > 0:
                        base_res = (ts["resolved_tasks"] / effective_total) * 100.0
                        overdue_penalty = min(50.0, ts["overdue_tasks"] * 10.0)
                        task_res_rate = round(max(0.0, base_res - overdue_penalty), 1)
                    else:
                        task_res_rate = 100.0

                    summaries.append({
                        "operator_id": op_id,
                        "operator_name": str(r["operator_name"] or op_id),
                        "operator_role": op_role,
                        "total_actions": total_acts,
                        "accept_count": accept_cnt,
                        "reject_count": reject_cnt,
                        "override_count": override_cnt,
                        "accuracy_rate": accuracy,
                        "assigned_tasks": ts["total_tasks"],
                        "resolved_tasks": ts["resolved_tasks"],
                        "overdue_tasks": ts["overdue_tasks"],
                        "revoked_tasks": ts["revoked_tasks"],
                        "task_resolution_rate": task_res_rate,
                    })

                # Also include operators who have tasks in staff_tasks but had no index_actions
                for op_id, ts in sorted(task_stats.items()):
                    if op_id not in seen_ops:
                        effective_total = ts["total_tasks"] + ts["revoked_tasks"]
                        if effective_total > 0:
                            base_res = (ts["resolved_tasks"] / effective_total) * 100.0
                            overdue_penalty = min(50.0, ts["overdue_tasks"] * 10.0)
                            task_res_rate = round(max(0.0, base_res - overdue_penalty), 1)
                        else:
                            task_res_rate = 100.0

                        summaries.append({
                            "operator_id": op_id,
                            "operator_name": op_id,
                            "operator_role": "user",
                            "total_actions": 0,
                            "accept_count": 0,
                            "reject_count": 0,
                            "override_count": 0,
                            "accuracy_rate": 100.0,
                            "assigned_tasks": ts["total_tasks"],
                            "resolved_tasks": ts["resolved_tasks"],
                            "overdue_tasks": ts["overdue_tasks"],
                            "revoked_tasks": ts["revoked_tasks"],
                            "task_resolution_rate": task_res_rate,
                        })

                return summaries
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Staff performance statistics could not be calculated.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def create_task(
        self,
        *,
        title: str,
        description: str = "",
        defect_type: str = "general",
        priority: str = "medium",
        macro_category: str = "workbook_approved",
        program_codes: list[str] | None = None,
        custom_topic: str = "",
        task_kind: str = "general",
        unit_scope: str = "provincial_hq",
        unit_name: str = "",
        checklist: list[dict[str, Any]] | None = None,
        requires_manager_approval: bool = True,
        peer_type: str = "",
        peer_id: int = 0,
        message_id: int = 0,
        event_id: str = "",
        assigned_to_user_id: str = "",
        assigned_to_name: str = "",
        created_by_user_id: str = "",
        created_by_name: str = "",
        due_date: str | None = None,
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = _now()
        prio = priority.lower() if priority.lower() in {"low", "medium", "high", "urgent"} else "medium"
        macro_cat = "other_cultural" if macro_category == "other_cultural" else "workbook_approved"
        valid_kinds = {
            "defect_resolution",
            "event_registration",
            "field_execution",
            "media_production",
            "inquiry_followup",
            "general",
        }
        kind = task_kind.lower() if task_kind.lower() in valid_kinds else "general"
        prog_codes = [str(c).strip() for c in (program_codes or []) if str(c).strip()]
        prog_codes_json = json.dumps(prog_codes, ensure_ascii=False, separators=(",", ":"))
        chk_items = list(checklist or [])
        chk_json = json.dumps(chk_items, ensure_ascii=False, separators=(",", ":"))
        req_approval = 1 if requires_manager_approval else 0

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO staff_tasks (
                        task_id, peer_type, peer_id, message_id, event_id, title, description,
                        defect_type, priority, status, assigned_to_user_id, assigned_to_name,
                        created_by_user_id, created_by_name, due_date, resolution_notes,
                        created_at, updated_at,
                        macro_category, program_codes_json, custom_topic, task_kind,
                        unit_scope, unit_name, checklist_json, requires_manager_approval
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        peer_type,
                        peer_id,
                        message_id,
                        event_id,
                        title.strip(),
                        description.strip(),
                        defect_type.strip(),
                        prio,
                        assigned_to_user_id.strip(),
                        assigned_to_name.strip(),
                        created_by_user_id.strip(),
                        created_by_name.strip(),
                        due_date,
                        now,
                        now,
                        macro_cat,
                        prog_codes_json,
                        custom_topic.strip(),
                        kind,
                        unit_scope.strip() or "provincial_hq",
                        unit_name.strip(),
                        chk_json,
                        req_approval,
                    ),
                )
                return {
                    "task_id": task_id,
                    "title": title.strip(),
                    "description": description.strip(),
                    "defect_type": defect_type.strip(),
                    "status": "open",
                    "priority": prio,
                    "macro_category": macro_cat,
                    "program_codes": prog_codes,
                    "custom_topic": custom_topic.strip(),
                    "task_kind": kind,
                    "unit_scope": unit_scope.strip() or "provincial_hq",
                    "unit_name": unit_name.strip(),
                    "checklist": chk_items,
                    "requires_manager_approval": bool(req_approval),
                    "assigned_to_user_id": assigned_to_user_id.strip(),
                    "assigned_to_name": assigned_to_name.strip(),
                    "created_by_user_id": created_by_user_id.strip(),
                    "created_by_name": created_by_name.strip(),
                    "due_date": due_date,
                    "created_at": now,
                }
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Staff task could not be created.",
                safe_context={"error_type": type(exc).__name__, "title": title},
            ) from exc

    def list_tasks(
        self,
        *,
        assigned_to_user_id: str | None = None,
        status: str | None = None,
        macro_category: str | None = None,
        task_kind: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if assigned_to_user_id:
            clauses.append("assigned_to_user_id = ?")
            params.append(assigned_to_user_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if macro_category:
            clauses.append("macro_category = ?")
            params.append(macro_category)
        if task_kind:
            clauses.append("task_kind = ?")
            params.append(task_kind)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT task_id, peer_type, peer_id, message_id, event_id, title, description,
                   defect_type, priority, status, assigned_to_user_id, assigned_to_name,
                   created_by_user_id, created_by_name, due_date, resolution_notes,
                   created_at, updated_at, resolved_at, closed_at,
                   macro_category, program_codes_json, custom_topic, task_kind,
                   unit_scope, unit_name, checklist_json, requires_manager_approval,
                   reassigned_from_user_id, reassigned_from_name, is_escalated, escalated_at, escalation_notes
            FROM staff_tasks
            {where_clause}
            ORDER BY (CASE status WHEN 'open' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'resolved' THEN 3 ELSE 4 END) ASC, created_at DESC
            LIMIT ?
        """
        params.append(max(1, min(limit, 1000)))
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, tuple(params)).fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    try:
                        item["program_codes"] = json.loads(item.get("program_codes_json") or "[]")
                    except (json.JSONDecodeError, TypeError):
                        item["program_codes"] = []
                    try:
                        item["checklist"] = json.loads(item.get("checklist_json") or "[]")
                    except (json.JSONDecodeError, TypeError):
                        item["checklist"] = []
                    item["requires_manager_approval"] = bool(item.get("requires_manager_approval", 1))
                    item["is_escalated"] = bool(item.get("is_escalated", 0))
                    results.append(item)
                return results
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Staff tasks could not be retrieved.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc

    def reassign_task(
        self,
        *,
        task_id: str,
        new_assigned_to_user_id: str,
        new_assigned_to_name: str,
        reassigned_by_id: str = "",
        reassigned_by_name: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        now = _now()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT assigned_to_user_id, assigned_to_name, resolution_notes, status FROM staff_tasks WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
                if not row:
                    raise LocalContentIndexStoreError(
                        "Task not found for reassignment.",
                        safe_context={"task_id": task_id},
                    )
                prev_assigned_id = str(row["assigned_to_user_id"] or "").strip()
                prev_assigned_name = str(row["assigned_to_name"] or "").strip()
                prev_notes = row["resolution_notes"] or ""
                reassign_note = f"[ارجاع مجدد از {prev_assigned_name or 'نامشخص'} به {new_assigned_to_name} توسط {reassigned_by_name or 'مدیر'}. علت: {reason or 'عدم اقدام در مهلت مقرر'}]"
                new_notes = f"{prev_notes}\n{reassign_note}".strip() if prev_notes else reassign_note

                cursor = connection.execute(
                    """
                    UPDATE staff_tasks
                    SET assigned_to_user_id = ?,
                        assigned_to_name = ?,
                        reassigned_from_user_id = ?,
                        reassigned_from_name = ?,
                        status = 'open',
                        resolution_notes = ?,
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (new_assigned_to_user_id.strip(), new_assigned_to_name.strip(), prev_assigned_id, prev_assigned_name, new_notes, now, task_id),
                )
                return {
                    "task_id": task_id,
                    "assigned_to_user_id": new_assigned_to_user_id.strip(),
                    "assigned_to_name": new_assigned_to_name.strip(),
                    "reassigned_from_user_id": prev_assigned_id,
                    "reassigned_from_name": prev_assigned_name,
                    "status": "open",
                    "resolution_notes": new_notes,
                    "updated_at": now,
                }
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Task could not be reassigned.",
                safe_context={"task_id": task_id, "error_type": type(exc).__name__},
            ) from exc

    def escalate_task(
        self,
        *,
        task_id: str,
        escalated_by_id: str = "",
        escalated_by_name: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        now = _now()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT priority, resolution_notes, status FROM staff_tasks WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
                if not row:
                    raise LocalContentIndexStoreError(
                        "Task not found for escalation.",
                        safe_context={"task_id": task_id},
                    )
                prev_prio = str(row["priority"] or "medium")
                new_prio = "urgent" if prev_prio in ("high", "urgent") else "high"
                prev_notes = row["resolution_notes"] or ""
                esc_note = f"[اخطار مدیریتی و افزایش اولویت به {new_prio} توسط {escalated_by_name or 'مدیر'}. علت: {notes or 'تاخیر در پیگیری و نیاز به اقدام فوری'}]"
                new_notes = f"{prev_notes}\n{esc_note}".strip() if prev_notes else esc_note

                connection.execute(
                    """
                    UPDATE staff_tasks
                    SET is_escalated = 1,
                        escalated_at = ?,
                        escalation_notes = ?,
                        priority = ?,
                        resolution_notes = ?,
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (now, notes.strip(), new_prio, new_notes, now, task_id),
                )
                return {
                    "task_id": task_id,
                    "is_escalated": True,
                    "escalated_at": now,
                    "escalation_notes": notes.strip(),
                    "priority": new_prio,
                    "resolution_notes": new_notes,
                    "updated_at": now,
                }
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Task could not be escalated.",
                safe_context={"task_id": task_id, "error_type": type(exc).__name__},
            ) from exc

    def update_task_checklist(
        self,
        *,
        task_id: str,
        checklist: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = _now()
        chk_json = json.dumps(checklist, ensure_ascii=False, separators=(",", ":"))
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE staff_tasks
                    SET checklist_json = ?,
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (chk_json, now, task_id),
                )
                if cursor.rowcount == 0:
                    raise LocalContentIndexStoreError(
                        "Task not found for checklist update.",
                        safe_context={"task_id": task_id},
                    )
                return {"task_id": task_id, "checklist": checklist, "updated_at": now}
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Task checklist could not be updated.",
                safe_context={"task_id": task_id, "error_type": type(exc).__name__},
            ) from exc

    def resolve_task(
        self,
        *,
        task_id: str,
        resolution_notes: str,
        user_id: str = "",
        user_name: str = "",
    ) -> dict[str, Any]:
        now = _now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE staff_tasks
                    SET status = 'resolved',
                        resolution_notes = ?,
                        resolved_at = ?,
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (resolution_notes.strip(), now, now, task_id),
                )
                if cursor.rowcount == 0:
                    raise LocalContentIndexStoreError(
                        "Task not found for resolution.",
                        safe_context={"task_id": task_id},
                    )
                return {"task_id": task_id, "status": "resolved", "resolved_at": now}
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Task could not be resolved.",
                safe_context={"task_id": task_id, "error_type": type(exc).__name__},
            ) from exc

    def close_task(
        self,
        *,
        task_id: str,
        manager_id: str = "",
        manager_name: str = "",
        reopen: bool = False,
    ) -> dict[str, Any]:
        now = _now()
        new_status = "in_progress" if reopen else "closed"
        closed_at = None if reopen else now
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE staff_tasks
                    SET status = ?,
                        closed_at = ?,
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (new_status, closed_at, now, task_id),
                )
                if cursor.rowcount == 0:
                    raise LocalContentIndexStoreError(
                        "Task not found for closure.",
                        safe_context={"task_id": task_id},
                    )
                return {"task_id": task_id, "status": new_status, "closed_at": closed_at}
        except sqlite3.Error as exc:
            raise LocalContentIndexStoreError(
                "Task could not be updated.",
                safe_context={"task_id": task_id, "error_type": type(exc).__name__},
            ) from exc
