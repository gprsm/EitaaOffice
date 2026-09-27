from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from .models import (
    ChatType,
    FileDetails,
    FileUploadInfo,
    FileUrl,
    Message,
    Peer,
    PeerType,
    SendType,
    Update,
)
from .wire import ProtoField, ProtoWriter, get_all, get_first, parse_fields, wrapped_int, wrapped_string


def encode_peer(peer: Peer) -> bytes:
    writer = ProtoWriter().int32(1, int(peer.type)).int64(2, peer.id)
    if peer.access_hash is not None:
        writer.int64(3, peer.access_hash)
    return writer.build()


def decode_peer(data: bytes, *, fallback: Peer | None = None) -> Peer:
    fields = parse_fields(data)
    kind = int(get_first(fields, 1, int(fallback.type) if fallback else int(PeerType.UNKNOWN)))
    peer_id = int(get_first(fields, 2, fallback.id if fallback else 0))
    access_hash = get_first(fields, 3, fallback.access_hash if fallback else None)
    try:
        peer_type = PeerType(kind)
    except ValueError:
        peer_type = PeerType.UNKNOWN
    return Peer(id=peer_id, type=peer_type, access_hash=int(access_hash) if access_hash is not None else None)


def encode_chat(peer: Peer, chat_type: ChatType | None = None) -> bytes:
    if chat_type is None:
        chat_type = ChatType.PRIVATE if peer.type == PeerType.PRIVATE else ChatType.GROUP
    return ProtoWriter().int32(1, int(chat_type)).int64(2, peer.id).build()


def encode_text_content(text: str) -> bytes:
    return ProtoWriter().message(15, ProtoWriter().string(1, text)).build()


def encode_document_content(details: FileDetails) -> bytes:
    doc = (
        ProtoWriter()
        .int64(1, details.file_id)
        .int64(2, details.access_hash)
        .int64(3, details.size)
        .string(4, details.name)
        .string(5, details.mime_type)
    )
    if details.caption:
        doc.message(8, wrapped_string(details.caption))
    return ProtoWriter().message(4, doc).build()


def build_send_message(peer: Peer, random_id: int, content: bytes, *, silent: bool = False) -> bytes:
    writer = (
        ProtoWriter()
        .message(1, encode_peer(peer))
        .int64(2, random_id)
        .message(3, content)
        .message(6, encode_peer(peer))
    )
    if silent:
        writer.bool(7, True)
    return writer.build()


def build_load_history(peer: Peer, *, offset_date: int = (1 << 63) - 1, load_mode: int = 2, limit: int = 20) -> bytes:
    return (
        ProtoWriter()
        .message(1, encode_peer(peer))
        .int64(2, offset_date)
        .int32(4, load_mode)
        .int32(5, limit)
        .build()
    )


def build_load_dialogs(
    *,
    offset_date: int = (1 << 63) - 1,
    min_date: int | None = None,
    limit: int = 20,
    dialog_type: int = 0,
    exclude_pinned: bool = False,
    archive: bool = False,
) -> bytes:
    effective_offset = offset_date if min_date is None else min_date
    writer = ProtoWriter().int64(1, effective_offset).int32(2, limit)
    if dialog_type:
        writer.int32(4, dialog_type)
    if exclude_pinned:
        writer.bool(5, True)
    if archive:
        writer.bool(6, True)
    return writer.build()



def build_update_message(peer: Peer, message_id: int, text: str) -> bytes:
    return (
        ProtoWriter()
        .message(1, encode_peer(peer))
        .int64(2, message_id)
        .message(3, encode_text_content(text))
        .build()
    )


def build_delete_message(
    peer: Peer,
    message_ids: list[int],
    dates: list[int],
    *,
    just_me: bool = False,
) -> bytes:
    writer = ProtoWriter().message(1, encode_peer(peer))
    writer.repeated_varint(2, message_ids)
    writer.message(3, ProtoWriter().repeated_varint(1, dates))
    writer.message(4, wrapped_int(1 if just_me else 0))
    return writer.build()


def build_clear_chat(peer: Peer) -> bytes:
    return ProtoWriter().message(1, encode_peer(peer)).build()


