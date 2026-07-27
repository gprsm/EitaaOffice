from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from runtime_state import load_version, project_root

SECRET_KEYS = re.compile(r"(password|token|secret|authorization|cookie|session|imei)", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?98|0)?9\d{9}(?!\d)")
LONG_SECRET = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-=]{24,}(?![A-Za-z0-9])")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a safe Eitaa Bridge diagnostics ZIP.")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def file_fingerprint(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"present": False}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    stat = path.stat()
    return {"present": True, "size": stat.st_size, "sha256_prefix": digest[:16], "modified": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")}


def redact_text(value: str) -> str:
    value = PHONE.sub("<redacted-phone>", value)
    value = LONG_SECRET.sub("<redacted-secret>", value)
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
    if not path.is_file():
        return {"present": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"present": True, "valid_json": False, "error_type": type(exc).__name__}
    return {"present": True, "valid_json": True, "config": redact_json(payload)}


def tail(path: Path, limit: int = 250_000) -> str:
    if not path.is_file():
        return ""
    data = path.read_bytes()
    return redact_text(data[-limit:].decode("utf-8", errors="replace"))


def run_doctor(root: Path) -> str:
    candidates = [root / ".venv" / "Scripts" / "python.exe", Path(sys.executable)]
    python = next((path for path in candidates if path.is_file()), None)
    if python is None:
        return "Python runtime unavailable."
    command = [str(python), str(root / "scripts" / "doctor.py"), "--config", "bridge.json"]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=90, check=False)
    return redact_text((result.stdout + "\n" + result.stderr).strip())


def main() -> int:
    args = parse_args()
    root = project_root()
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
        "cwd": str(root),
        "files": {
            "bridge.json": file_fingerprint(root / "bridge.json"),
            ".env": file_fingerprint(root / ".env"),
            ".eitaa_session.json": file_fingerprint(root / ".eitaa_session.json"),
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
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("system.json", json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("bridge.redacted.json", json.dumps(safe_bridge_config(root), ensure_ascii=False, indent=2) + "\n")
        archive.writestr("doctor.txt", run_doctor(root) + "\n")
        for relative in ["runtime/logs/api.log", "runtime/logs/desktop.log"]:
            content = tail(root / relative)
            if content:
                archive.writestr(f"logs/{Path(relative).name}", content)
        for base_relative in ["diagnostics/bridge", "diagnostics/core"]:
            base = root / base_relative
            if base.is_dir():
                for path in sorted(base.rglob("*.jsonl"))[-20:]:
                    archive.writestr(f"safe-diagnostics/{base.name}/{path.name}", tail(path, 100_000))
        archive.writestr(
            "README.txt",
            "This bundle intentionally excludes .env, Session contents, SQLite contents, media, and WordPress credentials.\n"
            "File hashes are truncated fingerprints and are not authentication secrets.\n",
        )
    temporary.replace(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
