from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from runtime_state import load_version, manifest_for, project_root, state_entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an Eitaa Bridge runtime-state backup.")
    parser.add_argument("--output", type=Path, help="Output ZIP path or directory.")
    parser.add_argument("--without-media", action="store_true", help="Exclude data/media from the backup.")
    parser.add_argument("--include-logs", action="store_true", help="Include diagnostics and runtime logs.")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def create_backup(
    *,
    output: Path | None = None,
    include_media: bool = True,
    include_logs: bool = False,
    root: Path | None = None,
) -> Path:
    root = (root or project_root()).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    default_dir = root / "backups" / "runtime"
    selected_output = output or default_dir
    if selected_output.suffix.lower() != ".zip":
        selected_output = selected_output / f"eitaa-bridge-backup-{timestamp}.zip"
    selected_output = selected_output.expanduser().resolve()
    selected_output.parent.mkdir(parents=True, exist_ok=True)

    entries = state_entries(root, include_media=include_media, include_logs=include_logs)
    manifest = manifest_for(
        entries,
        product_version=load_version(root),
        include_media=include_media,
        include_logs=include_logs,
    )
    manifest["created_local"] = datetime.now().astimezone().isoformat(timespec="seconds")

    temporary = selected_output.with_suffix(selected_output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for entry in entries:
            archive.write(entry.source, f"state/{entry.archive_name}")
        import json
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(selected_output)
    return selected_output


def main() -> int:
    args = parse_args()
    include_media = not args.without_media
    output = create_backup(
        output=args.output,
        include_media=include_media,
        include_logs=args.include_logs,
    )
    if not args.quiet:
        print(output.name)
        print(f"include_media={include_media} include_logs={args.include_logs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
