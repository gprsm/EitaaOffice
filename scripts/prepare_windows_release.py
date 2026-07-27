from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the Windows RC/installer staging directory.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    packaged = root / "ui" / "release" / "EitaaBridge-win32-x64"
    if not (packaged / "EitaaBridge.exe").is_file():
        raise SystemExit("Packaged Electron output is missing. Run ui\\npm run pack:win on Windows first.")

    target = (args.target or root / "release" / "windows" / "EitaaBridge-0.8.0-rc1").resolve()
    if target.exists():
        shutil.rmtree(target)
    copy_tree(packaged, target)
    runtime = target / "bridge-runtime"

    files = [
        "VERSION.txt", "bridge.example.json", ".env.example", "setup_venv.bat",
        "run_doctor.bat", "backup_now.bat", "restore_backup.bat",
        "create_diagnostics.bat", "open_runtime_logs.bat",
    ]
    for relative in files:
        copy_file(root / relative, runtime / relative)
    for relative in ["dist", "vendor", "scripts", "docs"]:
        copy_tree(root / relative, runtime / relative)

    (runtime / "runtime" / "logs").mkdir(parents=True, exist_ok=True)
    (runtime / "backups" / "runtime").mkdir(parents=True, exist_ok=True)
    (runtime / "README-FIRST.txt").write_text(
        "Eitaa Bridge 0.8 RC1 staging package\n"
        "1) Install Python 3.13 x64.\n"
        "2) Run bridge-runtime\\setup_venv.bat.\n"
        "3) Run EitaaBridge.exe.\n"
        "The official Inno Setup installer performs step 2 automatically.\n",
        encoding="utf-8",
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
