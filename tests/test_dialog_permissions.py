from __future__ import annotations

import struct

from eitaa_core.infrastructure.codec.tl import TLReader
from eitaa_core.infrastructure.discovery import constructors as c

from eitaa_bridge.infrastructure.eitaa.dialog_permissions import (
    dialog_account_role_hint,
    is_manageable_account_role,
)


def _metadata_header(constructor: int, flags: int, peer_id: int) -> TLReader:
    return TLReader(struct.pack("<IIq", constructor, flags, peer_id))


def test_channel_role_hint_distinguishes_owner_admin_and_member() -> None:
    assert dialog_account_role_hint(_metadata_header(c.CHANNEL, 1, 101)) == (
        "channel:101", "owner"
    )
    assert dialog_account_role_hint(
        _metadata_header(c.CHANNEL, 1 << 14, 102)
    ) == ("channel:102", "admin")
    assert dialog_account_role_hint(_metadata_header(c.CHANNEL, 0, 103)) == (
        "channel:103", "member"
    )
    assert is_manageable_account_role("owner") is True
    assert is_manageable_account_role("admin") is True
    assert is_manageable_account_role("member") is False


def test_basic_group_role_hint_is_fail_closed_except_for_creator() -> None:
    assert dialog_account_role_hint(_metadata_header(c.CHAT, 1, 201)) == (
        "chat:201", "owner"
    )
    assert dialog_account_role_hint(_metadata_header(c.CHAT, 0, 202)) == (
        "chat:202", "unknown"
    )
    assert dialog_account_role_hint(TLReader(struct.pack("<Iq", c.CHAT_FORBIDDEN, 203))) == (
        "chat:203", "unknown"
    )
    assert is_manageable_account_role("unknown") is False
