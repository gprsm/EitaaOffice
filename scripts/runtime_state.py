from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable
from zipfile import BadZipFile, ZipFile

PRODUCT_MARKER = "eitaa-bridge-runtime-backup-v1"


@dataclass(frozen=True)
class StateEntry:
    source: Path
    archive_name: str


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def state_entries(root: Path, *, include_media: bool = True, include_logs: bool = False) -> list[StateEntry]:
    entries: list[StateEntry] = []
    fixed_files = [
        "bridge.json",
        ".env",
        ".eitaa_session.json",
        "composition.json",
        "data/bridge_compositions.json",
        "ui/preferences.json",
    ]
    for relative in fixed_files:
        path = root / relative
        if path.is_file():
            entries.append(StateEntry(path, relative.replace("\\", "/")))

    for pattern in ("selected*.json",):
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                entries.append(StateEntry(path, path.name))

    directories = ["data"]
    if not include_media:
        excluded_prefix = (root / "data" / "media").resolve()
    else:
        excluded_prefix = None
    if include_logs:
        directories.extend(["diagnostics", "runtime/logs"])
    for relative in directories:
        base = root / relative
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if _excluded_state_file(path, root):
                continue
            resolved = path.resolve()
            if excluded_prefix is not None and (resolved == excluded_prefix or excluded_prefix in resolved.parents):
                continue
            if "backups" in path.parts:
                continue
            archive_name = path.relative_to(root).as_posix()
            if any(item.archive_name == archive_name for item in entries):
                continue
            entries.append(StateEntry(path, archive_name))

    fonts = root / "ui" / "fonts"
    if fonts.is_dir():
        for path in sorted(fonts.glob("*.woff2")):
            entries.append(StateEntry(path, path.relative_to(root).as_posix()))
    return entries


def _excluded_state_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part.startswith(".staging-") for part in relative.parts):
        return True
    lowered = path.name.lower()
    return lowered in {"lock"} or lowered.endswith((".tmp", ".part"))


def manifest_for(entries: Iterable[StateEntry], *, product_version: str, include_media: bool, include_logs: bool) -> dict[str, object]:
    files = []
    for entry in entries:
        stat = entry.source.stat()
        files.append(
            {
                "path": entry.archive_name,
                "size": stat.st_size,
                "sha256": sha256_file(entry.source),
            }
        )
    return {
        "format": PRODUCT_MARKER,
        "product_version": product_version,
        "include_media": include_media,
        "include_logs": include_logs,
        "file_count": len(files),
        "files": files,
    }


def load_version(root: Path) -> str:
    version_file = root / "VERSION.txt"
    if not version_file.is_file():
        return "unknown"
    for line in version_file.read_text(encoding="utf-8-sig").splitlines():
        if line.lower().startswith("product:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_backup(path: Path) -> dict[str, object]:
    """Verify manifest membership, size, and SHA-256 without extracting state."""

    selected = path.expanduser().resolve()
    try:
        archive = ZipFile(selected, "r")
    except (OSError, BadZipFile) as exc:
        raise ValueError("Backup is not a readable ZIP archive.") from exc
    with archive:
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Backup manifest is missing or invalid.") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != PRODUCT_MARKER:
            raise ValueError("Backup format is not supported.")
        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, list):
            raise ValueError("Backup manifest file list is invalid.")
        expected: dict[str, dict[str, object]] = {}
        for item in manifest_files:
            if not isinstance(item, dict):
                raise ValueError("Backup manifest contains an invalid file entry.")
            relative = str(item.get("path") or "")
            pure = PurePosixPath(relative)
            if not relative or pure.is_absolute() or ".." in pure.parts or relative in expected:
                raise ValueError("Backup manifest contains an unsafe or duplicate path.")
            try:
                size = int(item["size"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Backup manifest contains an invalid file size.") from exc
            checksum = str(item.get("sha256") or "").lower()
            if size < 0 or len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
                raise ValueError("Backup manifest contains invalid file metadata.")
            expected[relative] = {"size": size, "sha256": checksum}
        archive_infos = [info for info in archive.infolist() if not info.is_dir()]
        archive_names = [info.filename for info in archive_infos]
        if len(archive_names) != len(set(archive_names)):
            raise ValueError("Backup archive contains a duplicate member.")
        permitted_names = {"manifest.json", *(f"state/{name}" for name in expected)}
        if set(archive_names) != permitted_names:
            raise ValueError("Backup archive membership is not canonical.")
        archive_files = {
            info.filename[len("state/") :]: info
            for info in archive_infos
            if info.filename.startswith("state/")
        }
        if set(archive_files) != set(expected):
            raise ValueError("Backup members do not match the manifest.")
        for relative, item in expected.items():
            info = archive_files[relative]
            expected_size = int(item["size"])
            if info.file_size != expected_size:
                raise ValueError("Backup member size does not match the manifest.")
            digest = hashlib.sha256()
            with archive.open(info, "r") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != str(item["sha256"]):
                raise ValueError("Backup member checksum does not match the manifest.")
        try:
            file_count = int(manifest.get("file_count", -1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Backup file count is invalid.") from exc
        if file_count != len(expected):
            raise ValueError("Backup file count does not match the manifest.")
        return manifest
