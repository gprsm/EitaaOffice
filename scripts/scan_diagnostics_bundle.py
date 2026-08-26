"""Verify a diagnostics ZIP without echoing any bundled value."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FULL_PHONE = re.compile(
    r"(?<!\d)(?:\+[1-9]\d{7,14}|00[1-9]\d{7,14}|09\d{9})(?!\d)"
)
EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
)
BEARER_VALUE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
WINDOWS_USER_PATH = re.compile(
    r"(?i)\b[A-Z]:[\\/]+Users[\\/]+(?!<redacted-user>)[^\\/\s\"']+"
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:password|application_password|authorization|cookie|ciphertext|imei|otp|secret|token)"
    r"\s*[\"']?\s*[:=]\s*(?P<value>\"[^\"]*\"|'[^']*'|[^\s,}]+)"
)
FORBIDDEN_MEMBER_PARTS = {
    ".env",
    ".eitaa_session.json",
    "session.json",
    "session.bin",
}
FORBIDDEN_MEMBER_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".bin", ".jpg", ".jpeg", ".png", ".webp"}
MAX_MEMBER_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def _finding(findings: list[dict[str, str]], member: str, kind: str) -> None:
    member_ref = (
        "archive"
        if member == "<archive>"
        else "member-" + hashlib.sha256(member.encode("utf-8", errors="replace")).hexdigest()[:12]
    )
    item = {"member": member_ref, "kind": kind}
    if item not in findings:
        findings.append(item)


def _has_unredacted_secret_assignment(text: str) -> bool:
    safe_values = {
        "",
        "<redacted>",
        "[redacted]",
        "true",
        "false",
        "null",
        "none",
    }
    for match in SECRET_ASSIGNMENT.finditer(text):
        value = match.group("value").strip().strip("\"'").strip().casefold()
        if value.startswith("<redacted") and value.endswith(">"):
            continue
        if value not in safe_values:
            return True
    return False


def scan_bundle(path: Path) -> dict[str, object]:
    selected = path.expanduser().resolve()
    findings: list[dict[str, str]] = []
    member_count = 0
    total_bytes = 0
    try:
        archive = ZipFile(selected, "r")
    except (OSError, BadZipFile):
        return {
            "format": "eitaa-bridge-diagnostics-scan-v1",
            "verified": False,
            "archive_name": "diagnostics.zip",
            "member_count": 0,
            "total_bytes": 0,
            "finding_count": 1,
            "findings": [{"member": "archive", "kind": "archive_unreadable"}],
        }
    with archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in infos]
        member_count = len(infos)
        total_bytes = sum(int(item.file_size) for item in infos)
        if len(names) != len(set(names)):
            _finding(findings, "<archive>", "duplicate_member")
        if total_bytes > MAX_TOTAL_BYTES:
            _finding(findings, "<archive>", "uncompressed_total_too_large")
        text_by_name: dict[str, bytes] = {}
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                _finding(findings, name, "unsafe_member_path")
                continue
            lowered_parts = {part.casefold() for part in pure.parts}
            if lowered_parts & FORBIDDEN_MEMBER_PARTS:
                _finding(findings, name, "private_state_member")
            if pure.suffix.casefold() in FORBIDDEN_MEMBER_SUFFIXES:
                _finding(findings, name, "binary_or_database_member")
            if info.file_size > MAX_MEMBER_BYTES:
                _finding(findings, name, "member_too_large")
                continue
            data = archive.read(info)
            text_by_name[name] = data
            try:
                text = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                _finding(findings, name, "non_utf8_member")
                continue
            if FULL_PHONE.search(text):
                _finding(findings, name, "full_phone")
            if EMAIL.search(text):
                _finding(findings, name, "email_address")
            if BEARER_VALUE.search(text):
                _finding(findings, name, "bearer_value")
            if WINDOWS_USER_PATH.search(text):
                _finding(findings, name, "windows_user_path")
            if _has_unredacted_secret_assignment(text):
                _finding(findings, name, "unredacted_secret_assignment")
            if pure.suffix.casefold() == ".json":
                try:
                    json.loads(text)
                except json.JSONDecodeError:
                    _finding(findings, name, "invalid_json")
            elif pure.suffix.casefold() == ".jsonl":
                try:
                    for line in text.splitlines():
                        if line.strip():
                            json.loads(line)
                except json.JSONDecodeError:
                    _finding(findings, name, "invalid_jsonl")

        required = {"system.json", "bridge.redacted.json", "doctor.txt", "README.txt", "manifest.json"}
        for name in sorted(required.difference(names)):
            _finding(findings, name, "required_member_missing")
        try:
            manifest = json.loads(text_by_name["manifest.json"].decode("utf-8"))
            entries = manifest["entries"]
            expected = {
                str(item["name"]): (int(item["size"]), str(item["sha256"]))
                for item in entries
            }
            if set(expected) != set(names).difference({"manifest.json"}):
                _finding(findings, "manifest.json", "manifest_membership_mismatch")
            for name, (size, checksum) in expected.items():
                data = text_by_name.get(name)
                if data is None or len(data) != size or hashlib.sha256(data).hexdigest() != checksum:
                    _finding(findings, "manifest.json", "manifest_digest_mismatch")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            _finding(findings, "manifest.json", "manifest_invalid")
    return {
        "format": "eitaa-bridge-diagnostics-scan-v1",
        "verified": not findings,
        "archive_name": "diagnostics.zip",
        "member_count": member_count,
        "total_bytes": total_bytes,
        "finding_count": len(findings),
        "findings": sorted(findings, key=lambda item: (item["member"], item["kind"])),
    }


def main() -> int:
    args = parse_args()
    result = scan_bundle(args.bundle)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        report = args.report.expanduser().resolve()
        allowed = (ROOT / "backups" / "phase10-rollout").resolve()
        if report.parent != allowed:
            raise ValueError("Report must be written directly in backups/phase10-rollout.")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
