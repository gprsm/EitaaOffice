"""Restore and roll back a verified backup only inside an isolated temporary copy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from restore_runtime import digest, dry_run_backup, restore_backup
from runtime_state import verify_backup


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def _archive_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def execute(backup: Path) -> dict[str, object]:
    selected = backup.expanduser().resolve()
    manifest = verify_backup(selected)
    preview = dry_run_backup(selected)
    rehearsal_parent = (ROOT / "backups" / "phase10-rollout").resolve()
    rehearsal_parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix="phase10d-copy-", dir=rehearsal_parent) as temporary:
        temporary_path = Path(temporary).resolve()
        copy_root = temporary_path / "restored-copy"
        copy_root.mkdir()
        if ROOT == copy_root or copy_root in ROOT.parents:
            raise ValueError("Copy rehearsal root overlaps the live installation.")
        restored = restore_backup(selected, root=copy_root)
        hashes_match = True
        for item in manifest["files"]:
            target = copy_root / str(item["path"])
            if not target.is_file() or target.stat().st_size != int(item["size"]):
                hashes_match = False
                break
            if digest(target) != str(item["sha256"]):
                hashes_match = False
                break

        bridge = copy_root / "bridge.json"
        rollback_exercised = False
        rollback_hash_match = False
        if bridge.is_file():
            original_hash = digest(bridge)
            payload = json.loads(bridge.read_text(encoding="utf-8-sig"))
            features = payload.setdefault("features", {})
            multi_session = features.setdefault("multi_session", {})
            current = bool(multi_session.get("enabled", False))
            multi_session["enabled"] = not current
            bridge.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rollback_exercised = digest(bridge) != original_hash
            restore_backup(selected, root=copy_root)
            rollback_hash_match = digest(bridge) == original_hash

        result = {
            "format": "eitaa-bridge-phase10d-copy-rehearsal-v1",
            "verified": bool(
                preview["verified"]
                and restored["restored"]
                and hashes_match
                and rollback_exercised
                and rollback_hash_match
            ),
            "backup_name": selected.name,
            "backup_sha256": _archive_digest(selected),
            "file_count": int(preview["file_count"]),
            "total_bytes": int(preview["total_bytes"]),
            "include_media": bool(preview["include_media"]),
            "include_logs": bool(preview["include_logs"]),
            "copy_restore_verified": bool(restored["restored"] and hashes_match),
            "copy_feature_toggle_exercised": rollback_exercised,
            "copy_rollback_hash_match": rollback_hash_match,
            "live_root_targeted": False,
        }
    result["temporary_copy_removed"] = bool(temporary_path and not temporary_path.exists())
    result["verified"] = bool(result["verified"] and result["temporary_copy_removed"])
    return result


def main() -> int:
    args = parse_args()
    report = args.report.expanduser().resolve()
    allowed = (ROOT / "backups" / "phase10-rollout").resolve()
    if report.parent != allowed:
        raise ValueError("Report must be written directly in backups/phase10-rollout.")
    result = execute(args.backup)
    report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