def build_delete_chat(peer: Peer) -> bytes:
    return ProtoWriter().message(1, encode_peer(peer)).build()


def build_set_online(*, online: bool = True, timeout_seconds: int = 120, device_type: int = 3) -> bytes:
    return ProtoWriter().bool(1, online).int32(2, timeout_seconds).int32(3, device_type).build()


def build_typing(peer: Peer, typing_type: int = 1) -> bytes:
    return ProtoWriter().message(1, encode_peer(peer)).int32(3, typing_type).build()


def build_stop_typing(peer: Peer, typing_type: int = 1) -> bytes:
    return ProtoWriter().message(1, encode_peer(peer)).int32(2, typing_type).build()


def build_contact_user(user_id: int, contact_type: int = 1) -> bytes:
    return ProtoWriter().int64(1, user_id).int32(2, contact_type).build()


def build_search_contacts(query: str) -> bytes:
    return ProtoWriter().string(1, query).build()


def build_load_users(users: list[Peer]) -> bytes:
    writer = ProtoWriter()
    for user in users:
        writer.message(1, ProtoWriter().int64(1, user.id).int64(2, user.access_hash or 0))
    return writer.build()


def build_upload_url_request(
    path: str | Path,
    *,
    user_id: int,
    peer: Peer | None,
    send_type: SendType,
    mime_type: str | None = None,
) -> tuple[bytes, str, int, str]:
    p = Path(path)
    size = p.stat().st_size
    mime = mime_type or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    writer = (
        ProtoWriter()
        .int64(1, size)
        .int64(3, user_id)
        .string(4, p.name)
        .string(5, mime)
    )
    if peer is not None:
        writer.message(6, encode_chat(peer))
        writer.message(7, ProtoWriter().int32(1, int(send_type)))
    return writer.build(), p.name, size, mime


def build_get_file_url(details: FileDetails) -> bytes:
    info = (
        ProtoWriter()
        .int64(1, details.file_id)
        .int64(2, details.access_hash)
        .message(3, ProtoWriter().int32(1, 1))
    )
    return ProtoWriter().message(1, info).build()


def decode_upload_info(data: bytes) -> FileUploadInfo:
    fields = parse_fields(data)
    return FileUploadInfo(
        file_id=int(get_first(fields, 1, 0)),
        url=_as_text(get_first(fields, 2, b"")),
        access_hash=(int(get_first(fields, 3)) if get_first(fields, 3) is not None else None),
        chunk_size=int(get_first(fields, 4, 262_144)),
    )


def decode_file_url(data: bytes) -> FileUrl:
    fields = parse_fields(data)
    return FileUrl(
        file_id=int(get_first(fields, 1, 0)),
        url=_as_text(get_first(fields, 2, b"")),
        timeout=int(get_first(fields, 3, 0)),
        chunk_size=int(get_first(fields, 4, 65_536)),
    )


def decode_history(data: bytes, peer: Peer) -> list[Message]:
    fields = parse_fields(data)
    messages: list[Message] = []
    for raw in get_all(fields, 1):
        if isinstance(raw, bytes):
            try:
                messages.append(decode_message(raw, peer))
            except Exception:
                messages.append(Message(peer=peer, sender_id=0, message_id=0, date=0, raw=raw))
    return messages


def decode_message(data: bytes, peer: Peer) -> Message:
    fields = parse_fields(data)
    sender_id = int(get_first(fields, 1, 0))
    message_id = int(get_first(fields, 2, 0))
    date = int(get_first(fields, 3, 0))
    content = get_first(fields, 4, b"")
    text, document = decode_content(content if isinstance(content, bytes) else b"")
    return Message(
        peer=peer,
        sender_id=sender_id,
        message_id=message_id,
        date=date,
        text=text,
        document=document,
        raw=data,
    )


def decode_update_message(data: bytes, peer: Peer | None = None) -> Message:
    fields = parse_fields(data)
    sender_id = int(get_first(fields, 2, 0))
    date = int(get_first(fields, 3, 0))
    message_id = int(get_first(fields, 4, 0))
    content = get_first(fields, 5, b"")
    guessed_peer = peer or Peer(id=sender_id, type=PeerType.PRIVATE)
    text, document = decode_content(content if isinstance(content, bytes) else b"")
    return Message(
        peer=guessed_peer,
        sender_id=sender_id,
        message_id=message_id,
        date=date,
        text=text,
        document=document,
        raw=data,
    )


