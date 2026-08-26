from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


FONT_FILES = (
    "IRANSansWeb-Regular.woff2",
    "IRANSansWeb-Bold.woff2",
)


def sync_ui_fonts(root: Path) -> dict[str, object]:
    root = root.resolve()
    source = root / "ui" / "fonts"
    dist = root / "ui" / "dist"
    destination = dist / "fonts"
    status_path = root / "runtime" / "font-status.json"

    if not (dist / "index.html").is_file():
        result: dict[str, object] = {
            "status": "ui_dist_missing",
            "ready": False,
            "copied": [],
            "available": [],
            "missing": list(FONT_FILES),
            "fallback": ["Tahoma", "Segoe UI", "sans-serif"],
        }
    else:
        copied: list[str] = []
        destination.mkdir(parents=True, exist_ok=True)
        for name in FONT_FILES:
            source_file = source / name
            if not source_file.is_file() or source_file.stat().st_size < 1:
                continue
            target_file = destination / name
            if not target_file.is_file() or target_file.read_bytes() != source_file.read_bytes():
                shutil.copy2(source_file, target_file)
            copied.append(name)

        available = [
            name
            for name in FONT_FILES
            if (destination / name).is_file() and (destination / name).stat().st_size > 0
        ]
        missing = [name for name in FONT_FILES if name not in available]
        result = {
            "status": "iransans_ready" if not missing else "fallback_active",
            "ready": not missing,
            "copied": copied,
            "available": available,
            "missing": missing,
            "fallback": ["Tahoma", "Segoe UI", "sans-serif"],
        }

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy optional licensed IRANSans files into the prebuilt UI without Node.js."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = sync_ui_fonts(args.root)
    if not args.quiet:
        if result["status"] == "ui_dist_missing":
            print("Prebuilt ui/dist was not found; build the UI before syncing fonts.")
        elif result["ready"]:
            print("Optional licensed IRANSans Regular and Bold fonts are ready in ui/dist/fonts.")
        else:
            print("Optional IRANSans files are incomplete; Tahoma and Segoe UI fallbacks remain active.")
        print(f"Font status: {args.root / 'runtime' / 'font-status.json'}")
    return 2 if result["status"] == "ui_dist_missing" else 0


if __name__ == "__main__":
    raise SystemExit(main())
