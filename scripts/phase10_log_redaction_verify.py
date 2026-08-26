"""Scan every runtime JSONL log without echoing paths, account ids, or values."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UNSAFE_KEY_PARTS = (
    "authorization",
    "cookie",
    "ciphertext",
    "raw_phone",
    "access_hash",
    "otp",
    "secret",
    "token",
)
FULL_IRANIAN_MOBILE = re.compile(r"(?<!\d)(?:\+98|0098|0)9\d{9}(?!\d)")
BEARER_VALUE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Installation root. Reports never include this path.",
    )
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def _redacted(value: Any) -> bool:
    return value is None or value == "[redacted]"


def _walk(value: Any, *, findings: list[str]) -> None:
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.casefold()
            unsafe_key = any(part in lowered for part in UNSAFE_KEY_PARTS)
            password_value = "password" in lowered and not (
                isinstance(item, bool)
                and lowered.endswith(("_pending", "_required", "_configured"))
            )
            if (unsafe_key or password_value) and not _redacted(item):
                findings.append("unsafe_key_value")
            _walk(item, findings=findings)
        return
    if isinstance(value, list):
        for item in value:
            _walk(item, findings=findings)
        return
    if isinstance(value, str):
        if FULL_IRANIAN_MOBILE.search(value):
            findings.append("full_phone_value")
        if BEARER_VALUE.search(value):
            findings.append("bearer_value")


def _rotations(current: Path) -> list[Path]:
    """Return only regular, non-symlink numeric rotations for one current log."""

    if not current.parent.is_dir() or current.parent.is_symlink():
        return []
    selected: list[tuple[int, Path]] = []
    try:
        candidates = current.parent.glob(current.name + ".*")
        for candidate in candidates:
            suffix = candidate.name.removeprefix(current.name + ".")
            if (
                suffix.isdecimal()
                and candidate.is_file()
                and not candidate.is_symlink()
            ):
                selected.append((int(suffix), candidate))
    except OSError:
        return []
    return [path for _, path in sorted(selected)]


def _targets(root: Path) -> tuple[list[tuple[str, str, Path]], int, list[str]]:
    """Discover bounded log targets and assign account-opaque report scopes."""

    runtime = root / "runtime"
    application = runtime / "logs" / "application.jsonl"
    targets: list[tuple[str, str, Path]] = [("application", "current", application)]
    targets.extend(
        ("application", path.name.removeprefix(application.name + "."), path)
        for path in _rotations(application)
    )

    discovery_findings: list[str] = []
    accounts_root = runtime / "accounts"
    account_directories: list[Path] = []
    if accounts_root.is_dir() and not accounts_root.is_symlink():
        try:
            for child in accounts_root.iterdir():
                if child.is_symlink():
                    discovery_findings.append("account_scope_symlink_rejected")
                elif child.is_dir():
                    account_directories.append(child)
        except OSError:
            discovery_findings.append("account_scope_enumeration_failed")
    elif accounts_root.is_symlink():
        discovery_findings.append("accounts_root_symlink_rejected")

    for index, account_directory in enumerate(
        sorted(account_directories, key=lambda item: item.name.casefold()),
        start=1,
    ):
        scope = f"account-{index:04d}"
        worker = account_directory / "logs" / "worker.jsonl"
        targets.append((scope, "current", worker))
        targets.extend(
            (scope, path.name.removeprefix(worker.name + "."), path)
            for path in _rotations(worker)
        )
    return targets, len(account_directories), discovery_findings


def scan_runtime_logs(root: str | Path) -> dict[str, object]:
    """Scan a synthetic or live installation root and return only opaque metadata."""

    selected_root = Path(root).expanduser().resolve()
    targets, account_scope_count, discovery_findings = _targets(selected_root)
    files: list[dict[str, object]] = []
    all_findings: list[dict[str, object]] = [
        {"scope": "discovery", "line": 0, "kind": kind}
        for kind in discovery_findings
    ]
    for scope, rotation, log in targets:
        file_summary: dict[str, object] = {
            "scope": scope,
            "channel": "application" if scope == "application" else "worker",
            "rotation": rotation,
            "present": False,
            "records": 0,
            "invalid_json": 0,
            "invalid_utf8": 0,
        }
        if not log.is_file() or log.is_symlink():
            if rotation == "current":
                all_findings.append({"scope": scope, "line": 0, "kind": "required_log_missing"})
            files.append(file_summary)
            continue
        records = 0
        invalid_json = 0
        invalid_utf8 = 0
        try:
            with log.open("r", encoding="utf-8", errors="strict") as stream:
                for line_number, raw in enumerate(stream, start=1):
                    if not raw.strip():
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        invalid_json += 1
                        all_findings.append(
                            {"scope": scope, "line": line_number, "kind": "invalid_json"}
                        )
                        continue
                    records += 1
                    findings: list[str] = []
                    _walk(payload, findings=findings)
                    for finding in sorted(set(findings)):
                        all_findings.append(
                            {"scope": scope, "line": line_number, "kind": finding}
                        )
        except UnicodeDecodeError:
            invalid_utf8 = 1
            all_findings.append({"scope": scope, "line": 0, "kind": "invalid_utf8"})
        except OSError:
            all_findings.append({"scope": scope, "line": 0, "kind": "log_read_failed"})
        file_summary.update(
            {
                "present": True,
                "bytes": log.stat().st_size,
                "records": records,
                "invalid_json": invalid_json,
                "invalid_utf8": invalid_utf8,
            }
        )
        files.append(file_summary)

    return {
        "format": "eitaa-bridge-log-redaction-verification-v2",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "verified": not all_findings and bool(files),
        "account_scope_count": account_scope_count,
        "files": files,
        "finding_count": len(all_findings),
        "findings": all_findings,
    }


def main() -> int:
    args = parse_args()
    selected_root = args.root.expanduser().resolve()
    result = scan_runtime_logs(selected_root)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        report = args.report.expanduser().resolve()
        allowed = (selected_root / "backups" / "phase10-rollout").resolve()
        if report.parent != allowed:
            raise ValueError("Report must be written directly in backups/phase10-rollout.")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
