"""Typed codec extensions for the Bale personal client.

The base codecs in ``codecs.py`` keep every response as tolerant raw trees.
This module adds typed builders/decoders for the Phase-1 operations the Bale
branch needs: contact import by phone number, user-record decoding, dialog
summaries and message-content discrimination. Field numbers follow the
high-confidence wire observations recorded in ``PROTOCOL_NOTES.md`` and the
public schema observations used for design only; nothing is vendored.

If a server response disagrees, the escape hatch remains ``raw_rpc`` plus a
patch to this module only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ChatType, FileDetails, Message, Peer, PeerType
from .wire import ProtoWriter, get_all, get_first, parse_fields, wrapped_string

# User record scalars (stable across observed server versions):
#   1=id, 2=access_hash, 3=name, 4=local_name, 5=sex, 7=is_bot,
#   9=username, 16=is_deleted, 19=created_at
USER_FIELD_ID = 1
USER_FIELD_ACCESS_HASH = 2
USER_FIELD_NAME = 3
USER_FIELD_LOCAL_NAME = 4
USER_FIELD_IS_BOT = 7
USER_FIELD_USERNAME = 9
USER_FIELD_IS_DELETED = 16
USER_FIELD_CREATED_AT = 19


@dataclass(slots=True)
class UserRecord:
    """Best-effort typed view of a Bale user record."""

    id: int
    access_hash: int | None = None
    name: str | None = None
    local_name: str | None = None
    username: str | None = None
    is_bot: bool = False
    is_deleted: bool = False
    created_at: int | None = None
    raw: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "access_hash": self.access_hash,
            "name": self.name,
            "local_name": self.local_name,
            "username": self.username,
            "is_bot": self.is_bot,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class ContactSummary:
    peer: Peer
    name: str | None = None
    username: str | None = None
    is_bot: bool = False
    access_hash: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer": {"id": self.peer.id, "type": int(self.peer.type)},
            "name": self.name,
            "username": self.username,
            "is_bot": self.is_bot,
            "access_hash": self.access_hash,
        }


@dataclass(slots=True)
class DialogSummary:
    peer: Peer
    unread_count: int = 0
    sort_date: int | None = None
    sender_id: int | None = None
    last_message_id: int | None = None
    last_message_date: int | None = None
    last_text: str | None = None
    last_document: FileDetails | None = None
    unread_mentions: int | None = None

    def to_dict(self) -> dict[str, Any]:
        doc_dict = None
        if self.last_document:
            doc_dict = self.last_document.to_dict()
            doc_dict["media_kind"] = classify_media(self.last_document)
        return {
            "peer": {"id": self.peer.id, "type": int(self.peer.type)},
            "unread_count": self.unread_count,
            "sort_date": self.sort_date,
            "sender_id": self.sender_id,
            "last_message_id": self.last_message_id,
            "last_message_date": self.last_message_date,
            "last_text": self.last_text,
            "last_document": doc_dict,
            "unread_mentions": self.unread_mentions,
        }



def build_import_contacts(entries: list[tuple[int, str]]) -> bytes:
    """Build an ImportContacts request.

    ``entries`` are ``(phone_number, display_name)`` pairs; the phone is the
    international number without separators (e.g. ``98912xxxxxxx``).
    Each entry maps to a nested message ``field 1 { 1: phone, 2: wrapped name }``
    per the observed ContactData shape.
    """
    writer = ProtoWriter()
    for phone, name in entries:
        entry = (
            ProtoWriter()
            .int64(1, int(phone))
            .message(2, ProtoWriter().string(1, name))
        )
        writer.message(1, entry)
    return writer.build()


def build_search_contacts_by_phone(phone: int) -> bytes:
    """SearchContacts with a normalized phone query."""
    query = str(phone)
    return ProtoWriter().string(1, query).build()


def _decode_user_record(data: bytes) -> UserRecord | None:
    """Decode one user record; returns ``None`` when the blob is not a user."""
    try:
        fields = parse_fields(data)
    except Exception:
        return None
    user_id = get_first(fields, USER_FIELD_ID)
    if not isinstance(user_id, int) or not user_id:
        return None
    # A real user record always carries a name or an access hash alongside the
    # id; guard against mis-typed nested containers (Peer/Chat payloads).
    access_hash = get_first(fields, USER_FIELD_ACCESS_HASH)
    name_raw = get_first(fields, USER_FIELD_NAME)
    if not isinstance(access_hash, int) and not isinstance(name_raw, bytes):
        return None
    name = _decode_text(name_raw)
    local_raw = get_first(fields, USER_FIELD_LOCAL_NAME)
    # Observed live 2026-09-15: local_name arrives as a wrapped message
    # {1: text} (the user's custom nickname for the contact), not a string.
    local_name = _decode_wrapped_text(local_raw)
    username_raw = get_first(fields, USER_FIELD_USERNAME)
    if isinstance(username_raw, bytes):
        username = _decode_text(username_raw) or _decode_wrapped_text(username_raw)
    else:
        username = None
    is_bot = get_first(fields, USER_FIELD_IS_BOT)
    is_deleted = get_first(fields, USER_FIELD_IS_DELETED)
    created_at = get_first(fields, USER_FIELD_CREATED_AT)
    return UserRecord(
        id=user_id,
        access_hash=access_hash if isinstance(access_hash, int) else None,
        name=name,
        local_name=local_name,
        username=username,
        is_bot=bool(is_bot) if isinstance(is_bot, int) else False,
        is_deleted=bool(is_deleted) if isinstance(is_deleted, int) else False,
        created_at=created_at if isinstance(created_at, int) else None,
        raw=data,
    )


def _decode_text(raw: Any) -> str | None:
    if not isinstance(raw, bytes):
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text and all(ch.isprintable() or ch in "\r\n\t" for ch in text) else None


def _decode_wrapped_text(raw: Any) -> str | None:
    """Decode ``{1: text}``-wrapped string fields (local_name/username shape).

    Falls back to treating the blob as a plain string when it does not parse
    as a wrapper message with a textual field 1.
    """
    if not isinstance(raw, bytes):
        return None
    direct = _decode_text(raw)
    if direct is not None:
        return direct
    try:
        inner = get_first(parse_fields(raw), 1)
    except Exception:
        return None
    return _decode_text(inner)


def _iter_user_blobs(data: bytes) -> list[tuple[int, bytes]]:
    """Yield ``(container_field, blob)`` candidates that may hold user records."""
    out: list[tuple[int, bytes]] = []
    try:
        top = parse_fields(data)
    except Exception:
        return out
    for field in top:
        if isinstance(field.value, bytes):
            out.append((field.number, field.value))
    return out


def decode_users(data: bytes) -> list[UserRecord]:
    """Extract typed user records from a users-service response.

    Tolerates the known container drift: records may sit at the top level
    (e.g. LoadUsers field 1) or one level deeper inside a wrapper message.
    """
    records: list[UserRecord] = []
    seen: set[int] = set()
    for container, blob in _iter_user_blobs(data):
        direct = _decode_user_record(blob)
        if direct is not None:
            if direct.id not in seen:
                seen.add(direct.id)
                records.append(direct)
            continue
        # Try one nesting level deeper for wrapped containers.
        try:
            inner_fields = parse_fields(blob)
        except Exception:
            continue
        for inner in inner_fields:
            if not isinstance(inner.value, bytes):
                continue
            record = _decode_user_record(inner.value)
            if record is not None and record.id not in seen:
                seen.add(record.id)
                records.append(record)
    return records


def _extract_peer(fields: list, container: str = "peer") -> Peer | None:
    raw = get_first(fields, 1)
    if not isinstance(raw, bytes):
        return None
    try:
        peer_fields = parse_fields(raw)
    except Exception:
        return None
    peer_type = get_first(peer_fields, 1)
    peer_id = get_first(peer_fields, 2)
    access_hash = get_first(peer_fields, 3)
    if not isinstance(peer_id, int) or not peer_id:
        return None
    try:
        kind = PeerType(int(peer_type)) if isinstance(peer_type, int) else PeerType.PRIVATE
    except ValueError:
        kind = PeerType.PRIVATE
    return Peer(
        id=peer_id,
        type=kind,
        access_hash=access_hash if isinstance(access_hash, int) else None,
    )


def decode_contact_summaries(data: bytes) -> list[ContactSummary]:
    """Decode a GetContacts-style response into contact summaries.

    ContactsResponse exposes peers under container field 4, but observed
    personal-client responses drift; accept any container and keep the first
    successful interpretation per unique peer id.
    """
    out: list[ContactSummary] = []
    seen: set[int] = set()
    for container, blob in _iter_user_blobs(data):
        try:
            fields = parse_fields(blob)
        except Exception:
            continue
        peer = _extract_peer(fields)
        if peer is not None:
            name = _decode_text(get_first(fields, 3)) or _decode_text(get_first(fields, 4))
            username = _decode_text(get_first(fields, 9))
            is_bot = get_first(fields, 7)
            access_hash = get_first(fields, 2)
            if peer.id in seen:
                continue
            seen.add(peer.id)
            out.append(
                ContactSummary(
                    peer=peer,
                    name=name,
                    username=username,
                    is_bot=bool(is_bot) if isinstance(is_bot, int) else False,
                    access_hash=access_hash if isinstance(access_hash, int) else peer.access_hash,
                )
            )
            continue
        # Wrapped shape: container holds user records directly.
        record = _decode_user_record(blob)
        if record is not None and record.id not in seen:
            seen.add(record.id)
            out.append(
                ContactSummary(
                    peer=Peer(id=record.id, type=PeerType.PRIVATE, access_hash=record.access_hash),
                    name=record.name or record.local_name,
                    username=record.username,
                    is_bot=record.is_bot,
                    access_hash=record.access_hash,
                )
            )
    return out


def decode_dialog_summaries(data: bytes) -> list[DialogSummary]:
    """Decode a LoadDialogs response into dialog summaries.

    DialogResponse keeps peers under container field 3; each entry embeds a
    peer (1), unread count (2), sort date (3), sender id (4), message id (5),
    date (6), content (7) and wrapped unread mentions (13).
    """
    out: list[DialogSummary] = []
    seen: set[int] = set()
    for container, blob in _iter_user_blobs(data):
        try:
            fields = parse_fields(blob)
        except Exception:
            continue
        peer = _extract_peer(fields)
        if peer is None:
            continue
        if peer.id in seen:
            continue
        content_raw = get_first(fields, 7)
        text: str | None = None
        document: FileDetails | None = None
        if isinstance(content_raw, bytes):
            from .codecs import decode_content

            text, document = decode_content(content_raw)
        unread_mentions = get_first(fields, 13)
        if isinstance(unread_mentions, bytes):
            try:
                unread_mentions = get_first(parse_fields(unread_mentions), 1)
            except Exception:
                unread_mentions = None
        seen.add(peer.id)
        out.append(
            DialogSummary(
                peer=peer,
                unread_count=int(get_first(fields, 2, 0) or 0),
                sort_date=_signed_int_or_none(get_first(fields, 3)),
                sender_id=_int_or_none(get_first(fields, 4)),
                last_message_id=_int_or_none(get_first(fields, 5)),
                last_message_date=_signed_int_or_none(get_first(fields, 6)),
                last_text=text,
                last_document=document,
                unread_mentions=_int_or_none(unread_mentions),
            )
        )
    return out


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _signed_int_or_none(value: Any) -> int | None:
    if not isinstance(value, int):
        return None
    return value - (1 << 64) if value >= (1 << 63) else value



def classify_media(file_details: FileDetails) -> str:
    """Classify a document into the coarse media kinds used by the API layer."""
    mime = (file_details.mime_type or "").lower()
    name = (file_details.name or "").lower()
    if mime.startswith("image/") or _has_suffix(name, {".jpg", ".jpeg", ".png", ".webp", ".gif"}):
        return "photo"
    if mime.startswith("video/") or _has_suffix(name, {".mp4", ".mkv", ".mov", ".avi"}):
        return "video"
    if mime.startswith("audio/") or _has_suffix(name, {".mp3", ".ogg", ".m4a", ".wav"}):
        return "audio"
    return "document"


def _has_suffix(name: str, suffixes: set[str]) -> bool:
    return any(name.endswith(suffix) for suffix in suffixes)


def peer_from_identifier(identifier: int | str) -> Peer:
    """Build a private peer from a numeric user id (Bale user ids are the
    canonical way to address a contact without an access hash)."""
    if isinstance(identifier, str):
        identifier = int(identifier.lstrip("+"))
    return Peer(id=int(identifier), type=PeerType.PRIVATE)


def peer_from_dialog_summary(summary: DialogSummary) -> Peer:
    """Preserve the access hash learned from a dialog for later RPC calls."""
    return summary.peer


def chat_type_from_peer(peer: Peer) -> ChatType:
    if peer.type == PeerType.GROUP:
        return ChatType.GROUP
    return ChatType.PRIVATE
