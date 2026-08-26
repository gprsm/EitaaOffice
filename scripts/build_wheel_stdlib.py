"""Build the pure-Python bridge wheel without network or build backends."""

from __future__ import annotations

import argparse
import base64
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import tomllib
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


FIXED_ZIP_TIME = (2026, 8, 26, 0, 0, 0)
PACKAGE_SUFFIXES = frozenset({".py", ".pyi", ".typed"})
QUARANTINED_PACKAGE_PREFIXES = (
    "eitaa_bridge/application/bale_client/",
)


class WheelBuildError(RuntimeError):
    pass


def digest(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(sha256(content).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def _read_project(root: Path) -> dict[str, Any]:
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = payload.get("project")
    if not isinstance(project, dict):
        raise WheelBuildError("pyproject.toml has no project table.")
    return project


def _metadata(project: dict[str, Any]) -> bytes:
    name = str(project["name"])
    version = str(project["version"])
    description = str(project.get("description", ""))
    requires_python = str(project.get("requires-python", ">=3.11"))
    license_value = project.get("license", "LicenseRef-Proprietary")
    if isinstance(license_value, dict):
        license_value = license_value.get("text", "LicenseRef-Proprietary")
    authors = project.get("authors", [])
    author = ""
    if isinstance(authors, list) and authors and isinstance(authors[0], dict):
        author = str(authors[0].get("name", ""))
    lines = [
        "Metadata-Version: 2.4",
        f"Name: {name}",
        f"Version: {version}",
        f"Summary: {description}",
        f"Author: {author}",
        f"License: {license_value}",
        f"Requires-Python: {requires_python}",
    ]
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise WheelBuildError("Project dependencies must be a list.")
    lines.extend(f"Requires-Dist: {dependency}" for dependency in dependencies)
    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        raise WheelBuildError("Optional dependencies must be a table.")
    for extra in sorted(optional):
        values = optional[extra]
        if not isinstance(values, list):
            raise WheelBuildError("Optional dependency values must be lists.")
        lines.append(f"Provides-Extra: {extra}")
        lines.extend(f'Requires-Dist: {value}; extra == "{extra}"' for value in values)
    return ("\n".join(lines) + "\n\n").encode("utf-8")


def _entry_points(project: dict[str, Any]) -> bytes:
    scripts = project.get("scripts", {})
    if not isinstance(scripts, dict) or not scripts:
        raise WheelBuildError("Project scripts table is empty or invalid.")
    lines = ["[console_scripts]"]
    lines.extend(f"{name} = {scripts[name]}" for name in sorted(scripts))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_wheel(root: Path, output_dir: Path, *, force: bool = False) -> Path:
    selected_root = root.resolve(strict=True)
    project = _read_project(selected_root)
    name = str(project["name"])
    version = str(project["version"])
    normalized_name = name.replace("-", "_")
    dist_info = f"{normalized_name}-{version}.dist-info"
    output = output_dir.resolve() / f"{normalized_name}-{version}-py3-none-any.whl"
    if output.exists() and not force:
        raise WheelBuildError("Wheel output already exists; review it or use --force.")

    package_root = selected_root / "src" / "eitaa_bridge"
    files: dict[str, bytes] = {}
    for path in sorted(package_root.rglob("*")):
        if path.is_symlink():
            raise WheelBuildError("Symlinks are not allowed in wheel source.")
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in PACKAGE_SUFFIXES:
            continue
        archive_name = path.relative_to(selected_root / "src").as_posix()
        if archive_name.startswith(QUARANTINED_PACKAGE_PREFIXES):
            continue
        files[archive_name] = path.read_bytes()
    if not files:
        raise WheelBuildError("Bridge package source is empty.")

    files[f"{dist_info}/METADATA"] = _metadata(project)
    files[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: eitaa-bridge-stdlib-wheel\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n\n"
    ).encode("utf-8")
    files[f"{dist_info}/entry_points.txt"] = _entry_points(project)
    files[f"{dist_info}/top_level.txt"] = b"eitaa_bridge\n"

    record_buffer = StringIO()
    writer = csv.writer(record_buffer, lineterminator="\n")
    for archive_name, content in sorted(files.items()):
        writer.writerow((archive_name, digest(content), len(content)))
    writer.writerow((f"{dist_info}/RECORD", "", ""))
    files[f"{dist_info}/RECORD"] = record_buffer.getvalue().encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    if temporary.exists():
        raise WheelBuildError("Temporary wheel output already exists; review is required.")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for archive_name, content in sorted(files.items()):
                archive.writestr(_zip_info(archive_name), content, compresslevel=9)
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.root.resolve(strict=True)
    output_dir = (args.output_dir or root / "dist").resolve()
    output = build_wheel(root, output_dir, force=bool(args.force))
    print(output.name)
    print(f"SHA-256: {sha256(output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
