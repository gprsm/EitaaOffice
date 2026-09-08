from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


PRIVATE_KEY_PEM = re.compile(
    rb"-----BEGIN (?P<kind>(?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----"
    rb"[\r\n]+[A-Za-z0-9+/=:\-, \r\n]{64,}"
    rb"-----END (?P=kind)-----",
    re.IGNORECASE,
)
PRIVATE_KEY_NAME = re.compile(
    r"(?i)(?:private|signing)[-_ .]{0,8}key|\.(?:pfx|p12)$"
)
FORBIDDEN_ROOTS = frozenset(
    {"data", "runtime", "diagnostics", "backups", "catalog"}
)
FORBIDDEN_FILES = frozenset(
    {
        "bridge.json",
        ".env",
        ".eitaa_session.json",
        "composition.json",
        "transfer-backup.zip",
    }
)


def inspect_payload(root: Path) -> dict[str, object]:
    selected = root.resolve(strict=True)
    if not selected.is_dir() or selected.is_symlink():
        raise ValueError("Office payload root must be a regular directory.")
    file_count = 0
    operational: list[str] = []
    private_key_names: list[str] = []
    private_key_pem: list[str] = []
    for path in selected.rglob("*"):
        if path.is_symlink():
            raise ValueError("Office payload must not contain symlinks.")
        if not path.is_file():
            continue
        file_count += 1
        relative = path.relative_to(selected).as_posix()
        parts = tuple(part.casefold() for part in path.relative_to(selected).parts)
        if (parts and parts[0] in FORBIDDEN_ROOTS) or path.name.casefold() in FORBIDDEN_FILES:
            operational.append(relative)
        if PRIVATE_KEY_NAME.search(path.name):
            private_key_names.append(relative)
        if PRIVATE_KEY_PEM.search(path.read_bytes()):
            private_key_pem.append(relative)
    return {
        "ok": not (operational or private_key_names or private_key_pem),
        "file_count": file_count,
        "operational_findings": len(operational),
        "private_key_name_findings": len(private_key_names),
        "private_key_pem_findings": len(private_key_pem),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed on private Office payload state.")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    result = inspect_payload(args.root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
