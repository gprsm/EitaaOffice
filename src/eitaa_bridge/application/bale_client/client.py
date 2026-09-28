from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from .auth import AuthClient, ValidateCodeOutcome
from .catalog import RPC_CATALOG
from .codecs import (
    build_clear_chat,
    build_contact_user,
    build_delete_chat,
    build_delete_message,
    build_get_file_url,
    build_load_dialogs,
    build_load_history,
    build_load_users,
    build_search_contacts,
    build_send_message,
    build_stop_typing,
    build_typing,
    build_update_message,
    build_upload_url_request,
    decode_file_url,
    decode_history,
    decode_upload_info,
    decode_user_records,
    encode_document_content,
    encode_text_content,
)
from .config import BaleConfig, SERVICES
from .errors import AuthenticationError, ProtocolError
from .grpc_web import GrpcWebClient
from .models import BaleSession, FileDetails, Message, Peer, SendType, Update, session_from_tokens
from .vault import SessionVault
from .wire import decode_tree, encode_field_spec
from .ws import BaleWebSocket

ProgressCallback = Callable[[int, int], None]


class BaleClient:
    """Independent, research-grade Bale personal-client framework.

    Stable/high-confidence operations have typed helpers. Unknown or drifting
    schemas remain testable through ``raw_rpc`` and ``rpc_from_spec``.
    """

    def __init__(
        self,
        config: BaleConfig | None = None,
        *,
        passphrase: str | None = None,
        session: BaleSession | None = None,
    ) -> None:
        self.config = config or BaleConfig()
        self.passphrase = passphrase
        self.session = session
        self.vault = SessionVault(self.config.vault_path)
        self.log = self._configure_logging()
        self.http = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            headers={"User-Agent": self.config.user_agent},
        )
        self.grpc = GrpcWebClient(self.config, self.http)
        self.auth = AuthClient(self.config, self.grpc, self.http)
        self.ws: BaleWebSocket | None = None
        self._last_auth_start_registered: bool = True

    async def __aenter__(self) -> "BaleClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    def _configure_logging(self) -> logging.Logger:
        # An account's WebSocket logger must never inherit a FileHandler from
        # another account that was opened earlier in the same process.
        digest = hashlib.sha256(str(self.config.log_path.resolve()).encode("utf-8")).hexdigest()[:16]
        root = logging.getLogger(f"bale_personal_client.account_{digest}")
        root.propagate = False
        if root.handlers:
            return root
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
        root.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        file_handler = logging.FileHandler(self.config.log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)
        return root

    async def close(self) -> None:
        if self.ws:
            await self.ws.disconnect()
            self.ws = None
        await self.http.aclose()

    # --------------------------- Session & authentication --------------------

    def load_session(self, passphrase: str | None = None) -> BaleSession:
        phrase = passphrase or self.passphrase
        if not phrase:
            raise AuthenticationError("A vault passphrase is required")
        self.session = self.vault.load(phrase)
        return self.session

    def save_session(self, passphrase: str | None = None) -> None:
        if not self.session:
            raise AuthenticationError("No session is available to save")
        phrase = passphrase or self.passphrase
        if not phrase:
            raise AuthenticationError("A vault passphrase is required")
        self.vault.save(self.session, phrase)

    def import_access_token(
        self,
        access_token: str,
        *,
        jwt: str | None = None,
        passphrase: str | None = None,
    ) -> BaleSession:
        self.session = session_from_tokens(access_token, jwt)
        self.save_session(passphrase)
        return self.session

    async def auth_start(self, phone_number: str | int) -> str:
        result = await self.auth.start_phone_auth(phone_number)
        self._last_auth_start_registered = result.is_registered
        return result.transaction_hash

    async def auth_code(
        self,
        transaction_hash: str,
        code: str | int,
        *,
        is_registered_hint: bool | None = None,
        passphrase: str | None = None,
    ) -> ValidateCodeOutcome:
        outcome = await self.auth.validate_code(
            transaction_hash,
            code,
            is_registered_hint=(
                self._last_auth_start_registered if is_registered_hint is None else is_registered_hint
            ),
        )
        if outcome.session:
            self.session = outcome.session
            self.save_session(passphrase)
        return outcome

    async def auth_password(
        self,
        transaction_hash: str,
        password: str,
        *,
        passphrase: str | None = None,
    ) -> BaleSession:
        self.session = await self.auth.validate_password(transaction_hash, password)
        self.save_session(passphrase)
        return self.session

    async def auth_signup(
        self,
        transaction_hash: str,
        first_name: str,
        last_name: str = "",
        *,
        passphrase: str | None = None,
    ) -> BaleSession:
        self.session = await self.auth.signup(transaction_hash, first_name, last_name)
        self.save_session(passphrase)
        return self.session

    async def exchange_and_save_jwt(self, jwt: str, *, passphrase: str | None = None) -> BaleSession:
        token = await self.auth.exchange_jwt(jwt)
        self.session = session_from_tokens(token, jwt)
        self.save_session(passphrase)
        return self.session

    # --------------------------- Connection ---------------------------------

    async def connect(self, *, subscribe: bool = True, presence: bool = True) -> None:
        if not self.session:
            if self.vault.exists():
                self.load_session()
            else:
                raise AuthenticationError("No session. Authenticate or import access_token first")
        self.ws = BaleWebSocket(self.config, self.session, logger=self.log)
        await self.ws.connect(subscribe=subscribe, presence=presence)

    async def disconnect(self) -> None:
        if self.ws:
            await self.ws.disconnect()
            self.ws = None

    def add_update_handler(self, handler: Callable[[Update], Any]) -> None:
        if not self.ws:
            raise ProtocolError("Connect before registering a live update handler")
        self.ws.add_update_handler(handler)

    async def next_update(self, timeout: float | None = None) -> Update:
        return await self._require_ws().next_update(timeout)

    async def connection_test(self) -> dict[str, Any]:
        await self.connect(subscribe=False, presence=False)
        assert self.ws is not None
        result = {
            "connected": self.ws.connected,
            "server_proto_version": self.ws.server_proto_version,
            "server_api_version": self.ws.server_api_version,
            "expected_proto_version": self.config.proto_version,
            "expected_api_version": self.config.api_version,
        }
        await self.disconnect()
        return result

    # --------------------------- Generic RPC lab ----------------------------

    async def raw_rpc(self, service: str, method: str, payload: bytes = b"") -> bytes:
        return await self._require_ws().rpc(service, method, payload)

    async def rpc_from_spec(
        self,
        service: str,
        method: str,
        field_spec: list[dict[str, Any]] | dict[str, Any],
    ) -> dict[str, Any]:
        request = encode_field_spec(field_spec)
        response = await self.raw_rpc(service, method, request)
        return {
            "service": service,
            "method": method,
            "request_hex": request.hex(),
            "response_hex": response.hex(),
            "decoded": decode_tree(response),
        }

    @staticmethod
    def rpc_catalog() -> dict[str, list[str]]:
        return RPC_CATALOG

    # --------------------------- Messaging ----------------------------------

    async def load_dialogs(
        self,
        *,
        limit: int = 20,
        min_date: int = 0,
        dialog_type: int = 0,
        exclude_pinned: bool = False,
        archive: bool = False,
    ) -> dict[str, Any]:
        payload = build_load_dialogs(
            min_date=min_date,
            limit=limit,
            dialog_type=dialog_type,
            exclude_pinned=exclude_pinned,
            archive=archive,
        )
        response = await self.raw_rpc(SERVICES["messaging"], "LoadDialogs", payload)
        return {"raw": response, "decoded": decode_tree(response)}

    async def load_history(
        self,
        peer: Peer,
        *,
        limit: int = 20,
        offset_date: int = (1 << 63) - 1,
        load_mode: int = 2,
    ) -> list[Message]:
        payload = build_load_history(peer, offset_date=offset_date, load_mode=load_mode, limit=limit)
        response = await self.raw_rpc(SERVICES["messaging"], "LoadHistory", payload)
        return decode_history(response, peer)

    async def send_text(self, peer: Peer, text: str, *, silent: bool = False) -> bytes:
        random_id = secrets.randbits(63)
        payload = build_send_message(peer, random_id, encode_text_content(text), silent=silent)
        return await self.raw_rpc(SERVICES["messaging"], "SendMessage", payload)

    async def edit_message(self, peer: Peer, message_id: int, text: str) -> bytes:
        return await self.raw_rpc(
            SERVICES["messaging"],
            "UpdateMessage",
            build_update_message(peer, message_id, text),
        )

    async def delete_message(
        self,
        peer: Peer,
        message_ids: list[int],
        dates: list[int],
        *,
        just_me: bool = False,
    ) -> bytes:
        if len(message_ids) != len(dates):
            raise ValueError("message_ids and dates must have equal lengths")
        return await self.raw_rpc(
            SERVICES["messaging"],
            "DeleteMessage",
            build_delete_message(peer, message_ids, dates, just_me=just_me),
        )

    async def clear_chat(self, peer: Peer) -> bytes:
        return await self.raw_rpc(SERVICES["messaging"], "ClearChat", build_clear_chat(peer))

    async def delete_chat(self, peer: Peer) -> bytes:
        return await self.raw_rpc(SERVICES["messaging"], "DeleteChat", build_delete_chat(peer))

    # --------------------------- Files --------------------------------------

    async def upload_file(
        self,
        path: str | Path,
        *,
        peer: Peer | None = None,
        send_type: SendType = SendType.DOCUMENT,
        mime_type: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> tuple[FileDetails, bytes]:
        if not self.session or self.session.user_id is None:
            raise AuthenticationError(
                "Session does not expose user_id. Import it through a JWT-bearing session or use raw RPC"
            )
        request, name, size, mime = build_upload_url_request(
            path,
            user_id=self.session.user_id,
            peer=peer,
            send_type=send_type,
            mime_type=mime_type,
        )
        raw = await self.raw_rpc(SERVICES["files"], "GetNasimFileUploadUrl", request)
        info = decode_upload_info(raw)
        if not info.url:
            raise ProtocolError("Upload URL response did not contain a URL")
        p = Path(path)

        async def chunks():
            sent = 0
            with p.open("rb") as handle:
                while True:
                    chunk = handle.read(max(1, info.chunk_size))
                    if not chunk:
                        break
                    sent += len(chunk)
                    if progress:
                        progress(sent, size)
                    yield chunk

        response = await self.http.put(
            info.url,
            content=chunks(),
            headers={"Content-Type": mime, "Content-Length": str(size)},
        )
        response.raise_for_status()
        details = FileDetails(
            file_id=info.file_id,
            access_hash=info.access_hash or 0,
            name=name,
            size=size,
            mime_type=mime,
        )
        return details, raw

    async def send_file(
        self,
        peer: Peer,
        path: str | Path,
        *,
        caption: str | None = None,
        send_type: SendType = SendType.DOCUMENT,
        access_hash: int | None = None,
        progress: ProgressCallback | None = None,
    ) -> bytes:
        details, _ = await self.upload_file(
            path,
            peer=peer,
            send_type=send_type,
            progress=progress,
        )
        if access_hash is not None:
            details.access_hash = access_hash
        details.caption = caption
        payload = build_send_message(peer, secrets.randbits(63), encode_document_content(details))
        return await self.raw_rpc(SERVICES["messaging"], "SendMessage", payload)

    async def get_file_url(self, details: FileDetails):
        raw = await self.raw_rpc(SERVICES["files"], "GetNasimFileUrl", build_get_file_url(details))
        return decode_file_url(raw)

    async def download_file(
        self,
        details: FileDetails,
        destination: str | Path,
        *,
        progress: ProgressCallback | None = None,
    ) -> Path:
        info = await self.get_file_url(details)
        if not info.url:
            raise ProtocolError("File URL response did not contain a URL")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        received = 0
        async with self.http.stream("GET", info.url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", details.size or 0))
            with destination.open("wb") as handle:
                async for chunk in response.aiter_bytes(max(1, info.chunk_size)):
                    handle.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
        return destination

    # --------------------------- Contacts & users ---------------------------

    async def get_contacts(self) -> dict[str, Any]:
        response = await self.raw_rpc(SERVICES["users"], "GetContacts", b"")
        return {"records": decode_user_records(response), "decoded": decode_tree(response), "raw": response}

    async def search_contacts(self, query: str) -> dict[str, Any]:
        response = await self.raw_rpc(SERVICES["users"], "SearchContacts", build_search_contacts(query))
        return {"records": decode_user_records(response), "decoded": decode_tree(response), "raw": response}

    async def load_users(self, users: list[Peer]) -> dict[str, Any]:
        response = await self.raw_rpc(SERVICES["users"], "LoadUsers", build_load_users(users))
        return {"records": decode_user_records(response), "decoded": decode_tree(response), "raw": response}

    async def add_contact(self, user_id: int, contact_type: int = 1) -> bytes:
        return await self.raw_rpc(
            SERVICES["users"], "AddContact", build_contact_user(user_id, contact_type)
        )

    async def remove_contact(self, user_id: int, contact_type: int = 1) -> bytes:
        return await self.raw_rpc(
            SERVICES["users"], "RemoveContact", build_contact_user(user_id, contact_type)
        )

    # --------------------------- Presence -----------------------------------

    async def typing(self, peer: Peer, typing_type: int = 1) -> bytes:
        return await self.raw_rpc(SERVICES["presence"], "Typing", build_typing(peer, typing_type))

    async def stop_typing(self, peer: Peer, typing_type: int = 1) -> bytes:
        return await self.raw_rpc(
            SERVICES["presence"], "StopTyping", build_stop_typing(peer, typing_type)
        )

    async def set_online(self, online: bool = True) -> bytes:
        return await self._require_ws().set_online(online)

    def _require_ws(self) -> BaleWebSocket:
        if not self.ws or not self.ws.connected:
            raise ProtocolError("WebSocket is not connected")
        return self.ws


def to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"hex": value.hex(), "length": len(value)}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if hasattr(value, "__dict__"):
        return {k: to_jsonable(v) for k, v in vars(value).items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value


def dumps(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, indent=2, default=str)
