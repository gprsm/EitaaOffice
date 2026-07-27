"""Compare frozen assets directly against the signed clean GMI3 base ZIP."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE_ZIP = ROOT.parents[1] / "MVP6_1_1_GMI3" / "artifacts" / "eitaa_bridge_v0_7_ui_mvp6_1_1_gmi3_index_contacts_lab_WORKING.zip"
PREFIXES = (
    "runtime/",
    "installer/",
    "src/eitaa_bridge/infrastructure/wordpress/",
)
EXACT = {
    "vendor/eitaa_core-0.6.0.dev19-py3-none-any.whl",
    "src/eitaa_bridge/application/scheduler.py",
    "src/eitaa_bridge/facade.py",
    "src/eitaa_bridge/application/doctor.py",
    "src/eitaa_bridge/infrastructure/composition_manifest.py",
    "src/eitaa_bridge/infrastructure/composition_store.py",
    "ui/src/lib/scrollMath.ts",
    "ui/scripts/run-scroll-tests.mjs",
}


def selected(name: str) -> bool:
    return name in EXACT or any(name.startswith(prefix) for prefix in PREFIXES)


with zipfile.ZipFile(BASE_ZIP) as archive:
    names = [name for name in archive.namelist() if not name.endswith("/")]
    root_prefix = names[0].split("/", 1)[0] + "/"
    frozen = {
        name[len(root_prefix) :]: archive.read(name)
        for name in names
        if name.startswith(root_prefix) and selected(name[len(root_prefix) :])
    }

mismatches: list[str] = []
missing: list[str] = []
for relative, baseline in sorted(frozen.items()):
    current = ROOT / relative
    if not current.is_file():
        missing.append(relative)
    elif sha256(current.read_bytes()).digest() != sha256(baseline).digest():
        mismatches.append(relative)

print(f"FROZEN_FILES={len(frozen)}")
print(f"MISMATCHES={len(mismatches)}")
print(f"MISSING={len(missing)}")
for item in mismatches:
    print(f"CHANGED {item}")
for item in missing:
    print(f"MISSING {item}")
sys.exit(1 if mismatches or missing else 0)
