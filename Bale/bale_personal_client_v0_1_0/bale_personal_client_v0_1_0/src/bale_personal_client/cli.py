from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .client import BaleClient
from .config import BaleConfig
from .models import FileDetails, Peer, PeerType, SendType


def _passphrase(args: argparse.Namespace, *, required: bool = True) -> str | None:
    value = getattr(args, "passphrase", None) or os.getenv("BALE_VAULT_PASSPHRASE")
    if value or not required:
        return value
    return getpass.getpass("Vault passphrase: ")


def _peer(args: argparse.Namespace) -> Peer:
    return Peer(
        id=int(args.peer_id),
        type=PeerType(int(args.peer_type)),
        access_hash=int(args.access_hash) if args.access_hash is not None else None,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"hex": value.hex(), "length": len(value)}
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _print(value: Any) -> None:
    print(json.dumps(_jsonable(value), ensure_ascii=False, indent=2, default=str))


def _add_session_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--passphrase", help="Vault passphrase; otherwise env BALE_VAULT_PASSPHRASE/prompt")
    parser.add_argument("--vault", default="data/session.vault")


def _add_peer_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--peer-id", required=True, type=int)
    parser.add_argument("--peer-type", type=int, default=1, choices=[1, 2], help="1 private, 2 group")
    parser.add_argument("--access-hash", type=int)


