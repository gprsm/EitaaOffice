"""Stable Python API facade for the Bale personal client.

This is the modular boundary of the Bale branch: callers depend on
:class:`BaleApi` only, never on the underlying engine, transport or wire
codecs. Every returned value is JSON-serializable (via :func:`to_jsonable`)
and errors surface as :class:`BaleApiError` subclasses with a stable ``code``.

Phase 1 scope: authentication (phone/OTP/2FA), session management, contact
control (list/search/add-by-phone/remove), dialogs, text/file/photo/media
sending, history reading and media download. Channel/group *viewing* is a
later phase and intentionally absent.

The engine never touches the main application: nothing in
``eitaa_bridge`` outside this quarantined package imports it.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .client import BaleClient, ProgressCallback
from .codecs import decode_content
from .codecs_ext import (
    DialogSummary,
    UserRecord,
    build_import_contacts,
    classify_media,
    decode_contact_summaries,
    decode_dialog_summaries,
    decode_users,
    peer_from_identifier,
)
from .config import BaleConfig, SERVICES
from .errors import AuthenticationError, BaleError, ProtocolError, RpcError
from .models import FileDetails, Peer, PeerType, SendType
from .wire import decode_tree

log = logging.getLogger("bale_client.api")

__all__ = [
    "BaleApi",
    "BaleApiError",
    "BaleAuthPending",
    "BaleNotConnected",
    "SendType",
]


class BaleApiError(Exception):
    """Stable facade error; ``code`` is safe for logs and API responses."""

    def __init__(self, message: str, *, code: str = "bale_api_error") -> None:
        super().__init__(message)
        self.code = code


class BaleAuthPending(BaleApiError):
    def __init__(self, message: str, *, stage: str, transaction_hash: str | None = None) -> None:
        super().__init__(message, code=f"bale_auth_{stage}")
        self.stage = stage
        self.transaction_hash = transaction_hash


class BaleNotConnected(BaleApiError):
    def __init__(self) -> None:
        super().__init__("The Bale client is not connected", code="bale_not_connected")


@dataclass(slots=True)
class BaleAccountCard:
    """Safe session summary: no tokens, cookies or hashes leak here."""

    authenticated: bool
    user_id: int | None
    expires_at: int | None
    has_vault: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "authenticated": self.authenticated,
            "user_id": self.user_id,
            "expires_at": self.expires_at,
            "has_vault": self.has_vault,
        }


class BaleApi:
    """Async facade over :class:`BaleClient` with JSON-safe results.

    Usage::

        api = await BaleApi.open(passphrase="...")
        contacts = await api.list_contacts()
        await api.send_text(user_id, "سلام")
        await api.close()
    """

    def __init__(self, client: BaleClient) -> None:
        self._client = client
        self._auth_start_hint: bool | None = None

    # ------------------------------- lifecycle -------------------------------

    @classmethod
    def create(
        cls,
        *,
        passphrase: str | None = None,
        vault_path: str | Path | None = None,
        log_path: str | Path | None = None,
    ) -> "BaleApi":
        """Build an unauthenticated facade; call :meth:`auth_start` or
        :meth:`connect` before operations that need a session."""
        config = BaleConfig()
        if vault_path is not None:
            config.vault_path = Path(vault_path)
        if log_path is not None:
            config.log_path = Path(log_path)
        return cls(BaleClient(config, passphrase=passphrase))

    @classmethod
    async def open(
        cls,
        passphrase: str,
        *,
        vault_path: str | Path | None = None,
        log_path: str | Path | None = None,
        subscribe: bool = True,
    ) -> "BaleApi":
        """Open a connected facade from an existing vault session."""
        api = cls.create(passphrase=passphrase, vault_path=vault_path, log_path=log_path)
        await api.connect(passphrase=passphrase, subscribe=subscribe)
        return api

    async def connect(
        self,
        *,
        passphrase: str | None = None,
        subscribe: bool = True,
        presence: bool = True,
    ) -> dict[str, Any]:
        """Load the vault session (when needed) and connect the WebSocket.

        Returns the connection handshake summary (server proto/api versions).
        """
        try:
            if not self._client.session:
                self._client.load_session(passphrase)
            await self._client.connect(subscribe=subscribe, presence=presence)
        except FileNotFoundError as exc:
            raise BaleApiError("No saved Bale session vault exists", code="bale_vault_missing") from exc
        except AuthenticationError as exc:
            raise BaleApiError("Vault passphrase rejected", code="bale_vault_locked") from exc
        except ProtocolError as exc:
            raise BaleApiError(f"Connection failed: {exc}", code="bale_connect_failed") from exc
        ws = self._client.ws
        return {
            "connected": True,
            "server_proto_version": getattr(ws, "server_proto_version", None),
            "server_api_version": getattr(ws, "server_api_version", None),
        }

    async def close(self) -> None:
        """Disconnect and release HTTP resources; the vault is preserved."""
        await self._client.close()

    async def __aenter__(self) -> "BaleApi":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    def _require_client(self) -> BaleClient:
        return self._client

    def _require_ws(self) -> None:
        if not self._client.ws or not self._client.ws.connected:
            raise BaleNotConnected()

    # -------------------------------- auth ----------------------------------

    async def auth_start(self, phone_number: str | int) -> dict[str, Any]:
        """Request an OTP for ``phone_number`` (E.164-ish, e.g. +98912...)."""
        try:
            transaction_hash = await self._client.auth_start(phone_number)
        except BaleError as exc:
            raise BaleApiError(f"StartPhoneAuth failed: {exc}", code="bale_auth_start_failed") from exc
        self._auth_start_hint = self._client._last_auth_start_registered
        return {
            "transaction_hash": transaction_hash,
            "next": "code",
        }

    async def auth_code(
        self,
        transaction_hash: str,
        code: str | int,
        *,
        passphrase: str | None = None,
    ) -> dict[str, Any]:
        """Submit the OTP. May complete auth or report the next stage."""
        try:
            outcome = await self._client.auth_code(
                transaction_hash,
                code,
                is_registered_hint=self._auth_start_hint,
                passphrase=passphrase,
            )
        except BaleError as exc:
            raise BaleApiError(f"ValidateCode failed: {exc}", code="bale_auth_code_failed") from exc
        if outcome.session is not None:
            return {"authenticated": True, "next": None, "user_id": outcome.session.user_id}
        if outcome.password_required:
            return {"authenticated": False, "next": "password", "transaction_hash": transaction_hash}
        return {"authenticated": False, "next": "signup", "transaction_hash": transaction_hash}

    async def auth_password(
        self,
        transaction_hash: str,
        password: str,
        *,
        passphrase: str | None = None,
    ) -> dict[str, Any]:
        try:
            session = await self._client.auth_password(transaction_hash, password, passphrase=passphrase)
        except BaleError as exc:
            raise BaleApiError(f"ValidatePassword failed: {exc}", code="bale_auth_password_failed") from exc
        return {"authenticated": True, "user_id": session.user_id}

    async def auth_signup(
        self,
        transaction_hash: str,
        first_name: str,
        last_name: str = "",
        *,
        passphrase: str | None = None,
    ) -> dict[str, Any]:
        """Complete signup for an unregistered phone (rare path)."""
        try:
            session = await self._client.auth_signup(
                transaction_hash, first_name, last_name, passphrase=passphrase
            )
        except BaleError as exc:
            raise BaleApiError(f"SignUp failed: {exc}", code="bale_auth_signup_failed") from exc
        return {"authenticated": True, "user_id": session.user_id}

    async def account_card(self) -> dict[str, Any]:
        """Safe account summary; never includes token material."""
        session = self._client.session
        card = BaleAccountCard(
            authenticated=session is not None,
            user_id=session.user_id if session else None,
            expires_at=session.expires_at if session else None,
            has_vault=self._client.vault.exists(),
        )
        return card.to_dict()

    # ------------------------------- contacts --------------------------------

    async def list_contacts(self) -> list[dict[str, Any]]:
        """Return the account's contacts with names.

        Live GetContacts (2026-09-15) returns peer-only blobs; names and
        access hashes arrive from a follow-up LoadUsers batch. Some server
        versions return full user records directly, so records are preferred
        when present. Output shape is uniform: ``peer`` + display fields.
        """
        self._require_ws()
        response = await self._rpc("users", "GetContacts", b"")
        # Peer-only blobs decode as nameless records; treat those as "not
        # enriched" and route them through the LoadUsers batch instead.
        records = [r for r in decode_users(response) if _record_is_enriched(r)]
        if not records:
            peers = [s.peer for s in decode_contact_summaries(response)]
            if not peers:
                return []
            enriched = await self._load_user_names(peers)
            records = [enriched.get(p.id) or self._blank_record(p) for p in peers]
        out: list[dict[str, Any]] = []
        for record in records:
            out.append(_contact_record_to_dict(record))
        return out

    async def _load_user_names(self, peers: list[Peer]) -> dict[int, Any]:
        """LoadUsers for the given peers, keyed by user id ({} on failure)."""
        try:
            from .codecs import build_load_users

            payload = build_load_users(peers)
            response = await self._rpc("users", "LoadUsers", payload)
            return {record.id: record for record in decode_users(response)}
        except BaleApiError:
            return {}

    def _blank_record(self, peer: Peer) -> Any:
        """Placeholder record for a peer LoadUsers did not return."""
        from .codecs_ext import UserRecord

        return UserRecord(id=peer.id, access_hash=peer.access_hash)

    async def search_contacts(self, query: str) -> list[dict[str, Any]]:
        """Search contacts by free-text query (name/username/number).

        Server-side SearchContacts matches saved contacts only and can return
        nameless partial records; those trigger a local scan of the enriched
        contact list so nicknames (local_name) match too.
        """
        self._require_ws()
        response = await self._rpc("users", "SearchContacts", _build_search(query))
        lowered = query.strip().lower()
        records = [r for r in decode_users(response) if _record_is_enriched(r)]
        matches = [_contact_record_to_dict(r) for r in records]
        if matches or not lowered:
            return matches
        return [c for c in await self.list_contacts() if self._contact_matches(c, lowered)]

    @staticmethod
    def _contact_matches(contact: dict[str, Any], lowered: str) -> bool:
        name = (contact.get("name") or "").lower()
        username = (contact.get("username") or "").lower()
        return lowered in name or lowered in username

    async def add_contact_by_phone(
        self,
        phone_number: str | int,
        display_name: str,
        *,
        contact_type: int = 1,
    ) -> dict[str, Any]:
        """Import a contact by phone number and return matched users.

        ImportContacts registers the phone in the account's address book; the
        returned user ids are the addressable peers for messaging.
        """
        self._require_ws()
        phone = _normalize_phone(phone_number)
        response = await self._rpc("users", "ImportContacts", build_import_contacts([(phone, display_name)]))
        records = decode_users(response)
        if not records:
            summaries = decode_contact_summaries(response)
            matches = [dict(s) for s in summaries]
        else:
            matches = [r.to_dict() for r in records]
        return {
            "phone": phone,
            "matched": bool(matches),
            "users": matches,
        }

    async def add_contact(
        self,
        user_id: int | str,
        *,
        contact_type: int = 1,
    ) -> dict[str, Any]:
        """Add an existing Bale user id to the contact list."""
        self._require_ws()
        user_id = int(user_id)
        await self._rpc("users", "AddContact", _build_contact_user(user_id, contact_type))
        return {"user_id": user_id, "added": True}

    async def remove_contact(
        self,
        user_id: int | str,
        *,
        contact_type: int = 1,
    ) -> dict[str, Any]:
        """Remove a user id from the contact list."""
        self._require_ws()
        user_id = int(user_id)
        await self._rpc("users", "RemoveContact", _build_contact_user(user_id, contact_type))
        return {"user_id": user_id, "removed": True}

    # ------------------------------- dialogs ---------------------------------

    async def list_dialogs(
        self,
        *,
        limit: int = 20,
        offset_date: int = (1 << 63) - 1,
    ) -> list[dict[str, Any]]:
        """Recent conversation list with peer ids and last-message previews."""
        self._require_ws()
        payload = _build_load_dialogs(limit=limit, offset_date=offset_date)
        response = await self._rpc("messaging", "LoadDialogs", payload)
        return [s.to_dict() for s in decode_dialog_summaries(response)]


    # ------------------------------ messaging --------------------------------

    async def send_text(
        self,
        user_id: int | str,
        text: str,
        *,
        silent: bool = False,
    ) -> dict[str, Any]:
        """Send a text message to a private peer (contact user id)."""
        self._require_ws()
        if not text or not text.strip():
            raise BaleApiError("Message text cannot be empty", code="bale_empty_text")
        peer = peer_from_identifier(user_id)
        random_id = secrets.randbits(63)
        payload = _build_send_text(peer, random_id, text, silent=silent)
        response = await self._rpc("messaging", "SendMessage", payload)
        return {"user_id": peer.id, "random_id": random_id, "sent": True, "response_size": len(response)}

    async def send_file_bytes(
        self,
        user_id: int | str,
        name: str,
        data: bytes,
        *,
        caption: str | None = None,
        staging_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """Send in-memory bytes (browser upload) by staging them to disk.

        The engine's upload path needs a real file; bytes go to a temp file
        inside ``staging_dir`` (or the vault's data dir) and are removed
        after the upload completes.
        """
        self._require_ws()
        if not name or "/" in name or "\\" in name:
            raise BaleApiError("Unsafe file name", code="bale_unsafe_name")
        base = Path(staging_dir) if staging_dir else Path(self._client.config.vault_path).parent / "uploads"
        base.mkdir(parents=True, exist_ok=True)
        staged = base / f"{secrets.token_hex(8)}_{name}"
        try:
            staged.write_bytes(data)
            return await self.send_file(user_id, staged, caption=caption)
        finally:
            with contextlib.suppress(OSError):
                staged.unlink(missing_ok=True)

    async def send_file(
        self,
        user_id: int | str,
        path: str | Path,
        *,
        caption: str | None = None,
        media_kind: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Upload a file and send it as photo/video/audio/document.

        ``media_kind`` overrides the mime-based classification ("photo",
        "video", "audio", "document").
        """
        self._require_ws()
        peer = peer_from_identifier(user_id)
        p = Path(path)
        if not p.is_file():
            raise BaleApiError(f"File not found: {p}", code="bale_file_missing")
        details, _ = await self._client.upload_file(p, peer=peer, send_type=SendType.DOCUMENT, progress=progress)
        if caption:
            details.caption = caption
        if media_kind is not None:
            details.mime_type = _kind_to_mime(media_kind, p)
        payload = _build_send_document(peer, secrets.randbits(63), details)
        response = await self._rpc("messaging", "SendMessage", payload)
        return {
            "user_id": peer.id,
            "file_id": details.file_id,
            "name": details.name,
            "size": details.size,
            "media_kind": media_kind or classify_media(details),
            "sent": True,
            "response_size": len(response),
        }

    async def send_photo(
        self,
        user_id: int | str,
        path: str | Path,
        *,
        caption: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Send an image file (photo send-type)."""
        return await self.send_file(user_id, path, caption=caption, media_kind="photo", progress=progress)

    async def send_media(
        self,
        user_id: int | str,
        path: str | Path,
        *,
        caption: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Send any media file with mime-based classification."""
        return await self.send_file(user_id, path, caption=caption, progress=progress)

    async def read_history(
        self,
        user_id: int | str,
        *,
        limit: int = 20,
        offset_date: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read recent messages of a private conversation."""
        self._require_ws()
        peer = peer_from_identifier(user_id)
        messages = await self._client.load_history(peer, limit=limit, offset_date=offset_date or (1 << 63) - 1)
        return [_message_to_dict(m) for m in messages]

    async def read_message_media(
        self,
        user_id: int | str,
        message_id: int,
        destination_dir: str | Path,
    ) -> dict[str, Any]:
        """Download the document/photo attached to a history message.

        Finds the message by id in recent history and downloads its file.
        """
        self._require_ws()
        peer = peer_from_identifier(user_id)
        history = await self._client.load_history(peer, limit=100)
        target = next((m for m in history if m.message_id == message_id and m.document), None)
        if target is None or target.document is None:
            raise BaleApiError(
                f"No downloadable document found for message {message_id}",
                code="bale_media_not_found",
            )
        destination = Path(destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        out_path = destination / (target.document.name or f"bale_{message_id}")
        saved = await self._client.download_file(target.document, out_path)
        return {
            "message_id": message_id,
            "path": str(saved),
            "name": target.document.name,
            "size": target.document.size,
            "media_kind": classify_media(target.document),
        }

    # ------------------------------- internals -------------------------------

    async def _rpc(self, service_key: str, method: str, payload: bytes) -> bytes:
        try:
            return await self._client.raw_rpc(SERVICES[service_key], method, payload)
        except RpcError as exc:
            text = str(exc)
            if "PermissionDenied" in text:
                raise BaleApiError(
                    "Bale server denied access to this peer (group/channel not permitted "
                    "for this session or not a member)",
                    code="bale_access_denied",
                ) from exc
            raise BaleApiError(f"RPC {method} failed: {exc}", code="bale_rpc_error") from exc
        except ProtocolError as exc:
            raise BaleApiError(f"RPC {method} transport failed: {exc}", code="bale_transport_error") from exc
        except BaleError as exc:
            raise BaleApiError(f"RPC {method} failed: {exc}", code="bale_rpc_error") from exc


# ----------------------------------------------------------------------------
# Wire helpers (kept local so the facade does not re-export engine internals)
# ----------------------------------------------------------------------------

def _record_is_enriched(record: Any) -> bool:
    """True when a decoded user record carries display fields (not peer-only)."""
    return bool(record.name or record.local_name or record.username)


def _contact_record_to_dict(record: Any) -> dict[str, Any]:
    """Uniform contact shape: ``peer`` plus display fields.

    The user's own nickname (local_name) is the most useful display label;
    fall back to the account-level name.
    """
    return {
        "peer": {"id": record.id, "type": int(PeerType.PRIVATE)},
        "name": record.local_name or record.name,
        "username": record.username,
        "is_bot": record.is_bot,
        "access_hash": record.access_hash,
    }


def _normalize_phone(phone_number: str | int) -> int:
    cleaned = str(phone_number).strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not cleaned.isdigit():
        raise BaleApiError("Phone number must contain digits only after normalization", code="bale_invalid_phone")
    return int(cleaned)


def _build_search(query: str) -> bytes:
    from .codecs import build_search_contacts

    return build_search_contacts(query)


def _build_contact_user(user_id: int, contact_type: int) -> bytes:
    from .codecs import build_contact_user

    return build_contact_user(user_id, contact_type)


def _build_load_dialogs(*, limit: int = 20, offset_date: int = (1 << 63) - 1) -> bytes:
    from .codecs import build_load_dialogs

    return build_load_dialogs(limit=limit, offset_date=offset_date)



def _build_send_text(peer: Peer, random_id: int, text: str, *, silent: bool) -> bytes:
    from .codecs import build_send_message, encode_text_content

    return build_send_message(peer, random_id, encode_text_content(text), silent=silent)


def _build_send_document(peer: Peer, random_id: int, details: FileDetails) -> bytes:
    from .codecs import build_send_message, encode_document_content

    return build_send_message(peer, random_id, encode_document_content(details))


def _kind_to_mime(kind: str, path: Path) -> str:
    import mimetypes

    table = {
        "photo": "image/jpeg",
        "video": "video/mp4",
        "audio": "audio/mpeg",
        "document": "application/octet-stream",
    }
    if kind not in table:
        raise BaleApiError(f"Unknown media kind: {kind}", code="bale_unknown_media_kind")
    guessed = mimetypes.guess_type(path.name)[0]
    if kind == "photo" and guessed and guessed.startswith("image/"):
        return guessed
    return table[kind]


def _message_to_dict(message: Any) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "sender_id": message.sender_id,
        "date": message.date,
        "text": message.text,
        "media": (
            {
                "name": message.document.name,
                "size": message.document.size,
                "mime_type": message.document.mime_type,
                "media_kind": classify_media(message.document),
            }
            if message.document
            else None
        ),
    }
