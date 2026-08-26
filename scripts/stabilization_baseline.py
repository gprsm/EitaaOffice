from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


SCHEMA_VERSION = 1
CONTENT_MANIFEST_NAME = "_baseline/CONTENT_MANIFEST.json"
FIXED_ZIP_TIME = (2026, 8, 25, 0, 0, 0)

ALLOWED_DIRECTORY_PREFIXES = (
    "src",
    "tests",
    "scripts",
    "installer",
    "docs",
    "ui/src",
    "ui/scripts",
    "ui/electron",
    "ui/public",
)
IGNORED_DIRECTORY_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".vite",
    "build",
    "dist",
    "node_modules",
    "release",
}
IGNORED_FILE_SUFFIXES = (".pyc", ".pyo", ".tsbuildinfo")
ALLOWED_ROOT_FILES = {
    ".env.example",
    ".env.multisite.example",
    ".gitignore",
    "AGENTS.md",
    "ARCHITECTURE_DECISIONS.md",
    "CHECKSUMS.sha256",
    "README.md",
    "RELEASE_MANIFEST.json",
    "VERSION.txt",
    "bridge.example.json",
    "bridge.multisite.example.json",
    "bridge.trusted-lan-http.example.json",
    "bridge.web-reverse-proxy.example.json",
    "composition.example.json",
    "package_clean.py",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
}
ALLOWED_ROOT_SUFFIXES = (".bat", ".vbs")
ALLOWED_UI_ROOT_FILES = {
    "index.html",
    "package-lock.json",
    "package.json",
    "tsconfig.json",
    "tsconfig.node.json",
    "vite.config.ts",
}
EXCLUDED_SCOPE_LABELS = (
    ".env and local credential files",
    "bridge.json and live configuration",
    "session files",
    "data/runtime/diagnostics/backups/catalog",
    "Bale and lab artifacts",
    "virtual environments and dependency trees",
    "build/dist/release outputs",
    "test caches and temporary workspaces",
)


class BaselineError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object, *, pretty: bool = False) -> bytes:
    if pretty:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    else:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return (rendered + "\n").encode("utf-8")


def _is_ignored_relative(relative: Path) -> bool:
    if any(part in IGNORED_DIRECTORY_NAMES for part in relative.parts[:-1]):
        return True
    return relative.name.endswith(IGNORED_FILE_SUFFIXES)


def _allowed_root_file(path: Path) -> bool:
    name = path.name
    if name in ALLOWED_ROOT_FILES or name.endswith(ALLOWED_ROOT_SUFFIXES):
        return True
    return name.startswith("bridge.") and name.endswith(".example.json")


def _allowed_ui_root_file(path: Path) -> bool:
    return path.name in ALLOWED_UI_ROOT_FILES


def _safe_file(path: Path, *, root: Path) -> Path:
    if path.is_symlink():
        raise BaselineError(f"Symlinks are not allowed in the baseline scope: {path.name}")
    if not path.is_file():
        raise BaselineError(f"The baseline entry is not a regular file: {path.name}")
    resolved = path.resolve(strict=True)
    selected_root = root.resolve(strict=True)
    if selected_root != resolved and selected_root not in resolved.parents:
        raise BaselineError("A baseline entry resolved outside the project root.")
    return path


def _iter_directory_files(root: Path, prefix: str) -> Iterable[Path]:
    directory = root.joinpath(*prefix.split("/"))
    if not directory.exists():
        return ()
    if directory.is_symlink():
        raise BaselineError(f"Symlinked baseline roots are not allowed: {prefix}")
    if not directory.is_dir():
        raise BaselineError(f"Expected a baseline directory: {prefix}")
    return (
        path
        for path in directory.rglob("*")
        if path.is_file() or path.is_symlink()
    )