async def _run(args: argparse.Namespace) -> None:
    config = BaleConfig(vault_path=Path(args.vault) if hasattr(args, "vault") else Path("data/session.vault"))
    phrase = _passphrase(args, required=args.command not in {"catalog", "auth-start"})
    async with BaleClient(config, passphrase=phrase) as client:
        command = args.command
        if command == "catalog":
            _print(client.rpc_catalog())
            return
        if command == "auth-start":
            result = await client.auth.start_phone_auth(args.phone)
            _print(result)
            return
        if command == "auth-code":
            outcome = await client.auth_code(
                args.transaction,
                args.code,
                is_registered_hint=not args.unregistered,
            )
            _print({
                "session_saved": outcome.session is not None,
                "password_required": outcome.password_required,
                "signup_required": outcome.signup_required,
                "session": outcome.session,
                "raw_hex": outcome.raw.hex(),
            })
            return
        if command == "auth-password":
            password = args.password or getpass.getpass("Bale two-step password: ")
            _print(await client.auth_password(args.transaction, password))
            return
        if command == "auth-signup":
            _print(await client.auth_signup(args.transaction, args.first_name, args.last_name))
            return
        if command == "exchange-jwt":
            _print(await client.exchange_and_save_jwt(args.jwt))
            return
        if command == "import-token":
            _print(client.import_access_token(args.access_token, jwt=args.jwt))
            return
        if command == "session-show":
            _print(client.load_session())
            return
        if command == "session-clear":
            client.vault.clear()
            _print({"cleared": True})
            return

        client.load_session()
        if command == "connect-test":
            _print(await client.connection_test())
            return
        await client.connect(subscribe=command == "listen")
        try:
            if command == "dialogs":
                _print(await client.load_dialogs(limit=args.limit))
            elif command == "history":
                _print(await client.load_history(_peer(args), limit=args.limit, offset_date=args.offset_date))
            elif command == "send":
                _print(await client.send_text(_peer(args), args.text, silent=args.silent))
            elif command == "edit":
                _print(await client.edit_message(_peer(args), args.message_id, args.text))
            elif command == "delete":
                _print(await client.delete_message(
                    _peer(args), args.message_id, args.date, just_me=args.just_me
                ))
            elif command == "clear-chat":
                _print(await client.clear_chat(_peer(args)))
            elif command == "delete-chat":
                _print(await client.delete_chat(_peer(args)))
            elif command == "send-file":
                send_type = SendType(args.send_type)
                _print(await client.send_file(
                    _peer(args), args.path, caption=args.caption, send_type=send_type,
                    access_hash=args.file_access_hash,
                    progress=lambda n, t: print(f"\r{n}/{t}", end="", flush=True),
                ))
                print()
            elif command == "download-file":
                details = FileDetails(
                    file_id=args.file_id,
                    access_hash=args.file_access_hash,
                    name=Path(args.output).name,
                    size=args.size,
                    mime_type=args.mime,
                )
                _print(await client.download_file(details, args.output))
            elif command == "contacts":
                _print(await client.get_contacts())
            elif command == "search-contact":
                _print(await client.search_contacts(args.query))
            elif command == "add-contact":
                _print(await client.add_contact(args.user_id, args.contact_type))
            elif command == "remove-contact":
                _print(await client.remove_contact(args.user_id, args.contact_type))
            elif command == "typing":
                _print(await client.typing(_peer(args), args.typing_type))
            elif command == "stop-typing":
                _print(await client.stop_typing(_peer(args), args.typing_type))
            elif command == "set-online":
                _print(await client.set_online(not args.offline))
            elif command == "rpc":
                if args.spec_file:
                    spec = json.loads(Path(args.spec_file).read_text(encoding="utf-8"))
                else:
                    spec = json.loads(args.spec or "[]")
                _print(await client.rpc_from_spec(args.service, args.method, spec))
            elif command == "listen":
                loop = asyncio.get_running_loop()
                deadline = loop.time() + args.seconds if args.seconds > 0 else None
                while deadline is None or loop.time() < deadline:
                    try:
                        _print(await client.next_update(timeout=1.0))
                    except asyncio.TimeoutError:
                        pass
            else:
                raise RuntimeError(f"Unknown command: {command}")
        finally:
            await client.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bale-client", description="Bale Personal Client research CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog")

    p = sub.add_parser("auth-start")
    p.add_argument("phone")
    p.add_argument("--vault", default="data/session.vault")

    p = sub.add_parser("auth-code")
    _add_session_args(p)
    p.add_argument("transaction")
    p.add_argument("code")
    p.add_argument("--unregistered", action="store_true")

    p = sub.add_parser("auth-password")
    _add_session_args(p)
    p.add_argument("transaction")
    p.add_argument("--password")

    p = sub.add_parser("auth-signup")
    _add_session_args(p)
    p.add_argument("transaction")
    p.add_argument("first_name")
    p.add_argument("last_name", nargs="?", default="")

    p = sub.add_parser("exchange-jwt")
    _add_session_args(p)
    p.add_argument("jwt")

    p = sub.add_parser("import-token")
    _add_session_args(p)
    p.add_argument("access_token")
    p.add_argument("--jwt")

    for name in ("session-show", "session-clear", "connect-test"):
        p = sub.add_parser(name)
        _add_session_args(p)

    p = sub.add_parser("dialogs")
    _add_session_args(p)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("history")
    _add_session_args(p); _add_peer_args(p)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offset-date", type=int, default=(1 << 63) - 1)

    p = sub.add_parser("send")
    _add_session_args(p); _add_peer_args(p)
    p.add_argument("text")
    p.add_argument("--silent", action="store_true")

    p = sub.add_parser("edit")
    _add_session_args(p); _add_peer_args(p)
    p.add_argument("message_id", type=int)
    p.add_argument("text")

    p = sub.add_parser("delete")
    _add_session_args(p); _add_peer_args(p)
    p.add_argument("--message-id", type=int, action="append", required=True)
    p.add_argument("--date", type=int, action="append", required=True)
    p.add_argument("--just-me", action="store_true")

    for name in ("clear-chat", "delete-chat"):
        p = sub.add_parser(name)
        _add_session_args(p); _add_peer_args(p)

    p = sub.add_parser("send-file")
    _add_session_args(p); _add_peer_args(p)
    p.add_argument("path")
    p.add_argument("--caption")
    p.add_argument("--send-type", type=int, default=int(SendType.DOCUMENT), choices=[e.value for e in SendType])
    p.add_argument("--file-access-hash", type=int)

    p = sub.add_parser("download-file")
    _add_session_args(p)
    p.add_argument("file_id", type=int)
    p.add_argument("file_access_hash", type=int)
    p.add_argument("output")
    p.add_argument("--size", type=int, default=0)
    p.add_argument("--mime", default="application/octet-stream")

    p = sub.add_parser("contacts")
    _add_session_args(p)
    p = sub.add_parser("search-contact")
    _add_session_args(p); p.add_argument("query")
    for name in ("add-contact", "remove-contact"):
        p = sub.add_parser(name)
        _add_session_args(p)
        p.add_argument("user_id", type=int)
        p.add_argument("--contact-type", type=int, default=1)

    for name in ("typing", "stop-typing"):
        p = sub.add_parser(name)
        _add_session_args(p); _add_peer_args(p)
        p.add_argument("--typing-type", type=int, default=1)

    p = sub.add_parser("set-online")
    _add_session_args(p); p.add_argument("--offline", action="store_true")

    p = sub.add_parser("rpc")
    _add_session_args(p)
    p.add_argument("service")
    p.add_argument("method")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--spec", help="JSON field specification")
    group.add_argument("--spec-file")

    p = sub.add_parser("listen")
    _add_session_args(p)
    p.add_argument("--seconds", type=float, default=0, help="0 means until Ctrl+C")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
