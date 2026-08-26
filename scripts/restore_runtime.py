from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZipFile

from runtime_state import project_root, verify_backup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore an Eitaa Bridge runtime-state backup.")
    parser.add_argument("backup", type=Path)
    confirmation = parser.add_mutually_exclusive_group()
    confirmation.add_argument("--yes", action="store_true", help="Confirm destructive restore.")
    confirmation.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify the archive and report safe counts without extracting or changing state.",
    )
    parser.add_argument("--skip-current-backup", action="store_true")
    return parser.parse_args()


def safe_member(name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != "state":
        raise ValueError(f"Unsafe backup member: {name}")
    return Path(*pure.parts[1:])


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def dry_run_backup(backup: Path) -> dict[str, object]:
    """Verify a backup completely and return only non-secret readiness metadata."""

    manifest = verify_backup(backup)
    return {
        "verified": True,
        "format": manifest["format"],
        "product_version": manifest.get("product_version", "unknown"),
        "file_count": int(manifest["file_count"]),
        "total_bytes": sum(int(item["size"]) for item in manifest["files"]),
        "include_media": bool(manifest.get("include_media")),
        "include_logs": bool(manifest.get("include_logs")),
    }


def restore_backup(backup: Path, *, root: Path) -> dict[str, object]:
    """Restore a verified archive to an explicit root with in-process rollback."""

    selected_backup = backup.expanduser().resolve()
    selected_root = root.expanduser().resolve()
    if not selected_root.is_dir():
        raise ValueError("Restore root is not an existing directory.")
    manifest = verify_backup(selected_backup)
    expected = {str(item["path"]): dict(item) for item in manifest["files"]}
    with tempfile.TemporaryDirectory(prefix="eitaa-bridge-restore-") as temp_name:
        temp = Path(temp_name)
        staging = temp / "staging"
        rollback = temp / "rollback"
        extracted: list[tuple[Path, Path, Path]] = []
        with ZipFile(selected_backup, "r") as archive:
            for relative_name, item in expected.items():
                relative = safe_member(f"state/{relative_name}")
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(f"state/{relative_name}", "r") as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                if target.stat().st_size != int(item["size"]) or digest(target) != str(item["sha256"]):
                    raise ValueError("Extracted backup member does not match the verified manifest.")
                destination = (selected_root / relative).resolve()
                if destination == selected_root or selected_root not in destination.parents:
                    raise ValueError("Restore destination escapes the selected root.")
                extracted.append((target, destination, rollback / relative))

        applied: list[tuple[Path, Path | None]] = []
        try:
            for source, destination, rollback_path in extracted:
                previous: Path | None = None
                if destination.exists():
                    if not destination.is_file():
                        raise ValueError("Restore destination is not a regular file.")
                    rollback_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, rollback_path)
                    previous = rollback_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(
                    f".{destination.name}.restore-{uuid4().hex}.tmp"
                )
                shutil.copy2(source, temporary)
                temporary.replace(destination)
                applied.append((destination, previous))
        except Exception:
            for destination, previous in reversed(applied):
                if previous is None:
                    destination.unlink(missing_ok=True)
                    continue
                temporary = destination.with_name(
                    f".{destination.name}.rollback-{uuid4().hex}.tmp"
                )
                shutil.copy2(previous, temporary)
                temporary.replace(destination)
            raise
    return {
        "restored": True,
        "file_count": int(manifest["file_count"]),
        "total_bytes": sum(int(item["size"]) for item in manifest["files"]),
    }


def main() -> int:
    args = parse_args()
    backup = args.backup.expanduser().resolve()
    if args.dry_run:
        try:
            print(json.dumps(dry_run_backup(backup), sort_keys=True))
            return 0
        except (OSError, ValueError) as exc:
            print(f"Backup dry-run failed: {type(exc).__name__}", file=sys.stderr)
            return 1
    if not args.yes:
        print("Restore not confirmed. Re-run with --yes.", file=sys.stderr)
        return 2
    root = project_root()
    if not backup.is_file():
        print("Backup file was not found.", file=sys.stderr)
        return 1
    if not args.skip_current_backup:
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "backup_runtime.py"), "--quiet"],
            cwd=root,
            check=False,
        )
        if result.returncode != 0:
            print("Could not create the mandatory pre-restore backup.", file=sys.stderr)
            return 1
    try:
        result = restore_backup(backup, root=root)
    except (OSError, ValueError) as exc:
        print(f"Restore failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Restored {result['file_count']} files from {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
