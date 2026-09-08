from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo


SCHEMA_VERSION = 1
CONTENT_MANIFEST_NAME = "_release/CONTENT_MANIFEST.json"
FIXED_ZIP_TIME = (2026, 8, 26, 0, 0, 0)
MAX_ARCHIVE_ENTRIES = 20_000
MAX_ARCHIVE_FILE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 1024 * 1024 * 1024

ROOT_RELEASE_FILES = {
    ".env.example",
    ".env.multisite.example",
    ".gitignore",
    "ARCHITECTURE_DECISIONS.md",
    "BUILD_OFFICE_SETUP_EXE.bat",
    "EitaaBridge.bat",
    "EitaaBridgeElectron.bat",
    "EitaaBridgeLanServer.bat",
    "EitaaBridgeOffice.vbs",
    "README.md",
    "VERSION.txt",
    "backup_now.bat",
    "bridge.example.json",
    "bridge.multisite.example.json",
    "bridge.trusted-lan-http.example.json",
    "bridge.web-reverse-proxy.example.json",
    "build_wheel.bat",
    "build_windows_installer.bat",
    "composition.example.json",
    "create_diagnostics.bat",
    "install_app.bat",
    "install_bridge.bat",
    "open_runtime_logs.bat",
    "package_clean.py",
    "pyproject.toml",
    "repair_app.bat",
    "requirements-dev.txt",
    "requirements.txt",
    "restore_backup.bat",
    "run_api.bat",
    "run_api_health.bat",
    "run_auth_status.bat",
    "run_composer_preview.bat",
    "run_composer_publish.bat",
    "run_composer_status.bat",
    "run_doctor.bat",
    "run_message_usage.bat",
    "run_publication_one.bat",
    "run_publication_preview.bat",
    "run_publication_restore.bat",
    "run_publication_restore_preview.bat",
    "run_publication_status.bat",
    "run_publication_update.bat",
    "run_publication_update_preview.bat",
    "run_sites_list.bat",
    "run_tests.bat",
    "run_ui.bat",
    "run_ui_checks.bat",
    "run_wp_categories.bat",
    "run_wp_draft.bat",
    "run_wp_info.bat",
    "run_wp_media_info.bat",
    "run_wp_media_upload.bat",
    "run_wp_tags.bat",
    "run_wp_test.bat",
    "setup_ui.bat",
    "setup_venv.bat",
    "stop_eitaa_bridge.bat",
    "upgrade_from_application_api1.bat",
    "upgrade_from_foundation3.bat",
    "upgrade_from_ui_mvp1.bat",
    "upgrade_from_ui_mvp1_1.bat",
    "upgrade_from_ui_mvp2.bat",
    "upgrade_from_ui_mvp3.bat",
    "upgrade_from_ui_mvp4.bat",
    "upgrade_from_ui_mvp5.bat",
    "upgrade_from_ui_mvp5_1.bat",
    "upgrade_from_ui_mvp5_2.bat",
    "upgrade_from_ui_mvp5_3.bat",
    "upgrade_from_ui_mvp5_4.bat",
    "upgrade_from_ui_mvp5_5.bat",
    "upgrade_from_ui_mvp5_6.bat",
    "upgrade_from_ui_mvp6_0.bat",
    "upgrade_from_wordpress_composer1.bat",
    "upgrade_from_wordpress_media1.bat",
    "upgrade_from_wordpress_publication1.bat",
    "upgrade_from_wordpress_update1.bat",
    "upgrade_from_wordpress_update1_1.bat",
    "upgrade_from_wordpress_update1_2.bat",
}

UI_ROOT_FILES = {
    "ui/.npmrc",
    "ui/index.html",
    "ui/package-lock.json",
    "ui/package.json",
    "ui/tsconfig.app.json",
    "ui/tsconfig.json",
    "ui/vite.config.ts",
}

