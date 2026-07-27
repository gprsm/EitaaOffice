from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
