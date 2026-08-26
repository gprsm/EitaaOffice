from __future__ import annotations

import json
import hashlib
from importlib import util as importlib_util
from pathlib import Path
from types import ModuleType
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts.build_wheel_stdlib import build_wheel

PACKAGE_MODULE_PATH = Path(__file__).resolve().parents[1] / "package_clean.py"


def _load_package_module_for_audit() -> ModuleType:
    raw = PACKAGE_MODULE_PATH.read_bytes()
    if b"\x00" in raw:
        source = raw.decode("utf-16")
        module = ModuleType("package_clean_audit")
        module.__file__ = str(PACKAGE_MODULE_PATH)
        exec(compile(source, str(PACKAGE_MODULE_PATH), "exec"), module.__dict__)
        return module
    spec = importlib_util.spec_from_file_location("package_clean_audit", PACKAGE_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package_clean = _load_package_module_for_audit()


def _write(root: Path, relative: str, content: str = "safe\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_release_tree(root: Path) -> set[str]:
    files = {
        "VERSION.txt": "0.7.0\n",
        "README.md": "# Safe release\n",
        ".env.example": "EITAA_API_ID=replace-me\n",
        "bridge.example.json": "{}\n",
        "pyproject.toml": "[project]\nname='example'\n",
        "requirements.txt": "requests>=2\n",
        "setup_venv.bat": "@echo off\n",
        "src/eitaa_bridge/__init__.py": "__version__='test'\n",
        "ui/src/App.tsx": "export const App = () => null;\n",
        "ui/package.json": '{"name":"safe"}\n',
        "scripts/check_runtime_environment.py": "print('safe')\n",
        "installer/EitaaBridge.iss": "[Setup]\n",
        "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl": "bridge-wheel\n",
        "vendor/eitaa_core-0.6.0.dev19-py3-none-any.whl": "core-wheel\n",
        "vendor/runtime/requests-2.34.2-py3-none-any.whl": "requests-wheel\n",
    }
    for relative, content in files.items():
        _write(root, relative, content)
    with ZipFile(
        root / "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl",
        "w",
        compression=ZIP_DEFLATED,
    ) as wheel:
        wheel.writestr(
            "eitaa_bridge/__init__.py",
            (root / "src/eitaa_bridge/__init__.py").read_bytes(),
        )
    return set(files)


def test_package_module_is_utf8_importable_without_null_bytes() -> None:
    raw = PACKAGE_MODULE_PATH.read_bytes()
    has_null_bytes = b"\x00" in raw
    assert not has_null_bytes, "package_clean.py must be UTF-8 Python without NUL bytes"
    source = raw.decode("utf-8")
    compile(source, str(PACKAGE_MODULE_PATH), "exec")


def test_legacy_packager_demonstrates_blacklist_leak_on_synthetic_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(tmp_path, "README.md")
    _write(tmp_path, "src/eitaa_bridge/app.py")
    _write(tmp_path, "prompt_out.txt", "synthetic scratch output\n")
    _write(tmp_path, "probe.json", "{}\n")
    monkeypatch.chdir(tmp_path)

    package_clean.create_zip()

    with ZipFile(tmp_path / "AntiGravity2_Clean.zip") as archive:
        names = set(archive.namelist())
    assert "README.md" in names
    assert "src/eitaa_bridge/app.py" in names
    assert "prompt_out.txt" not in names
    assert "probe.json" not in names


def test_release_collection_is_allowlisted_and_excludes_private_or_scratch_state(
    tmp_path: Path,
) -> None:
    included = _minimal_release_tree(tmp_path)
    excluded = {
        ".env",
        "bridge.json",
        "prompt_out.txt",
        "probe.json",
        "Bale/private_client.py",
        "scripts/scratch_fix.py",
        "src/eitaa_bridge/application/bale_client/private.py",
        "data/coordinator.sqlite3",
        "runtime/app.jsonl",
        "diagnostics/bundle.json",
        "backups/runtime.zip",
        ".codex_work/state.json",
        ".pytest-work/nodeids",
        "src/eitaa_bridge/__pycache__/app.pyc",
        "eitaa_bridge.egg-info/PKG-INFO",
    }
    for relative in excluded:
        _write(tmp_path, relative)

    selected = {
        path.relative_to(tmp_path).as_posix()
        for path in package_clean.collect_release_files(tmp_path)
    }

    assert included <= selected
    assert excluded.isdisjoint(selected)


def test_release_dry_run_is_write_free_and_archive_is_deterministic(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    _minimal_release_tree(root)
    dry_archive = tmp_path / "dry.zip"
    dry_receipt = tmp_path / "dry.receipt.json"

    dry_manifest = package_clean.create_release_archive(
        root,
        dry_archive,
        dry_receipt,
        dry_run=True,
        created_at="2026-08-26T00:00:00+03:30",
    )

    assert dry_manifest["file_count"] >= 15
    assert not dry_archive.exists()
    assert not dry_receipt.exists()

    first_archive = tmp_path / "first.zip"
    first_receipt = tmp_path / "first.receipt.json"
    second_archive = tmp_path / "second.zip"
    second_receipt = tmp_path / "second.receipt.json"
    package_clean.create_release_archive(
        root,
        first_archive,
        first_receipt,
        created_at="2026-08-26T00:00:00+03:30",
    )
    package_clean.create_release_archive(
        root,
        second_archive,
        second_receipt,
        created_at="2026-08-26T00:00:00+03:30",
    )

    assert first_archive.read_bytes() == second_archive.read_bytes()
    verified = package_clean.verify_release_archive(first_archive)
    assert verified["file_count"] == dry_manifest["file_count"]
    assert json.loads(first_receipt.read_text(encoding="utf-8"))["archive_sha256"]


def test_release_privacy_scan_rejects_secret_content_without_echoing_it(
    tmp_path: Path,
) -> None:
    _minimal_release_tree(tmp_path)
    secret = "synthetic-private-material-must-not-be-echoed"
    _write(
        tmp_path,
        "src/eitaa_bridge/unsafe.py",
        f"-----BEGIN PRIVATE KEY-----\n{secret}\n-----END PRIVATE KEY-----\n",
    )

    with pytest.raises(package_clean.PackageError) as exc_info:
        package_clean.create_release_archive(
            tmp_path,
            tmp_path / "unsafe.zip",
            tmp_path / "unsafe.json",
        )

    assert secret not in str(exc_info.value)
    assert not (tmp_path / "unsafe.zip").exists()
    assert not (tmp_path / "unsafe.json").exists()


@pytest.mark.parametrize("unsafe_name", ["../escape.py", "/absolute.py", "dir\\escape.py"])
def test_archive_verifier_rejects_traversal_and_noncanonical_names(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    archive_path = tmp_path / "unsafe.zip"
    manifest = {
        "schema_version": 1,
        "file_count": 1,
        "files": [{"path": unsafe_name, "sha256": "0" * 64, "size_bytes": 1}],
    }
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(unsafe_name, b"x")
        archive.writestr(
            "_release/CONTENT_MANIFEST.json",
            json.dumps(manifest).encode("utf-8"),
        )

    with pytest.raises(package_clean.PackageError):
        package_clean.verify_release_archive(archive_path)


def test_archive_verifier_rejects_case_insensitive_name_collision(tmp_path: Path) -> None:
    archive_path = tmp_path / "collision.zip"
    entries = [
        {"path": "src/App.py", "sha256": hashlib.sha256(b"a").hexdigest(), "size_bytes": 1},
        {"path": "src/app.py", "sha256": hashlib.sha256(b"b").hexdigest(), "size_bytes": 1},
    ]
    manifest = {"schema_version": 1, "file_count": 2, "files": entries}
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("src/App.py", b"a")
        archive.writestr("src/app.py", b"b")
        archive.writestr(
            "_release/CONTENT_MANIFEST.json",
            json.dumps(manifest).encode("utf-8"),
        )

    with pytest.raises(package_clean.PackageError):
        package_clean.verify_release_archive(archive_path)


def test_archive_verifier_rejects_entry_hash_tamper(tmp_path: Path) -> None:
    archive_path = tmp_path / "tampered.zip"
    manifest = {
        "schema_version": 1,
        "file_count": 1,
        "files": [{"path": "src/app.py", "sha256": "0" * 64, "size_bytes": 4}],
    }
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("src/app.py", b"safe")
        archive.writestr(
            "_release/CONTENT_MANIFEST.json",
            json.dumps(manifest).encode("utf-8"),
        )

    with pytest.raises(package_clean.PackageError):
        package_clean.verify_release_archive(archive_path)


def test_existing_output_is_not_overwritten_without_force(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _minimal_release_tree(root)
    archive_path = tmp_path / "existing.zip"
    receipt_path = tmp_path / "existing.json"
    sentinel = b"existing-output-must-survive"
    archive_path.write_bytes(sentinel)

    with pytest.raises(package_clean.PackageError):
        package_clean.create_release_archive(root, archive_path, receipt_path)

    assert archive_path.read_bytes() == sentinel
    assert not receipt_path.exists()
    assert not (tmp_path / ".existing.zip.tmp").exists()
    assert not (tmp_path / ".existing.json.tmp").exists()


def test_bridge_wheel_parity_rejects_stale_or_missing_source(tmp_path: Path) -> None:
    _minimal_release_tree(tmp_path)
    wheel_path = tmp_path / "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
    with ZipFile(wheel_path, "w", compression=ZIP_DEFLATED) as wheel:
        wheel.writestr("eitaa_bridge/__init__.py", b"__version__='stale'\n")

    with pytest.raises(package_clean.PackageError):
        package_clean.verify_bridge_wheel_source_parity(tmp_path, wheel_path)


def test_bundled_bridge_wheel_matches_current_source_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    wheel_path = root / "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl"

    result = package_clean.verify_bridge_wheel_source_parity(root, wheel_path)

    assert result["source_file_count"] > 0
    assert result["missing"] == 0
    assert result["mismatched"] == 0
    assert result["extra"] == 0


def test_release_excludes_quarantined_bale_client_but_keeps_fail_closed_slot() -> None:
    root = Path(__file__).resolve().parents[1]
    selected = {
        path.relative_to(root).as_posix()
        for path in package_clean.collect_release_files(root)
    }

    assert "src/eitaa_bridge/providers/bale/slot.py" in selected
    assert not any(
        name.startswith("src/eitaa_bridge/application/bale_client/")
        for name in selected
    )

    wheel_path = root / "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
    with ZipFile(wheel_path) as wheel:
        names = wheel.namelist()
        metadata = wheel.read("eitaa_bridge-0.7.0.dev31.dist-info/METADATA")
    assert "eitaa_bridge/providers/bale/slot.py" in names
    assert not any(name.startswith("eitaa_bridge/application/bale_client/") for name in names)
    assert b"Requires-Dist: httpx" not in metadata
    assert b"Requires-Dist: websockets" not in metadata
    assert b"Requires-Dist: cryptography" not in metadata


def test_stdlib_wheel_builder_is_deterministic_and_uses_canonical_contract(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    first = build_wheel(root, tmp_path / "first")
    second = build_wheel(root, tmp_path / "second")

    assert first.read_bytes() == second.read_bytes()
    parity = package_clean.verify_bridge_wheel_source_parity(root, first)
    assert parity["missing"] == parity["mismatched"] == parity["extra"] == 0

    with ZipFile(first) as wheel:
        names = wheel.namelist()
        metadata = wheel.read("eitaa_bridge-0.7.0.dev31.dist-info/METADATA")
        entry_points = wheel.read("eitaa_bridge-0.7.0.dev31.dist-info/entry_points.txt")
    assert "eitaa_bridge/providers/bale/slot.py" in names
    assert not any(name.startswith("eitaa_bridge/application/bale_client/") for name in names)
    assert metadata.count(b"Requires-Dist:") == 3
    assert b"Requires-Dist: eitaa-core==0.6.0.dev19" in metadata
    assert b"Requires-Dist: requests>=2.31,<3" in metadata
    assert b"Provides-Extra: dev" in metadata
    assert entry_points.count(b" = eitaa_bridge.") == 4