SCRIPT_FILES = {
    "scripts/archive_previous_office_release.ps1",
    "scripts/backup_runtime.py",
    "scripts/build_self_contained_setup.py",
    "scripts/build_windows_icon.ps1",
    "scripts/build_wheel_stdlib.py",
    "scripts/check_runtime_environment.py",
    "scripts/create_diagnostics_bundle.py",
    "scripts/create_shortcuts.ps1",
    "scripts/doctor.py",
    "scripts/migrate_legacy_account.py",
    "scripts/new_internal_code_signing_certificate.ps1",
    "scripts/office_runtime.py",
    "scripts/prepare_windows_release.py",
    "scripts/restore_runtime.py",
    "scripts/runtime_state.py",
    "scripts/scan_diagnostics_bundle.py",
    "scripts/sign_windows_release.ps1",
    "scripts/sync_ui_fonts.py",
    "scripts/verify_windows_release_signature.ps1",
    "scripts/write_iexpress_sed.py",
}

INSTALLER_FILES = {
    "installer/EitaaBridge.iss",
    "installer/assets/EitaaBridge.ico",
    "installer/assets/EitaaBridge-source.png",
    "installer/check_windows_version.vbs",
    "installer/install_office_payload.cmd",
    "installer/license-policy.json",
}

DOCUMENTATION_FILES = {
    "docs/APPLICATION_API.md",
    "docs/ARCHITECTURE.md",
    "docs/BACKUP_RESTORE.md",
    "docs/BULK_OPERATIONS.md",
    "docs/DEVELOPMENT_GUIDE.md",
    "docs/INSTALLER.md",
    "docs/INTERNAL_CODE_SIGNING.md",
    "docs/LOGGING_AND_OBSERVABILITY.md",
    "docs/MIGRATION_GUIDE.md",
    "docs/MULTI_SITE.md",
    "docs/OFFICE_DEPLOYMENT.md",
    "docs/OFFLINE_ACTIVATION.md",
    "docs/PHASE10_CONTROLLED_ROLLOUT_RUNBOOK.md",
    "docs/PHASE10_WEB_REVERSE_PROXY_DEPLOYMENT.md",
    "docs/PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md",
    "docs/RUNTIME_OWNERSHIP.md",
    "docs/SECURITY.md",
    "docs/TRUSTED_LAN_HTTP_CONFIGURATION.md",
    "docs/UI_MVP.md",
    "docs/WORKER_IPC_PROTOCOL.md",
    "docs/WORDPRESS_COMPOSER.md",
    "docs/WORDPRESS_MEDIA.md",
    "docs/WORDPRESS_PUBLICATION.md",
    "docs/WORDPRESS_SITE_SETTINGS.md",
    "docs/WORDPRESS_UPDATE.md",
    "docs/WRITE_RETRY_SAFETY.md",
}

OFFLINE_WHEEL_FILES = {
    "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl",
    "vendor/eitaa_core-0.6.0.dev19-py3-none-any.whl",
    "vendor/runtime/certifi-2026.6.17-py3-none-any.whl",
    "vendor/runtime/cffi-2.1.1-cp313-cp313-win_amd64.whl",
    "vendor/runtime/charset_normalizer-3.4.9-cp313-cp313-win_amd64.whl",
    "vendor/runtime/cryptography-46.0.7-cp311-abi3-win_amd64.whl",
    "vendor/runtime/idna-3.18-py3-none-any.whl",
    "vendor/runtime/requests-2.34.2-py3-none-any.whl",
    "vendor/runtime/pycparser-3.0-py3-none-any.whl",
    "vendor/runtime/tzdata-2026.3-py2.py3-none-any.whl",
    "vendor/runtime/urllib3-2.7.0-py3-none-any.whl",
}

EXACT_RELEASE_FILES = frozenset(
    ROOT_RELEASE_FILES
    | UI_ROOT_FILES
    | SCRIPT_FILES
    | INSTALLER_FILES
    | DOCUMENTATION_FILES
    | OFFLINE_WHEEL_FILES
)

RECURSIVE_RELEASE_SCOPES = {
    "src": frozenset({".py", ".pyi", ".typed"}),
    "ui/src": frozenset({".css", ".d.ts", ".js", ".ts", ".tsx"}),
    "ui/electron": frozenset({".cjs", ".js", ".mjs"}),
    "ui/scripts": frozenset({".cjs", ".js", ".mjs"}),
    "ui/public": frozenset({".ico", ".jpg", ".jpeg", ".png", ".svg", ".woff", ".woff2"}),
    "ui/fonts": frozenset({".txt", ".woff", ".woff2"}),
}
QUARANTINED_RELEASE_PREFIXES = (
    "src/eitaa_bridge/application/bale_client/",
)