def decode_content(data: bytes) -> tuple[str | None, FileDetails | None]:
    if not data:
        return None, None
    fields = parse_fields(data)
    text_raw = get_first(fields, 15)
    if isinstance(text_raw, bytes):
        inner = get_first(parse_fields(text_raw), 1)
        if isinstance(inner, bytes):
            return _as_text(inner), None
    for field_number in (4, 7):
        raw = get_first(fields, field_number)
        if isinstance(raw, bytes):
            doc = _decode_document(raw)
            if doc:
                return doc.caption, doc
    raw_13 = get_first(fields, 13)
    if isinstance(raw_13, bytes):
        f13_fields = parse_fields(raw_13)
        inner_content = get_first(f13_fields, 1)
        if isinstance(inner_content, bytes):
            text, doc = decode_content(inner_content)
            if text or doc:
                return text, doc
        f5_raw = get_first(f13_fields, 5)
        if isinstance(f5_raw, bytes):
            for item in parse_fields(f5_raw):
                if isinstance(item.value, bytes):
                    sub = parse_fields(item.value)
                    first_str = get_first(sub, 1)
                    if isinstance(first_str, bytes):
                        t = _as_text(first_str)
                        if t:
                            return t, None
    return None, None



def _decode_document(data: bytes) -> FileDetails | None:
    fields = parse_fields(data)
    file_id = int(get_first(fields, 1, 0))
    access_hash = int(get_first(fields, 2, 0))
    if not file_id:
        return None
    caption_raw = get_first(fields, 8)
    caption: str | None = None
    if isinstance(caption_raw, bytes):
        inner = get_first(parse_fields(caption_raw), 1)
        if isinstance(inner, bytes):
            caption = _as_text(inner)
    return FileDetails(
        file_id=file_id,
        access_hash=access_hash,
        size=int(get_first(fields, 3, 0)),
        name=_as_text(get_first(fields, 4, b"file")),
        mime_type=_as_text(get_first(fields, 5, b"application/octet-stream")),
        caption=caption,
    )


UPDATE_FIELD_KIND: dict[int, str] = {
    4: "message_sent",
    19: "message_read",
    46: "message_deleted",
    47: "chat_cleared",
    48: "chat_deleted",
    50: "read_by_me",
    55: "new_message",
    85: "empty",
    162: "message_edited",
    209: "username_changed",
    210: "about_changed",
    721: "message_pinned",
    722: "message_unpinned",
    2629: "user_blocked",
    2630: "user_unblocked",
}


def decode_update_union(data: bytes) -> list[Update]:
    out: list[Update] = []
    for field in parse_fields(data):
        kind = UPDATE_FIELD_KIND.get(field.number, f"field_{field.number}")
        payload: Any = field.value
        if isinstance(field.value, bytes) and kind in {"message_sent", "new_message", "message_edited"}:
            try:
                payload = decode_update_message(field.value)
            except Exception:
                payload = field.value
        out.append(Update(kind=kind, payload=payload, raw=field.value if isinstance(field.value, bytes) else data))
    return out


def decode_user_records(data: bytes) -> list[dict[str, Any]]:
    # User response models have changed more than the request shape. Preserve raw
    # fields while extracting stable scalar/text values where possible.
    records: list[dict[str, Any]] = []
    for candidate in parse_fields(data):
        if not isinstance(candidate.value, bytes):
            continue
        try:
            fields = parse_fields(candidate.value)
        except Exception:
            continue
        record: dict[str, Any] = {"container_field": candidate.number, "raw_hex": candidate.value.hex()}
        for field in fields:
            if isinstance(field.value, int):
                record[f"f{field.number}"] = field.value
            else:
                text = _as_text_or_none(field.value)
                record[f"f{field.number}"] = text if text is not None else field.value.hex()
        records.append(record)
    return records


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _as_text_or_none(value: bytes) -> str | None:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if all(ch.isprintable() or ch in "\r\n\t" for ch in text) else None
