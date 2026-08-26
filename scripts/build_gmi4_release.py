"""Generate review artifacts and privacy-clean GMI4 ZIPs from the signed GMI3 base."""

from __future__ import annotations

import difflib
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
GMI4_ROOT = ROOT.parent
ARTIFACTS = GMI4_ROOT / "artifacts"
GMI_REPORTS = ROOT / "docs" / "reports" / "gmi"
GMI_REVIEW_ARTIFACTS = GMI_REPORTS / "artifacts"
GMI4_CHANGED_FILES = GMI_REVIEW_ARTIFACTS / "GMI4_CHANGED_FILES.json"
GMI4_UNIFIED_DIFF = GMI_REVIEW_ARTIFACTS / "GMI4_UNIFIED.diff"
BASE_ZIP = ROOT.parents[1] / "MVP6_1_1_GMI3" / "artifacts" / "eitaa_bridge_v0_7_ui_mvp6_1_1_gmi3_index_contacts_lab_WORKING.zip"
PACKAGE_ROOT = "eitaa_bridge_v0_7_ui_mvp6_1_1_gmi4_contact_sources_handoff"
WORKING_ZIP = ARTIFACTS / f"{PACKAGE_ROOT}_WORKING.zip"
REVIEW_ZIP = ARTIFACTS / "Eitaa_Bridge_MVP6_1_1_GMI4_REVIEW_BUNDLE.zip"
SUMS = ARTIFACTS / "GMI4_SHA256SUMS.txt"

GENERATED_COMPARE_EXCLUSIONS = {
    "CHECKSUMS.sha256",
    "docs/reports/gmi/artifacts/GMI4_CHANGED_FILES.json",
    "docs/reports/gmi/artifacts/GMI4_UNIFIED.diff",
    "GMI4_SHA256SUMS.txt",
}
EXCLUDED_TOP = {".venv", ".wheel-test", ".git", "node_modules", "artifacts"}
PRIVATE_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".log", ".session"}
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mp3", ".ogg", ".wav"}
TEXT_SUFFIXES = {".py", ".tsx", ".ts", ".css", ".json", ".md", ".txt", ".toml", ".cjs", ".mjs", ".bat", ".vbs"}


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def excluded(relative: str) -> bool:
    path = Path(relative)
    lowered = relative.replace("\\", "/").lower()
    if any(part in EXCLUDED_TOP or part == "__pycache__" for part in path.parts):
        return True
    if path.suffix.lower() == ".pyc":
        return True
    if lowered.startswith("ui/node_modules/"):
        return True
    if lowered.startswith(("data/", "diagnostics/", "runtime/logs/", "runtime/uploads/")) and path.name != ".gitkeep":
        return True
    if path.name == ".env" or ".eitaa_session" in path.name.lower():
        return True
    if relative in {"bridge.json", "bridge.multisite.json", "composition.json"}:
        return True
    if path.suffix.lower() in PRIVATE_SUFFIXES or path.suffix.lower() in MEDIA_SUFFIXES:
        return True
    if lowered.startswith("dist/eitaa_bridge-") and relative != "dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl":
        return True
    return False


def current_files() -> dict[str, Path]:
    return {
        path.relative_to(ROOT).as_posix(): path
        for path in ROOT.rglob("*")
        if path.is_file() and not excluded(path.relative_to(ROOT).as_posix())
    }


with zipfile.ZipFile(BASE_ZIP) as archive:
    base_names = [name for name in archive.namelist() if not name.endswith("/")]
    base_prefix = base_names[0].split("/", 1)[0] + "/"
    base = {
        name[len(base_prefix) :]: archive.read(name)
        for name in base_names
        if name.startswith(base_prefix)
        and not excluded(name[len(base_prefix) :])
        and name[len(base_prefix) :] not in GENERATED_COMPARE_EXCLUSIONS
    }

current = current_files()
compare_current = {
    name: path
    for name, path in current.items()
    if name not in GENERATED_COMPARE_EXCLUSIONS
}
changes: list[dict[str, object]] = []
for name in sorted(set(base) | set(compare_current)):
    baseline = base.get(name)
    path = compare_current.get(name)
    if baseline is None and path is not None:
        changes.append({"path": name, "status": "added", "bytes": path.stat().st_size, "sha256": sha(path)})
    elif path is None:
        changes.append({"path": name, "status": "removed", "bytes": 0, "sha256": None})
    elif sha256(baseline).digest() != sha256(path.read_bytes()).digest():
        changes.append({"path": name, "status": "modified", "bytes": path.stat().st_size, "sha256": sha(path)})

