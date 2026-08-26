"""Print only safe recent authentication failure metadata from the live coordinator."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "data" / "coordinator" / "coordinator.sqlite3"
    uri = f"{path.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
        connection.row_factory = sqlite3.Row
        session = connection.execute(
            """
            SELECT auth_state,session_generation,storage_revision,safe_reason_code,
                   last_auth_transition_at
            FROM messenger_session_metadata ORDER BY created_at LIMIT 1
            """
        ).fetchone()
        events = connection.execute(
            """
            SELECT at,action,result,reason_code,request_id,safe_metadata_json
            FROM audit_events
            WHERE action LIKE 'eitaa.auth.%'
            ORDER BY rowid DESC LIMIT 12
            """
        ).fetchall()
    result = {
        "session": dict(session) if session else None,
        "events": [
            {
                "at": row["at"],
                "action": row["action"],
                "result": row["result"],
                "reason_code": row["reason_code"],
                "request_id": row["request_id"],
                "safe_metadata": json.loads(row["safe_metadata_json"] or "{}"),
            }
            for row in events
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
