from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from runtime_state import PRODUCT_MARKER, project_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore an Eitaa Bridge runtime-state backup.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--yes", action="store_true", help="Confirm destructive restore.")
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


def main() -> int:
    args = parse_args()
    if not args.yes:
        print("Restore not confirmed. Re-run with --yes.", file=sys.stderr)
        return 2
    root = project_root()
    backup = args.backup.expanduser().resolve()
    if not backup.is_file():
        print("Backup file was not found.", file=sys.stderr)
        return 1
    try:
        archive = ZipFile(backup, "r")
    except BadZipFile:
        print("Backup is not a valid ZIP file.", file=sys.stderr)
        return 1
    with archive:
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            print("Backup manifest is missing or invalid.", file=sys.stderr)
            return 1
        if manifest.get("format") != PRODUCT_MARKER:
            print("Backup format is not supported.", file=sys.stderr)
            return 1
        expected = {str(item["path"]): str(item["sha256"]) for item in manifest.get("files", [])}
        with tempfile.TemporaryDirectory(prefix="eitaa-bridge-restore-") as temp_name:
            temp = Path(temp_name)
            extracted: list[tuple[Path, Path]] = []
            for info in archive.infolist():
                if not info.filename.startswith("state/") or info.is_dir():
                    continue
                relative = safe_member(info.filename)
                target = temp / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                expected_hash = expected.get(relative.as_posix())
                if expected_hash and digest(target) != expected_hash:
                    print(f"Checksum mismatch: {relative}", file=sys.stderr)
                    return 1
                extracted.append((target, root / relative))

            if not args.skip_current_backup:
                result = subprocess.run(
                    [sys.executable, str(root / "scripts" / "backup_runtime.py"), "--quiet"],
                    cwd=root,
                    check=False,
                )
                if result.returncode != 0:
                    print("Could not create the mandatory pre-restore backup.", file=sys.stderr)
                    return 1

            for source, destination in extracted:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".restore.tmp")
                shutil.copy2(source, temporary)
                temporary.replace(destination)
    print(f"Restored {manifest.get('file_count', 0)} files from {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