def collect_baseline_files(root: Path) -> tuple[Path, ...]:
    selected_root = root.resolve(strict=True)
    candidates: list[Path] = []

    for path in selected_root.iterdir():
        if path.is_symlink() and (_allowed_root_file(path) or path.name == "ui"):
            raise BaselineError(f"Symlinked baseline entries are not allowed: {path.name}")
        if path.is_file() and _allowed_root_file(path):
            candidates.append(_safe_file(path, root=selected_root))

    ui_root = selected_root / "ui"
    if ui_root.exists():
        if ui_root.is_symlink():
            raise BaselineError("The ui baseline root must not be a symlink.")
        for path in ui_root.iterdir():
            if path.is_file() and _allowed_ui_root_file(path):
                candidates.append(_safe_file(path, root=selected_root))

    for prefix in ALLOWED_DIRECTORY_PREFIXES:
        for path in _iter_directory_files(selected_root, prefix):
            relative = path.relative_to(selected_root)
            if _is_ignored_relative(relative):
                continue
            candidates.append(_safe_file(path, root=selected_root))

    unique: dict[str, Path] = {}
    casefolded: dict[str, str] = {}
    for path in candidates:
        relative = path.relative_to(selected_root).as_posix()
        folded = relative.casefold()
        previous = casefolded.get(folded)
        if previous is not None and previous != relative:
            raise BaselineError(
                f"Case-insensitive path collision in baseline scope: {previous} / {relative}"
            )
        casefolded[folded] = relative
        unique[relative] = path
    return tuple(unique[name] for name in sorted(unique))


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _verify_archive(archive_path: Path, content_manifest: dict[str, object]) -> None:
    expected_files = [str(item["path"]) for item in content_manifest["files"]]  # type: ignore[index]
    expected_names = [*expected_files, CONTENT_MANIFEST_NAME]
    with ZipFile(archive_path) as archive:
        if archive.namelist() != expected_names:
            raise BaselineError("The written archive does not match the allowlisted manifest.")
        for item in content_manifest["files"]:  # type: ignore[index]
            name = str(item["path"])
            if _sha256(archive.read(name)) != str(item["sha256"]):
                raise BaselineError(f"Archive verification failed for {name}.")
        stored_manifest = json.loads(archive.read(CONTENT_MANIFEST_NAME))
        if stored_manifest != content_manifest:
            raise BaselineError("The archive content manifest is inconsistent.")


def create_baseline(
    root: Path,
    archive_path: Path,
    receipt_path: Path,
    *,
    created_at: str | None = None,
    force: bool = False,
) -> dict[str, object]:
    selected_root = root.resolve(strict=True)
    selected_archive = archive_path.resolve()
    selected_receipt = receipt_path.resolve()
    if not force and (selected_archive.exists() or selected_receipt.exists()):
        raise BaselineError("Baseline output already exists; use --force only after review.")
    if selected_archive == selected_receipt:
        raise BaselineError("Archive and receipt paths must be different.")

    files = collect_baseline_files(selected_root)
    entries: list[dict[str, object]] = []
    file_payloads: list[tuple[str, bytes]] = []
    for path in files:
        relative = path.relative_to(selected_root).as_posix()
        payload = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": _sha256(payload),
                "size_bytes": len(payload),
            }
        )
        file_payloads.append((relative, payload))

    content_set_bytes = _json_bytes(entries)
    content_manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "safe-product-source-ui-tests-scripts-installer-docs",
        "root": "<project-root>",
        "file_count": len(entries),
        "content_set_sha256": _sha256(content_set_bytes),
        "files": entries,
    }
    manifest_bytes = _json_bytes(content_manifest, pretty=True)

    selected_archive.parent.mkdir(parents=True, exist_ok=True)
    selected_receipt.parent.mkdir(parents=True, exist_ok=True)
    archive_temp = selected_archive.with_name(f".{selected_archive.name}.tmp")
    receipt_temp = selected_receipt.with_name(f".{selected_receipt.name}.tmp")
    if archive_temp.exists() or receipt_temp.exists():
        raise BaselineError("A baseline temporary output already exists; manual review is required.")

    try:
        with ZipFile(
            archive_temp,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, payload in file_payloads:
                archive.writestr(_zip_info(relative), payload)
            archive.writestr(_zip_info(CONTENT_MANIFEST_NAME), manifest_bytes)
        _verify_archive(archive_temp, content_manifest)
        archive_sha256 = _sha256(archive_temp.read_bytes())
        receipt: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            "root": "<project-root>",
            "scope": content_manifest["scope"],
            "file_count": len(entries),
            "content_set_sha256": content_manifest["content_set_sha256"],
            "content_manifest_sha256": _sha256(manifest_bytes),
            "archive_name": selected_archive.name,
            "archive_sha256": archive_sha256,
            "archive_size_bytes": archive_temp.stat().st_size,
            "excluded_scopes": list(EXCLUDED_SCOPE_LABELS),
            "verification": "archive reopened; names, manifest and every file SHA-256 matched",
        }
        receipt_temp.write_bytes(_json_bytes(receipt, pretty=True))
        archive_temp.replace(selected_archive)
        receipt_temp.replace(selected_receipt)
        return receipt
    except Exception:
        archive_temp.unlink(missing_ok=True)
        receipt_temp.unlink(missing_ok=True)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a deterministic, allowlisted stabilization baseline."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "artifacts" / "stabilization",
    )
    parser.add_argument("--label", default="STAB-G00-R01-safe-baseline")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = args.output_dir.resolve()
    archive_path = output_dir / f"{args.label}.zip"
    receipt_path = output_dir / f"{args.label}.receipt.json"
    receipt = create_baseline(
        args.root,
        archive_path,
        receipt_path,
        force=bool(args.force),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "archive": archive_path.name,
                "receipt": receipt_path.name,
                "file_count": receipt["file_count"],
                "archive_sha256": receipt["archive_sha256"],
                "content_set_sha256": receipt["content_set_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