EXCLUDED_SCOPE_LABELS = (
    "live .env and bridge configuration",
    "session and credential state",
    "data/runtime/diagnostics/backups/catalog",
    "Bale implementation and operational artifacts",
    "test suites, caches and scratch/fix/probe files",
    "virtual environments and dependency trees",
    "generated UI/build/release output except exact offline wheels",
    "project-memory, handoff and internal stabilization reports",
)

PRIVATE_KEY_PATTERN = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.IGNORECASE,
)
JWT_PATTERN = re.compile(rb"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])")
BRIDGE_SOURCE_SUFFIXES = frozenset({".py", ".pyi", ".typed"})


class PackageError(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def _safe_file(path: Path, *, root: Path) -> Path:
    if path.is_symlink():
        raise PackageError("Symlinks are not allowed in the release scope.")
    if not path.is_file():
        raise PackageError("A release entry is not a regular file.")
    selected_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if selected_root != resolved and selected_root not in resolved.parents:
        raise PackageError("A release entry resolved outside the project root.")
    return path


def _iter_recursive_scope(root: Path, prefix: str, suffixes: frozenset[str]) -> Iterable[Path]:
    directory = root.joinpath(*prefix.split("/"))
    if not directory.exists():
        return ()
    if directory.is_symlink() or not directory.is_dir():
        raise PackageError("A release scope root is not a regular directory.")
    return (
        path
        for path in directory.rglob("*")
        if (path.is_file() or path.is_symlink())
        and path.suffix.lower() in suffixes
        and "__pycache__" not in path.parts
        and not any(
            path.relative_to(root).as_posix().startswith(quarantined)
            for quarantined in QUARANTINED_RELEASE_PREFIXES
        )
    )


def collect_release_files(root: Path) -> tuple[Path, ...]:
    selected_root = root.resolve(strict=True)
    candidates: list[Path] = []
    for relative in sorted(EXACT_RELEASE_FILES):
        path = selected_root.joinpath(*relative.split("/"))
        if path.exists() or path.is_symlink():
            candidates.append(_safe_file(path, root=selected_root))

    for prefix, suffixes in RECURSIVE_RELEASE_SCOPES.items():
        for path in _iter_recursive_scope(selected_root, prefix, suffixes):
            candidates.append(_safe_file(path, root=selected_root))

    unique: dict[str, Path] = {}
    casefolded: dict[str, str] = {}
    for path in candidates:
        relative = path.relative_to(selected_root).as_posix()
        folded = relative.casefold()
        previous = casefolded.get(folded)
        if previous is not None and previous != relative:
            raise PackageError("Case-insensitive path collision in release scope.")
        casefolded[folded] = relative
        unique[relative] = path
    return tuple(unique[name] for name in sorted(unique))


def _validate_archive_name(name: str) -> None:
    if not name or "\\" in name or name.startswith("/") or "//" in name:
        raise PackageError("Archive contains a noncanonical entry name.")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError("Archive contains an unsafe entry name.")
    if path.as_posix() != name:
        raise PackageError("Archive contains a noncanonical entry name.")


def _scan_payload(relative: str, payload: bytes) -> None:
    if PRIVATE_KEY_PATTERN.search(payload) or JWT_PATTERN.search(payload):
        raise PackageError(f"Release content failed high-confidence secret scan: {relative}")


def verify_bridge_wheel_source_parity(root: Path, wheel_path: Path) -> dict[str, object]:
    selected_root = root.resolve(strict=True)
    source_root = selected_root / "src" / "eitaa_bridge"
    selected_wheel = _safe_file(wheel_path, root=selected_root)
    expected: dict[str, bytes] = {}
    for path in source_root.rglob("*"):
        if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in BRIDGE_SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(selected_root / "src").as_posix()
        if f"src/{relative}".startswith(QUARANTINED_RELEASE_PREFIXES):
            continue
        _validate_archive_name(relative)
        expected[relative] = path.read_bytes()

    try:
        with ZipFile(selected_wheel) as wheel:
            infos = wheel.infolist()
            names = [info.filename for info in infos if not info.is_dir()]
            for name in names:
                _validate_archive_name(name)
            if len({name.casefold() for name in names}) != len(names):
                raise PackageError("Bundled bridge wheel contains duplicate names.")
            actual_names = {
                name
                for name in names
                if name.startswith("eitaa_bridge/")
                and PurePosixPath(name).suffix.lower() in BRIDGE_SOURCE_SUFFIXES
            }
            expected_names = set(expected)
            missing = expected_names - actual_names
            extra = actual_names - expected_names
            mismatched = {
                name
                for name in expected_names & actual_names
                if wheel.read(name) != expected[name]
            }
    except BadZipFile as exc:
        raise PackageError("Bundled bridge wheel is not a valid ZIP file.") from exc

    if missing or extra or mismatched:
        raise PackageError(
            "Bundled bridge wheel/source parity failed: "
            f"missing={len(missing)}, mismatched={len(mismatched)}, extra={len(extra)}"
        )
    return {
        "source_file_count": len(expected),
        "missing": 0,
        "mismatched": 0,
        "extra": 0,
        "wheel_sha256": _sha256(selected_wheel.read_bytes()),
    }


def _content_manifest(root: Path) -> tuple[dict[str, object], list[tuple[str, bytes]]]:
    payloads: list[tuple[str, bytes]] = []
    entries: list[dict[str, object]] = []
    for path in collect_release_files(root):
        relative = path.relative_to(root.resolve(strict=True)).as_posix()
        _validate_archive_name(relative)
        payload = path.read_bytes()
        _scan_payload(relative, payload)
        payloads.append((relative, payload))
        entries.append(
            {
                "path": relative,
                "sha256": _sha256(payload),
                "size_bytes": len(payload),
            }
        )
    bridge_wheel = root / "dist" / "eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
    if bridge_wheel.exists():
        verify_bridge_wheel_source_parity(root, bridge_wheel)
    entries_bytes = _json_bytes(entries)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "allowlisted-runtime-source-ui-installer-offline-wheels-and-operator-docs",
        "root": "<project-root>",
        "file_count": len(entries),
        "content_set_sha256": _sha256(entries_bytes),
        "privacy_scan": "high-confidence private-key and JWT patterns: 0 findings",
        "files": entries,
    }
    return manifest, payloads


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def verify_release_archive(archive_path: Path) -> dict[str, object]:
    try:
        with ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise PackageError("Archive exceeds the entry-count safety limit.")
            total_size = 0
            names: list[str] = []
            folded_names: set[str] = set()
            for info in infos:
                name = info.filename
                _validate_archive_name(name)
                if info.is_dir():
                    raise PackageError("Archive must not contain directory entries.")
                if info.file_size > MAX_ARCHIVE_FILE_BYTES:
                    raise PackageError("Archive entry exceeds the file-size safety limit.")
                total_size += info.file_size
                if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                    raise PackageError("Archive exceeds the total-size safety limit.")
                folded = name.casefold()
                if name in names or folded in folded_names:
                    raise PackageError("Archive contains duplicate or case-colliding names.")
                names.append(name)
                folded_names.add(folded)

            if not names or names[-1] != CONTENT_MANIFEST_NAME:
                raise PackageError("Archive content manifest is missing or out of order.")
            try:
                manifest = json.loads(archive.read(CONTENT_MANIFEST_NAME))
            except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise PackageError("Archive content manifest is unreadable.") from exc
            if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
                raise PackageError("Archive content manifest schema is invalid.")
            entries = manifest.get("files")
            if not isinstance(entries, list) or manifest.get("file_count") != len(entries):
                raise PackageError("Archive content manifest count is invalid.")
            expected_names: list[str] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    raise PackageError("Archive content manifest entry is invalid.")
                name = entry.get("path")
                if not isinstance(name, str) or name == CONTENT_MANIFEST_NAME:
                    raise PackageError("Archive content manifest path is invalid.")
                _validate_archive_name(name)
                expected_names.append(name)
            if names != [*expected_names, CONTENT_MANIFEST_NAME]:
                raise PackageError("Archive names do not match the content manifest.")
            if expected_names != sorted(expected_names):
                raise PackageError("Archive content entries are not deterministic.")
            if len({name.casefold() for name in expected_names}) != len(expected_names):
                raise PackageError("Archive manifest contains case-colliding names.")

            for entry in entries:
                name = str(entry["path"])
                payload = archive.read(name)
                if entry.get("size_bytes") != len(payload):
                    raise PackageError("Archive entry size verification failed.")
                if entry.get("sha256") != _sha256(payload):
                    raise PackageError("Archive entry hash verification failed.")
                _scan_payload(name, payload)
            return manifest
    except BadZipFile as exc:
        raise PackageError("Release archive is not a valid ZIP file.") from exc


