from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from enum import IntEnum
from typing import Any


class PeerType(IntEnum):
    UNKNOWN = 0
    PRIVATE = 1
    GROUP = 2


class ChatType(IntEnum):
    UNKNOWN = 0
    PRIVATE = 1
    GROUP = 2
    CHANNEL = 3
    BOT = 4
    SUPERGROUP = 5


class SendType(IntEnum):
    UNKNOWN = 0
    PHOTO = 1
    VIDEO = 2
    VOICE = 3
    GIF = 4
    AUDIO = 5
    DOCUMENT = 6
    STICKER = 7


@dataclass(slots=True)
class Peer:
    id: int
    type: PeerType = PeerType.PRIVATE
    access_hash: int | None = None


@dataclass(slots=True)
class BaleSession:
    access_token: str
    jwt: str | None = None
    user_id: int | None = None
    auth_id: str | None = None
    auth_sid: int | None = None
    expires_at: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BaleSession":
        return cls(**value)


@dataclass(slots=True)
class AuthStart:
    transaction_hash: str
    is_registered: bool


@dataclass(slots=True)
class FileDetails:
    file_id: int
    access_hash: int
    name: str
    size: int
    mime_type: str
    caption: str | None = None


@dataclass(slots=True)
class FileUploadInfo:
    file_id: int
    url: str
    access_hash: int | None = None
    chunk_size: int = 262_144


@dataclass(slots=True)
class FileUrl:
    file_id: int
    url: str
    timeout: int = 0
    chunk_size: int = 65_536


@dataclass(slots=True)
class Message:
    peer: Peer
    sender_id: int
    message_id: int
    date: int
    text: str | None = None
    document: FileDetails | None = None
    raw: bytes | None = None


@dataclass(slots=True)
class Update:
    kind: str
    payload: Any
    raw: bytes


def decode_jwt_payload(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) < 2:
        return None
    try:
        raw = parts[1] + "=" * (-len(parts[1]) % 4)
        value = json.loads(base64.urlsafe_b64decode(raw).decode("utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def session_from_tokens(access_token: str, jwt: str | None = None) -> BaleSession:
    payload = decode_jwt_payload(jwt or access_token) or {}
    inner = payload.get("payload")
    data = inner if isinstance(inner, dict) else payload

    def as_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return BaleSession(
        access_token=access_token,
        jwt=jwt,
        user_id=as_int(data.get("user_id") or data.get("userId")),
        auth_id=str(data.get("auth_id")) if data.get("auth_id") is not None else None,
        auth_sid=as_int(data.get("auth_sid")),
        expires_at=as_int(payload.get("exp")),
    )
