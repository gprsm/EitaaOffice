from __future__ import annotations

import json
from uuid import uuid4

from eitaa_core import Peer, PeerType, save_peer_file

from eitaa_bridge.infrastructure.data_scope import ProviderAccountScope
from eitaa_bridge.infrastructure.dialog_catalog import JsonDialogCatalog


def test_dialog_catalog_persists_manual_kind_and_favorite(tmp_path):
    peer = Peer(id=42, type=PeerType.CHANNEL, access_hash=99, title="گروه نمونه")
    peer_file = tmp_path / "peers" / "channel-42.json"
    peer_file.parent.mkdir()
    save_peer_file(peer_file, peer)
    catalog = JsonDialogCatalog(tmp_path / "data" / "catalog.json", base_directory=tmp_path)

    created = catalog.upsert(peer=peer, peer_file=peer_file, source="manual", display_kind="group")
    catalog.set_favorite(created["peer_key"], True)
    catalog.set_display_kind(created["peer_key"], "group")

    reopened = JsonDialogCatalog(tmp_path / "data" / "catalog.json", base_directory=tmp_path)
    item = reopened.list()[0]
    assert item["display_kind"] == "group"
    assert item["display_kind_locked"] is True
    assert item["favorite"] is True
    assert item["peer_file"] == "peers/channel-42.json"


def test_remote_refresh_does_not_overwrite_locked_group_override(tmp_path):
    peer = Peer(id=50, type=PeerType.CHANNEL, access_hash=1, title="سوپرگروه")
    peer_file = tmp_path / "channel-50.json"
    save_peer_file(peer_file, peer)
    catalog = JsonDialogCatalog(tmp_path / "catalog.json", base_directory=tmp_path)
    item = catalog.upsert(peer=peer, peer_file=peer_file, source="remote")
    catalog.set_display_kind(item["peer_key"], "group")

    refreshed = catalog.upsert(peer=peer, peer_file=peer_file, source="remote", top_message_id=100)
    assert refreshed["display_kind"] == "group"
    assert refreshed["display_kind_locked"] is True
    assert refreshed["top_message_id"] == 100


def test_dialog_catalog_deduplicates_same_peer_key(tmp_path):
    peer = Peer(id=77, type=PeerType.CHANNEL, access_hash=5, title="نمونه")
    peer_file = tmp_path / "channel-77.json"
    save_peer_file(peer_file, peer)
    catalog = JsonDialogCatalog(tmp_path / "catalog.json", base_directory=tmp_path)

    catalog.upsert(peer=peer, peer_file=peer_file, source="remote", top_message_id=10)
    catalog.upsert(peer=peer, peer_file=peer_file, source="remote", top_message_id=20)

    items = catalog.list()
    assert len(items) == 1
    assert items[0]["peer_key"] == "channel:77"
    assert items[0]["top_message_id"] == 20


def test_dialog_catalog_migrates_schema1_and_preserves_ui_metadata(tmp_path):
    peer = Peer(id=88, type=PeerType.CHANNEL, access_hash=7, title="قدیمی")
    peer_file = tmp_path / "channel-88.json"
    save_peer_file(peer_file, peer)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "dialogs": {
            "channel:88": {
                "peer_key": "channel:88",
                "peer": {**peer.safe_summary(), "title": peer.title, "username": None},
                "peer_file": "channel-88.json",
                "display_kind": "group",
                "display_kind_locked": True,
                "favorite": True,
                "source": "remote",
                "top_message_id": 10,
                "unread_count": 0,
                "unread_mentions_count": 0,
                "pinned": False,
                "unread_mark": False,
                "folder_id": None,
            }
        },
    }), encoding="utf-8")

    catalog = JsonDialogCatalog(path, base_directory=tmp_path)
    item = catalog.upsert(
        peer=peer, peer_file=peer_file, source="remote", technical_kind="supergroup",
        top_message_id=20, top_message_date=100, unread_count=3, megagroup=True,
    )
    assert item["display_kind"] == "group"
    assert item["display_kind_locked"] is True
    assert item["favorite"] is True
    assert item["technical_kind"] == "supergroup"
    assert item["top_message_id"] == 20
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2


def test_account_catalog_repairs_only_copied_legacy_peer_paths(tmp_path):
    account_id = str(uuid4())
    scope = ProviderAccountScope.for_account(account_id)
    legacy_root = tmp_path / "data" / "ui-peers"
    account_root = (
        tmp_path / "data" / "accounts" / account_id
        / "provider" / "state" / "ui-peers"
    )
    legacy_root.mkdir(parents=True)
    account_root.mkdir(parents=True)
    peer = Peer(id=91, type=PeerType.CHANNEL, access_hash=12, title="Migrated")
    legacy_peer = legacy_root / "channel-91.json"
    copied_peer = account_root / legacy_peer.name
    save_peer_file(legacy_peer, peer)
    save_peer_file(copied_peer, peer)
    catalog_path = account_root / "catalog.json"
    catalog = JsonDialogCatalog(
        catalog_path,
        base_directory=tmp_path,
        scope=scope,
    )
    catalog.upsert(peer=peer, peer_file=legacy_peer, source="remote")

    assert catalog.repair_migrated_peer_paths() == 1
    repaired = catalog.get("channel:91")
    assert repaired is not None
    assert repaired["peer_file"] == copied_peer.relative_to(tmp_path).as_posix()
    assert catalog.repair_migrated_peer_paths() == 0


def test_account_catalog_does_not_rebase_when_copied_peer_is_missing(tmp_path):
    account_id = str(uuid4())
    scope = ProviderAccountScope.for_account(account_id)
    legacy_root = tmp_path / "data" / "ui-peers"
    account_root = (
        tmp_path / "data" / "accounts" / account_id
        / "provider" / "state" / "ui-peers"
    )
    legacy_root.mkdir(parents=True)
    account_root.mkdir(parents=True)
    peer = Peer(id=92, type=PeerType.CHANNEL, access_hash=13, title="Missing copy")
    legacy_peer = legacy_root / "channel-92.json"
    save_peer_file(legacy_peer, peer)
    catalog = JsonDialogCatalog(
        account_root / "catalog.json",
        base_directory=tmp_path,
        scope=scope,
    )
    created = catalog.upsert(peer=peer, peer_file=legacy_peer, source="remote")

    assert catalog.repair_migrated_peer_paths() == 0
    assert catalog.get("channel:92")["peer_file"] == created["peer_file"]