def create_release_archive(
    root: Path,
    archive_path: Path,
    receipt_path: Path,
    *,
    dry_run: bool = False,
    created_at: str | None = None,
    force: bool = False,
) -> dict[str, object]:
    selected_root = root.resolve(strict=True)
    selected_archive = archive_path.resolve()
    selected_receipt = receipt_path.resolve()
    if selected_archive == selected_receipt:
        raise PackageError("Archive and receipt paths must be different.")
    if not force and (selected_archive.exists() or selected_receipt.exists()):
        raise PackageError("Release output already exists; review it or use --force.")

    manifest, payloads = _content_manifest(selected_root)
    if dry_run:
        return manifest

    selected_archive.parent.mkdir(parents=True, exist_ok=True)
    selected_receipt.parent.mkdir(parents=True, exist_ok=True)
    archive_temp = selected_archive.with_name(f".{selected_archive.name}.tmp")
    receipt_temp = selected_receipt.with_name(f".{selected_receipt.name}.tmp")
    if archive_temp.exists() or receipt_temp.exists():
        raise PackageError("A temporary release output already exists; review is required.")

    manifest_bytes = _json_bytes(manifest, pretty=True)
    try:
        with ZipFile(
            archive_temp,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, payload in payloads:
                archive.writestr(_zip_info(relative), payload)
            archive.writestr(_zip_info(CONTENT_MANIFEST_NAME), manifest_bytes)
        verified = verify_release_archive(archive_temp)
        if verified != manifest:
            raise PackageError("Written archive verification returned a different manifest.")
        archive_payload = archive_temp.read_bytes()
        receipt: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            "root": "<project-root>",
            "scope": manifest["scope"],
            "file_count": manifest["file_count"],
            "content_set_sha256": manifest["content_set_sha256"],
            "content_manifest_sha256": _sha256(manifest_bytes),
            "archive_name": selected_archive.name,
            "archive_sha256": _sha256(archive_payload),
            "archive_size_bytes": len(archive_payload),
            "excluded_scopes": list(EXCLUDED_SCOPE_LABELS),
            "verification": "archive reopened; safe names, manifest, privacy scan and every file hash matched",
        }
        receipt_temp.write_bytes(_json_bytes(receipt, pretty=True))
        archive_temp.replace(selected_archive)
        receipt_temp.replace(selected_receipt)
        return receipt
    except Exception:
        archive_temp.unlink(missing_ok=True)
        receipt_temp.unlink(missing_ok=True)
        raise


def create_zip() -> dict[str, object]:
    root = Path.cwd()
    archive_path = root / "AntiGravity2_Clean.zip"
    receipt_path = root / "AntiGravity2_Clean.receipt.json"
    receipt = create_release_archive(root, archive_path, receipt_path)
    print(f"Created {archive_path.name} with {receipt['file_count']} allowlisted files.")
    print(f"SHA-256: {receipt['archive_sha256']}")
    return receipt


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a deterministic, allowlisted and privacy-scanned release archive."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.root.resolve(strict=True)
    output = (args.output or root / "AntiGravity2_Clean.zip").resolve()
    receipt = (args.receipt or root / "AntiGravity2_Clean.receipt.json").resolve()
    result = create_release_archive(
        root,
        output,
        receipt,
        dry_run=bool(args.dry_run),
        force=bool(args.force),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "dry-run" if args.dry_run else "write",
                "archive": output.name,
                "receipt": receipt.name,
                "file_count": result["file_count"],
                "content_set_sha256": result["content_set_sha256"],
                "archive_sha256": result.get("archive_sha256"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
