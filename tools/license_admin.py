"""Private operator tool for generating keys and issuing offline licenses.

This file and every private key are deliberately excluded from customer release
artifacts.  Production keys should use encrypted PKCS8 storage and an offline
backup controlled by the software owner.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from eitaa_bridge.licensing import decode_request_code, issue_activation_code


def _public_identity(private_key: Ed25519PrivateKey) -> tuple[str, bytes]:
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "eb-" + hashlib.sha256(public).hexdigest()[:16], public


def _write_private_key(path: Path, private_key: Ed25519PrivateKey, *, unencrypted: bool) -> None:
    if path.exists():
        raise RuntimeError("Private key output already exists; refusing to overwrite it.")
    if unencrypted:
        encryption: serialization.KeySerializationEncryption = serialization.NoEncryption()
    else:
        first = getpass.getpass("Private-key passphrase: ").encode("utf-8")
        second = getpass.getpass("Repeat passphrase: ").encode("utf-8")
        if len(first) < 14 or first != second:
            raise RuntimeError("Passphrases must match and contain at least 14 characters.")
        encryption = serialization.BestAvailableEncryption(first)
    payload = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    password: bytes | None = None
    if b"ENCRYPTED PRIVATE KEY" in raw:
        password = getpass.getpass("Private-key passphrase: ").encode("utf-8")
    loaded = serialization.load_pem_private_key(raw, password=password)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise RuntimeError("The supplied key is not an Ed25519 private key.")
    return loaded


def _keygen(args: argparse.Namespace) -> int:
    private_key = Ed25519PrivateKey.generate()
    _write_private_key(args.private_key, private_key, unencrypted=args.unencrypted_development_key)
    key_id, public = _public_identity(private_key)
    public_record = {
        "format": "eitaa-bridge-license-public-key-v1",
        "key_id": key_id,
        "public_key_base64": base64.b64encode(public).decode("ascii"),
    }
    if args.public_record.exists():
        raise RuntimeError("Public record output already exists; refusing to overwrite it.")
    args.public_record.parent.mkdir(parents=True, exist_ok=True)
    args.public_record.write_text(
        json.dumps(public_record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(public_record, ensure_ascii=False, indent=2))
    return 0


def _issue(args: argparse.Namespace) -> int:
    private_key = _load_private_key(args.private_key)
    key_id, _ = _public_identity(private_key)
    request_code = args.request_code_file.read_text(encoding="utf-8-sig").strip()
    request = decode_request_code(request_code)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = now + timedelta(days=args.valid_days) if args.valid_days else None
    activation_code = issue_activation_code(
        request_code,
        private_key=private_key,
        key_id=key_id,
        issued_at=now,
        expires_at=expires_at,
        customer_reference=args.customer_reference,
        edition=args.edition,
    )
    if args.output.exists():
        raise RuntimeError("Activation output already exists; refusing to overwrite it.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(activation_code + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.output),
                "key_id": key_id,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Issue offline Eitaa Bridge activation codes.")
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen")
    keygen.add_argument("--private-key", type=Path, required=True)
    keygen.add_argument("--public-record", type=Path, required=True)
    keygen.add_argument(
        "--unencrypted-development-key",
        action="store_true",
        help="Only for a disposable branch-test key stored outside release artifacts.",
    )
    keygen.set_defaults(handler=_keygen)

    issue = commands.add_parser("issue")
    issue.add_argument("--private-key", type=Path, required=True)
    issue.add_argument("--request-code-file", type=Path, required=True)
    issue.add_argument("--output", type=Path, required=True)
    issue.add_argument("--customer-reference")
    issue.add_argument("--edition", default="standard")
    issue.add_argument("--valid-days", type=int)
    issue.set_defaults(handler=_issue)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "valid_days", None) is not None and not 1 <= args.valid_days <= 3650:
        print("valid-days must be between 1 and 3650", file=sys.stderr)
        return 2
    try:
        return int(args.handler(args))
    except Exception as exc:
        print(f"license-admin: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
