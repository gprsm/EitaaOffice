"""Capture safe current-account management hints from pinned Core dialog data.

Core 7.4.5 parses the owner/admin flags needed by the UI but intentionally does
not expose them on ``DialogEntry``.  This narrow compatibility hook observes
the already-validated peer metadata parse and publishes only a fail-closed role
summary.  It does not retain raw provider payloads or account identifiers.
"""

from __future__ import annotations

from contextvars import ContextVar
from threading import RLock
from typing import Literal

from eitaa_core.infrastructure.codec.tl import TLReader
from eitaa_core.infrastructure.discovery import constructors as c
from eitaa_core.infrastructure.discovery.codec import DiscoveryCodec


DialogAccountRole = Literal["owner", "admin", "member", "unknown"]

_active_roles: ContextVar[dict[str, DialogAccountRole] | None] = ContextVar(
    "eitaa_bridge_active_dialog_roles", default=None
)
_latest_roles: ContextVar[dict[str, DialogAccountRole]] = ContextVar(
    "eitaa_bridge_latest_dialog_roles", default={}
)
_install_lock = RLock()


def dialog_account_role_hint(
    reader: TLReader,
) -> tuple[str, DialogAccountRole] | None:
    """Read only the stable constructor/flags/id prefix from a cloned reader."""

    probe = reader.clone()
    try:
        constructor = probe.read_u32()
        if constructor == c.CHANNEL:
            flags = probe.read_u32()
            peer_id = probe.read_i64()
            role: DialogAccountRole = (
                "owner"
                if flags & 1
                else "admin"
                if flags & (1 << 14)
                else "member"
            )
            return f"channel:{peer_id}", role
        if constructor == c.CHAT:
            flags = probe.read_u32()
            peer_id = probe.read_i64()
            # The basic Chat constructor exposes creator but not a reliable
            # current-account administrator marker in this pinned Core layer.
            return f"chat:{peer_id}", "owner" if flags & 1 else "unknown"
        if constructor == c.CHAT_EMPTY:
            return f"chat:{probe.read_i64()}", "unknown"
        if constructor == c.CHAT_FORBIDDEN:
            return f"chat:{probe.read_i64()}", "unknown"
        if constructor == c.CHANNEL_FORBIDDEN:
            probe.read_u32()  # flags
            return f"channel:{probe.read_i64()}", "unknown"
    except Exception:
        return None
    return None


def is_manageable_account_role(value: object) -> bool:
    return value in {"owner", "admin"}


def consume_dialog_account_roles() -> dict[str, DialogAccountRole]:
    """Return and clear roles captured by the latest parse in this context."""

    roles = dict(_latest_roles.get())
    _latest_roles.set({})
    return roles


def install_dialog_permission_capture() -> None:
    """Install the idempotent pinned-Core compatibility hook."""

    with _install_lock:
        if getattr(DiscoveryCodec, "_bridge_dialog_role_capture", False):
            return

        original_parse_dialogs = DiscoveryCodec.parse_dialogs
        original_parse_peer_metadata = DiscoveryCodec._parse_peer_metadata

        def parse_peer_metadata(reader: TLReader):
            hint = dialog_account_role_hint(reader)
            metadata = original_parse_peer_metadata(reader)
            roles = _active_roles.get()
            if hint is not None and roles is not None:
                peer_key, role = hint
                actual_key = f"{metadata.peer.type.value}:{metadata.peer.id}"
                if actual_key == peer_key and metadata.peer.id > 0:
                    previous = roles.get(peer_key)
                    roles[peer_key] = (
                        role if previous in {None, role} else "unknown"
                    )
            return metadata

        def parse_dialogs(data: bytes):
            token = _active_roles.set({})
            try:
                page = original_parse_dialogs(data)
                _latest_roles.set(dict(_active_roles.get() or {}))
                return page
            finally:
                _active_roles.reset(token)

        DiscoveryCodec._parse_peer_metadata = staticmethod(parse_peer_metadata)
        DiscoveryCodec.parse_dialogs = staticmethod(parse_dialogs)
        DiscoveryCodec._bridge_dialog_role_capture = True
