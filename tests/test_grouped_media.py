from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sqlite3
from types import SimpleNamespace

import pytest

from eitaa_core import MediaReference, MediaType, Message, Peer, PeerType
from eitaa_core.errors import MessageStoreError
from eitaa_core.infrastructure.codec.tl import TLWriter
from eitaa_core.infrastructure.history import constructors as c
from eitaa_core.infrastructure.history.response import HistoryResponseCodec
from eitaa_core.infrastructure.persistence.sqlite_messages import SQLiteMessageRepository

from eitaa_bridge.facade import EitaaBridge


PEER = Peer(id=88001, type=PeerType.CHANNEL, access_hash=123)


def _layer134_message(
    message_id: int,
    grouped_id: int,
    *,
    text: str = "گزارش فعالیت",
    entity_constructor: int = 0xBD610BC9,
) -> bytes:
    flags = (1 << 9) | (1 << 7) | (1 << 10) | (1 << 15) | (1 << 16) | (1 << 17)
    writer = TLWriter()
    writer.write_i32(c.MESSAGE)
    writer.write_i32(flags)
    writer.write_i32(message_id)
    writer.write_i32(c.PEER_CHANNEL)
    writer.write_i64(PEER.id)
    writer.write_i32(1_720_000_000)
    writer.write_string(text)
    writer.write_i32(c.MESSAGE_MEDIA_PHOTO)
    writer.write_i32(0)
    writer.write_i32(c.VECTOR)
    writer.write_i32(1)
    writer.write_i32(entity_constructor)
    writer.write_i32(0)
    writer.write_i32(len(text))
    writer.write_i32(14)
    writer.write_i32(2)
    writer.write_i32(1_720_000_100)
    writer.write_string("واحد گزارش")
    writer.write_i64(grouped_id)
    return writer.to_bytes()


def _history_payload(*messages: bytes) -> bytes:
    writer = TLWriter()
    writer.write_i32(c.MESSAGES_MESSAGES)
    writer.write_i32(c.VECTOR)
    writer.write_i32(len(messages))
    for message in messages:
        writer.write_raw(message)
    return writer.to_bytes()


def _create_schema8_database(path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE peers (
                peer_type TEXT NOT NULL,
                peer_id INTEGER NOT NULL,
                access_hash INTEGER,
                username TEXT,
                title TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (peer_type, peer_id)
            );
            CREATE TABLE messages (
                peer_type TEXT NOT NULL,
                peer_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                date_utc TEXT NOT NULL,
                text TEXT NOT NULL,
                outgoing INTEGER NOT NULL DEFAULT 0,
                from_peer_type TEXT,
                from_peer_id INTEGER,
                reply_to_message_id INTEGER,
                flags INTEGER NOT NULL DEFAULT 0,
                parse_warning TEXT,
                media_json TEXT,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (peer_type, peer_id, message_id)
            );
            PRAGMA user_version = 8;
            """
        )
    finally:
        connection.close()


def test_layer134_decoder_retains_grouped_id_after_entities_and_channel_metadata():
    payload = _history_payload(
        _layer134_message(101, 987654321),
        _layer134_message(102, 987654321),
    )
    page = HistoryResponseCodec.parse(payload, PEER)
    assert [message.id for message in page.messages] == [102, 101]
    assert {message.grouped_id for message in page.messages} == {987654321}
    assert all(message.media and message.media.type is MediaType.PHOTO for message in page.messages)
    assert all(message.parse_warning is None for message in page.messages)


def test_unknown_entity_keeps_message_and_records_safe_grouped_metadata_warning():
    page = HistoryResponseCodec.parse(
        _history_payload(_layer134_message(101, 987654321, entity_constructor=0x01020304)),
        PEER,
    )
    assert page.messages[0].id == 101
    assert page.messages[0].grouped_id is None
    assert page.messages[0].parse_warning == "grouped_id:UnexpectedConstructorError"


def test_schema8_migration_is_transactional_and_creates_recovery_backup(tmp_path):
    path = tmp_path / "messages.sqlite3"
    _create_schema8_database(path)
    repository = SQLiteMessageRepository(path)
    repository.initialize()
    repository.close()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
        columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
        assert "grouped_id" in columns

    backup = tmp_path / "messages.sqlite3.pre-schema9-v8.bak"
    assert backup.exists()
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
        assert "grouped_id" not in columns


def test_failed_schema9_migration_rolls_back_and_leaves_backup(tmp_path, monkeypatch):
    path = tmp_path / "messages.sqlite3"
    _create_schema8_database(path)

    def fail_migration(connection):
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            ALTER TABLE messages ADD COLUMN grouped_id INTEGER;
            SELECT * FROM table_that_does_not_exist;
            COMMIT;
            """
        )

    monkeypatch.setattr(
        SQLiteMessageRepository, "_migrate_v9", staticmethod(fail_migration)
    )
    with pytest.raises(MessageStoreError):
        SQLiteMessageRepository(path).initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
        assert "grouped_id" not in columns
    assert (tmp_path / "messages.sqlite3.pre-schema9-v8.bak").exists()


def test_album_lookup_and_metadata_only_update_preserve_content_hash(tmp_path):
    repository = SQLiteMessageRepository(tmp_path / "fresh.sqlite3")
    repository.initialize()
    base = Message(
        id=201,
        peer=PEER,
        date=datetime.now(timezone.utc),
        text="کپشن",
        media=MediaReference(MediaType.PHOTO, remote_id=1),
    )
    repository.upsert_many((base,))
    original_hash = repository.content_hash(PEER, 201)
    updated = repository.upsert_many((replace(base, grouped_id=4444),))
    sibling = replace(base, id=202, text="", grouped_id=4444)
    repository.upsert_many((sibling,))

    assert updated.updated == 1
    assert repository.content_hash(PEER, 201) == original_hash
    assert [message.id for message in repository.list_by_grouped_id(PEER, 4444)] == [201, 202]
    repository.close()


def test_bridge_completes_album_crossing_page_boundary_and_serializes_album_size():
    first = Message(
        id=301,
        peer=PEER,
        date=datetime.now(timezone.utc),
        text="کپشن",
        media=MediaReference(MediaType.PHOTO, remote_id=1),
        grouped_id=5555,
    )
    second = replace(first, id=302, text="", media=MediaReference(MediaType.PHOTO, remote_id=2))

    class Harness:
        _application_message_item = EitaaBridge._application_message_item
        _application_message_items = EitaaBridge._application_message_items
        _expand_local_albums = EitaaBridge._expand_local_albums
        core = SimpleNamespace(
            messages=SimpleNamespace(list_album=lambda peer, grouped_id: (first, second))
        )

        @staticmethod
        def wordpress_message_usage_details(peer, message_id):
            return {
                "used": False,
                "usage_state": "unused",
                "stale": False,
                "compositions": [],
            }

    harness = Harness()
    expanded = harness._expand_local_albums(PEER, (second,))
    items = harness._application_message_items(PEER, expanded)
    assert [message.id for message in expanded] == [302, 301]
    assert {item["grouped_id"] for item in items} == {5555}
    assert {item["album_size"] for item in items} == {2}
