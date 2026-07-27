"""Build the pure-Python bridge wheel without downloading build backends."""

from __future__ import annotations

import base64
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.7.0.dev31"
DIST_INFO = f"eitaa_bridge-{VERSION}.dist-info"
OUTPUT = ROOT / "dist" / f"eitaa_bridge-{VERSION}-py3-none-any.whl"


def digest(content: bytes) -> str:
    encoded = base64.urlsafe_b64encode(sha256(content).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


files: dict[str, bytes] = {}
for path in sorted((ROOT / "src" / "eitaa_bridge").rglob("*")):
    if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
        archive_name = path.relative_to(ROOT / "src").as_posix()
        files[archive_name] = path.read_bytes()

files[f"{DIST_INFO}/METADATA"] = f"""Metadata-Version: 2.4
Name: eitaa-bridge
Version: {VERSION}
Summary: Local-first Eitaa-to-WordPress desktop bridge with an explainable index workbench and private contact directory.
Author: Eitaa Unified Project
License: LicenseRef-Proprietary
Requires-Python: >=3.11
Requires-Dist: eitaa-core==0.6.0.dev19
Requires-Dist: requests<3,>=2.31
Provides-Extra: dev
Requires-Dist: pytest<10,>=8; extra == "dev"

""".encode("utf-8")
files[f"{DIST_INFO}/WHEEL"] = b"""Wheel-Version: 1.0
Generator: eitaa-bridge-stdlib-wheel
Root-Is-Purelib: true
Tag: py3-none-any

"""
files[f"{DIST_INFO}/entry_points.txt"] = b"""[console_scripts]
eitaa-bridge = eitaa_bridge.interfaces.cli:main
eitaa-bridge-api = eitaa_bridge.interfaces.http_api:main
"""
files[f"{DIST_INFO}/top_level.txt"] = b"eitaa_bridge\n"

record_buffer = StringIO()
writer = csv.writer(record_buffer, lineterminator="\n")
for name, content in sorted(files.items()):
    writer.writerow((name, digest(content), len(content)))
writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
files[f"{DIST_INFO}/RECORD"] = record_buffer.getvalue().encode("utf-8")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, content in sorted(files.items()):
        info = zipfile.ZipInfo(name, date_time=(2026, 7, 24, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, content, compresslevel=9)

print(OUTPUT.name)