GMI_REVIEW_ARTIFACTS.mkdir(parents=True, exist_ok=True)
GMI4_CHANGED_FILES.write_text(
    json.dumps(
        {
            "base": BASE_ZIP.name,
            "version": "0.7.0-ui-mvp6.1.1-gmi4.2",
            "changed_file_count": len(changes),
            "files": changes,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

diff_parts: list[str] = []
for change in changes:
    name = str(change["path"])
    if name.startswith("GMI4_") or name in {"RELEASE_MANIFEST.json", "CHECKSUMS.sha256"}:
        continue
    suffix = Path(name).suffix.lower()
    if suffix not in TEXT_SUFFIXES:
        diff_parts.append(f"Binary files a/{name} and b/{name} differ\n")
        continue
    before = base.get(name, b"").decode("utf-8", errors="replace").splitlines(keepends=True)
    path = compare_current.get(name)
    after = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if path else []
    diff_parts.extend(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"a/{name}" if before else "/dev/null",
            tofile=f"b/{name}" if after else "/dev/null",
            n=3,
        )
    )
GMI4_UNIFIED_DIFF.write_text("".join(diff_parts), encoding="utf-8")

current = current_files()
checksum_targets = {
    name: path
    for name, path in current.items()
    if name not in {"CHECKSUMS.sha256", "GMI4_SHA256SUMS.txt"}
}
(ROOT / "CHECKSUMS.sha256").write_text(
    "".join(f"{sha(path)}  {name}\n" for name, path in sorted(checksum_targets.items())),
    encoding="utf-8",
)

current = current_files()
forbidden_names = [
    name for name in current
    if Path(name).name == ".env"
    or ".eitaa_session" in Path(name).name.lower()
    or Path(name).suffix.lower() in PRIVATE_SUFFIXES | MEDIA_SUFFIXES
]
private_key_hits = 0
synthetic_phone_hits = 0
private_key = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
iranian_phone = re.compile(rb"(?<!\d)(?:\+98|0098|0)?9\d{9}(?!\d)")
for name, path in current.items():
    if path.stat().st_size > 5 * 1024 * 1024:
        continue
    content = path.read_bytes()
    private_key_hits += len(private_key.findall(content))
    if name.startswith(("tests/", "scripts/gmi4_smoke.py")):
        synthetic_phone_hits += len(iranian_phone.findall(content))

if forbidden_names or private_key_hits:
    raise SystemExit(
        f"Privacy scan failed: forbidden_names={forbidden_names}, private_key_hits={private_key_hits}"
    )

ARTIFACTS.mkdir(parents=True, exist_ok=True)
for target in (WORKING_ZIP, REVIEW_ZIP, SUMS):
    if target.exists():
        target.unlink()

with zipfile.ZipFile(WORKING_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, path in sorted(current.items()):
        if name == "GMI4_SHA256SUMS.txt":
            continue
        archive.write(path, f"{PACKAGE_ROOT}/{name}")

bridge_wheel = ROOT / "dist" / "eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
core_wheel = ROOT / "vendor" / "eitaa_core-0.6.0.dev19-py3-none-any.whl"
SUMS.write_text(
    f"{sha(WORKING_ZIP)}  {WORKING_ZIP.name}\n"
    f"{sha(bridge_wheel)}  {bridge_wheel.name}\n"
    f"{sha(core_wheel)}  {core_wheel.name}\n",
    encoding="utf-8",
)
(ROOT / "GMI4_SHA256SUMS.txt").write_text(SUMS.read_text(encoding="utf-8"), encoding="utf-8")

review_files = [
    (GMI_REPORTS / "GMI4_REVIEW_README.md", "GMI4_REVIEW_README.md"),
    (GMI_REPORTS / "GMI4_ARCHITECTURE_AND_SCOPE.md", "GMI4_ARCHITECTURE_AND_SCOPE.md"),
    (GMI_REPORTS / "GMI4_MIGRATION_REPORT.md", "GMI4_MIGRATION_REPORT.md"),
    (GMI_REPORTS / "GMI4_VALIDATION_REPORT.md", "GMI4_VALIDATION_REPORT.md"),
    (GMI_REPORTS / "GMI4_INVARIANTS_REPORT.md", "GMI4_INVARIANTS_REPORT.md"),
    (GMI_REPORTS / "GMI4_PRIVACY_SCAN.md", "GMI4_PRIVACY_SCAN.md"),
    (ROOT / "docs" / "checklists" / "GMI4_WINDOWS_ACCEPTANCE_CHECKLIST.md", "GMI4_WINDOWS_ACCEPTANCE_CHECKLIST.md"),
    (GMI4_UNIFIED_DIFF, "GMI4_UNIFIED.diff"),
    (GMI4_CHANGED_FILES, "GMI4_CHANGED_FILES.json"),
    (ROOT / "GMI4_SHA256SUMS.txt", "GMI4_SHA256SUMS.txt"),
    (ROOT / "RELEASE_MANIFEST.json", "RELEASE_MANIFEST.json"),
]
with zipfile.ZipFile(REVIEW_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for source, archive_name in review_files:
        archive.write(source, archive_name)

with SUMS.open("a", encoding="utf-8") as handle:
    handle.write(f"{sha(REVIEW_ZIP)}  {REVIEW_ZIP.name}\n")
(ROOT / "GMI4_SHA256SUMS.txt").write_text(SUMS.read_text(encoding="utf-8"), encoding="utf-8")

with zipfile.ZipFile(WORKING_ZIP) as archive:
    packaged_names = archive.namelist()
    packaged_forbidden = [
        name for name in packaged_names
        if "/.venv/" in name
        or "/.wheel-test/" in name
        or "/node_modules/" in name
        or Path(name).name == ".env"
        or ".eitaa_session" in Path(name).name.lower()
        or Path(name).suffix.lower() in PRIVATE_SUFFIXES | MEDIA_SUFFIXES
    ]
if packaged_forbidden:
    raise SystemExit(f"Packaged privacy scan failed: {packaged_forbidden[:10]}")

print(f"CHANGED_FILES={len(changes)}")
print(f"PRIVACY_FORBIDDEN=0")
print(f"PRIVATE_KEY_HITS={private_key_hits}")
print(f"SYNTHETIC_PHONE_FIXTURES={synthetic_phone_hits}")
print(f"WORKING_FILES={len(packaged_names)}")
print(f"WORKING_SHA256={sha(WORKING_ZIP)}")
print(f"REVIEW_SHA256={sha(REVIEW_ZIP)}")
