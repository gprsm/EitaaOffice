from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from uuid import UUID

from runtime_state import load_version, project_root

SECRET_KEYS = re.compile(r"(password|token|secret|authorization|cookie|session|imei)", re.IGNORECASE)
PHONE = re.compile(
    r"(?<!\d)(?:\+[1-9]\d{7,14}|00[1-9]\d{7,14}|09\d{9})(?!\d)"
)
EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
)
IPV4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
WINDOWS_USER_PATH = re.compile(
    r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"']+"
)
LONG_SECRET = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-=]{24,}(?![A-Za-z0-9])")
CANONICAL_UUID = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![0-9a-f])",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a safe Eitaa Bridge diagnostics ZIP.")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--messenger-account-id",
        help="Include only safe diagnostics for this canonical MessengerAccount.",
    )
    return parser.parse_args()


def canonical_account_id(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("messenger account ID must be a canonical UUID v4") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("messenger account ID must be a canonical UUID v4")
    return value


def file_fingerprint(path: Path) -> dict[str, object]:
    if path.is_symlink():
        return {"present": False, "symlink_rejected": True}
    if not path.is_file():
        return {"present": False}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    stat = path.stat()
    return {"present": True, "size": stat.st_size, "sha256_prefix": digest[:16], "modified": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")}


def redact_text(value: str) -> str:
    preserved: list[str] = []

    def keep_uuid(match: re.Match[str]) -> str:
        preserved.append(match.group(0))
        return f"<safe-uuid-{len(preserved) - 1}>"

    value = CANONICAL_UUID.sub(keep_uuid, value)
    value = WINDOWS_USER_PATH.sub(
        lambda _match: r"C:\\Users\\<redacted-user>",
        value,
    )
    value = PHONE.sub("<redacted-phone>", value)
    value = EMAIL.sub("<redacted-email>", value)

    def redact_ip(match: re.Match[str]) -> str:
        selected = match.group(0)
        try:
            address = ipaddress.ip_address(selected)
        except ValueError:
            return selected
        return selected if address.is_loopback else "<redacted-ip>"

    value = IPV4.sub(redact_ip, value)
    value = LONG_SECRET.sub("<redacted-secret>", value)
    for index, selected in enumerate(preserved):
        value = value.replace(f"<safe-uuid-{index}>", selected)
    return value


def redact_json(value: object, key: str = "") -> object:
    if SECRET_KEYS.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): redact_json(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_json(item, key) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def safe_bridge_config(root: Path) -> object:
    path = root / "bridge.json"
    if path.is_symlink():
        return {"present": False, "symlink_rejected": True}
    if not path.is_file():
        return {"present": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"present": True, "valid_json": False, "error_type": type(exc).__name__}
    return {"present": True, "valid_json": True, "config": redact_json(payload)}


def tail(path: Path, limit: int = 250_000) -> str:
    if path.is_symlink() or not path.is_file():
        return ""
    data = path.read_bytes()
    if len(data) > limit:
        data = data[-limit:]
        first_complete_record = data.find(b"\n")
        data = data[first_complete_record + 1 :] if first_complete_record >= 0 else b""
    return redact_text(data.decode("utf-8", errors="replace"))


def safe_jsonl_tail(path: Path, limit: int = 250_000) -> str:
    """Return valid, redacted JSONL and replace malformed source lines by one marker."""

    selected = tail(path, limit)
    records: list[str] = []
    omitted = 0
    for line in selected.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            omitted += 1
            continue
        records.append(json.dumps(redact_json(payload), ensure_ascii=False, sort_keys=True))
    if omitted:
        records.append(
            json.dumps(
                {
                    "event": "support_bundle_source_record_omitted",
                    "level": "warning",
                    "fields": {
                        "reason_code": "invalid_jsonl",
                        "omitted_count": omitted,
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return "".join(record + "\n" for record in records)


def run_doctor(root: Path) -> str:
    candidates = [root / ".venv" / "Scripts" / "python.exe", Path(sys.executable)]
    python = next((path for path in candidates if path.is_file()), None)
    if python is None:
        return "Python runtime unavailable."
    command = [str(python), str(root / "scripts" / "doctor.py"), "--config", "bridge.json"]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=90, check=False)
    combined = (result.stdout + "\n" + result.stderr).strip()
    for spelling in {str(root), root.as_posix()}:
        combined = combined.replace(spelling, "<installation-root>")
    return redact_text(combined)


def safe_coordinator_account(root: Path, account_id: str) -> dict[str, object]:
    database = root / "data" / "coordinator" / "coordinator.sqlite3"
    if database.is_symlink():
        return {"present": False, "symlink_rejected": True}
    if not database.is_file():
        return {"present": False}
    try:
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro",
            uri=True,
            timeout=10.0,
        )
        connection.row_factory = sqlite3.Row
        account = connection.execute(
            """
            SELECT
                ma.id AS messenger_account_id,ma.phone_account_id,ma.provider,ma.label,
                ma.lifecycle_state,ma.desired_worker_state,pa.display_hint AS phone_hint,
                sm.auth_state,sm.session_generation,sm.storage_revision,
                sm.last_validated_at,sm.last_auth_transition_at,sm.safe_reason_code
            FROM messenger_accounts ma
            JOIN phone_accounts pa ON pa.id=ma.phone_account_id
            JOIN messenger_session_metadata sm ON sm.messenger_account_id=ma.id
            WHERE ma.id=?
            """,
            (account_id,),
        ).fetchone()
        workers = connection.execute(
            """
            SELECT id,generation,runtime_state,process_id,started_at,last_heartbeat_at,
                   stopped_at,exit_code,safe_reason_code
            FROM worker_instances WHERE messenger_account_id=?
            ORDER BY generation DESC LIMIT 20
            """,
            (account_id,),
        ).fetchall()
        audit = connection.execute(
            """
            SELECT id,at,actor_type,actor_global_role,action,target_type,target_id,
                   provider,result,reason_code,request_id,safe_metadata_json,
                   previous_event_hash,event_hash
            FROM audit_events WHERE messenger_account_id=?
            ORDER BY rowid DESC LIMIT 200
            """,
            (account_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        return {"present": True, "readable": False, "error_type": type(exc).__name__}
    finally:
        if "connection" in locals():
            connection.close()
    if account is None:
        return {"present": True, "account_found": False}
    safe_audit: list[dict[str, object]] = []
    for row in audit:
        item = dict(row)
        try:
            item["safe_metadata"] = redact_json(
                json.loads(str(item.pop("safe_metadata_json") or "{}"))
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            item["safe_metadata"] = {"readable": False}
        safe_audit.append(item)
    return {
        "present": True,
        "account_found": True,
        "account": redact_json(dict(account)),
        "workers": redact_json([dict(row) for row in workers]),
        "audit": redact_json(safe_audit),
    }


def main() -> int:
    args = parse_args()
    root = project_root()
    try:
        account_id = canonical_account_id(args.messenger_account_id)
    except ValueError as exc:
        print(f"diagnostics: {exc}", file=sys.stderr)
        return 2
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = (args.output or root / "diagnostics" / "bundles" / f"eitaa-bridge-diagnostics-{timestamp}.zip").expanduser().resolve()
    if output.suffix.lower() != ".zip":
        output = output / f"eitaa-bridge-diagnostics-{timestamp}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)

    inventory = {
        "created_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "product_version": load_version(root),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "installation_root": {"path_included": False},
        "files": {
            "bridge.json": file_fingerprint(root / "bridge.json"),
            "protected_environment": {"present": (root / ".env").is_file()},
            "protected_session": {
                "present": (root / ".eitaa_session.json").is_file()
            },
            "database": file_fingerprint(root / "data" / "eitaa_messages.sqlite3"),
            "composition_state": file_fingerprint(root / "data" / "bridge_compositions.json"),
        },
        "environment": {
            "EITAA_BRIDGE_CONFIG": bool(os.environ.get("EITAA_BRIDGE_CONFIG")),
            "EITAA_UI_DEV_URL": bool(os.environ.get("EITAA_UI_DEV_URL")),
        },
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    included: list[dict[str, object]] = []
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        def add_text(name: str, content: str) -> None:
            encoded = content.encode("utf-8")
            archive.writestr(name, encoded)
            included.append(
                {
                    "name": name,
                    "size": len(encoded),
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                }
            )

        inventory["messenger_account_id"] = account_id
        add_text("system.json", json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
        add_text("bridge.redacted.json", json.dumps(safe_bridge_config(root), ensure_ascii=False, indent=2) + "\n")
        add_text("doctor.txt", run_doctor(root) + "\n")
        for relative in ["runtime/logs/api.log", "runtime/logs/desktop.log", "runtime/logs/application.jsonl"]:
            path = root / relative
            candidates = [path, *sorted(path.parent.glob(path.name + ".*"))]
            for candidate in candidates:
                content = (
                    safe_jsonl_tail(candidate)
                    if candidate.name.startswith("application.jsonl")
                    else tail(candidate)
                )
                if content:
                    add_text(f"logs/{candidate.name}", content)
        for base_relative in ["diagnostics/bridge", "diagnostics/core"]:
            base = root / base_relative
            if base.is_dir():
                for path in sorted(base.rglob("*.jsonl"))[-20:]:
                    if path.is_symlink():
                        continue
                    relative_name = path.relative_to(base).as_posix()
                    add_text(
                        f"safe-diagnostics/{base.name}/{relative_name}",
                        safe_jsonl_tail(path, 100_000),
                    )
        if account_id is not None:
            account_runtime = root / "runtime" / "accounts" / account_id
            worker_log = account_runtime / "logs" / "worker.jsonl"
            for candidate in [worker_log, *sorted(worker_log.parent.glob(worker_log.name + ".*"))]:
                content = safe_jsonl_tail(candidate)
                if content:
                    add_text(f"account/logs/{candidate.name}", content)
            diagnostics = account_runtime / "diagnostics"
            if diagnostics.is_dir():
                for path in sorted(diagnostics.rglob("*.jsonl"))[-40:]:
                    if path.is_symlink():
                        continue
                    add_text(
                        "account/safe-diagnostics/" + path.relative_to(diagnostics).as_posix(),
                        safe_jsonl_tail(path, 100_000),
                    )
            add_text(
                "account/coordinator.redacted.json",
                json.dumps(
                    safe_coordinator_account(root, account_id),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
            )
        add_text(
            "README.txt",
            "This bundle intentionally excludes .env, Session contents, SQLite contents, media, and WordPress credentials.\n"
            "It includes redacted runtime logs, safe diagnostics, and safe coordinator metadata only.\n"
            "File hashes are support fingerprints and are not authentication secrets.\n",
        )
        add_text(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "messenger_account_id": account_id,
                    "entries": included,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    temporary.replace(output)
    print(f"diagnostics bundle created: {output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
