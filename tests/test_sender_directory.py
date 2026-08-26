from __future__ import annotations

from eitaa_core.infrastructure.codec.tl import TLWriter
from eitaa_core.infrastructure.contacts import constructors as contact_constructors

from eitaa_bridge.infrastructure.eitaa.sender_directory import (
    SQLiteSenderDirectory,
    extract_sender_users,
)


def test_history_sender_directory_extracts_and_persists_human_name(tmp_path):
    user_id = 928374
    flags = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 11)
    encoded_user = (
        TLWriter()
        .write_i32(contact_constructors.USER)
        .write_i32(flags)
        .write_i32(0)
        .write_i32(0)
        .write_i64(user_id)
        .write_string("نام")
        .write_string("نویسنده")
        .write_string("author_name")
        .to_bytes()
    )

    users = extract_sender_users(b"unrelated-prefix" + encoded_user, {user_id, 111})

    assert len(users) == 1
    assert users[0].display_name == "نام نویسنده"
    assert users[0].is_contact is True

    directory = SQLiteSenderDirectory(tmp_path / "sender-directory.sqlite3")
    assert directory.upsert_users(users) == 1
    profiles = directory.profiles((user_id, 111))
    assert profiles[user_id] == {
        "display_name": "نام نویسنده",
        "username": "author_name",
        "is_eitaa_contact": True,
        "resolution": "history_user",
    }
    assert 111 not in profiles
