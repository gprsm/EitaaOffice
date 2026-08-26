from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest
from eitaa_core import Peer, PeerType

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.domain.composer import CompositionRecord
from eitaa_bridge.errors import CoordinatorSchemaError
from eitaa_bridge.infrastructure.composition_store import JsonCompositionStore
from eitaa_bridge.infrastructure.content_index_store import SQLiteContentIndexStore
from eitaa_bridge.infrastructure.coordinator import CoordinatorDatabase
from eitaa_bridge.infrastructure.data_scope import DataScopeError, ProviderAccountScope
from eitaa_bridge.infrastructure.dialog_catalog import JsonDialogCatalog
from eitaa_bridge.infrastructure.eitaa.sender_directory import SQLiteSenderDirectory


def _scope() -> ProviderAccountScope:
    return ProviderAccountScope.for_account(str(uuid4()))


def _composition(*, title: str, post_id: int = 1) -> CompositionRecord:
    return CompositionRecord(
        composition_key="same-composition",
        site_key="main",
        post_id=post_id,
        post_url=None,
        post_slug="same-slug",
        status="draft",
        title=title,
        excerpt="",
        category_ids=(),
        tag_ids=(),
        source_keys=("channel:77:9",),
        source_hashes=("a" * 64,),
        featured_source_key=None,
        featured_media_id=None,
    )


def test_provider_account_scope_is_canonical_and_rejects_cross_scope_keys():
    first, second = _scope(), _scope()
    key = first.key("message", "channel:77", 9)

    assert first.strip("message", key) == "channel:77:9"
    assert first.safe_summary() == {
        "provider": "eitaa",
        "messenger_account_id": first.messenger_account_id,
    }
    with pytest.raises(DataScopeError, match="different account"):
        second.strip("message", key)
    with pytest.raises(DataScopeError):
        ProviderAccountScope.for_account("legacy")


def test_dialog_and_sender_collisions_are_isolated_by_provider_account(tmp_path):
    first, second = _scope(), _scope()
    peer = Peer(id=77, type=PeerType.CHANNEL, access_hash=5, title="Shared ID")
    first_catalog = JsonDialogCatalog(
        tmp_path / "first.json", base_directory=tmp_path, scope=first
    )
    second_catalog = JsonDialogCatalog(
        tmp_path / "second.json", base_directory=tmp_path, scope=second
    )
    first_catalog.upsert(peer=peer, peer_file=tmp_path / "peer.json", source="remote")
    second_catalog.upsert(
        peer=peer,
        peer_file=tmp_path / "peer.json",
        source="remote",
        display_kind="group",
    )

    assert first_catalog.get("channel:77")["display_kind"] == "channel"
    assert second_catalog.get("channel:77")["display_kind"] == "group"
    with pytest.raises(DataScopeError):
        JsonDialogCatalog(
            tmp_path / "first.json", base_directory=tmp_path, scope=second
        ).list()

    sender_path = tmp_path / "senders.sqlite3"
    first_senders = SQLiteSenderDirectory(sender_path, scope=first)
    second_senders = SQLiteSenderDirectory(sender_path, scope=second)
    first_senders.upsert_users(
        [SimpleNamespace(peer=Peer(id=501, type=PeerType.USER), display_name="A", username="a", is_contact=True)]
    )
    second_senders.upsert_users(
        [SimpleNamespace(peer=Peer(id=501, type=PeerType.USER), display_name="B", username="b", is_contact=False)]
    )
    assert first_senders.profiles([501])[501]["display_name"] == "A"
    assert second_senders.profiles([501])[501]["display_name"] == "B"


def test_content_index_keys_include_account_and_same_remote_ids_do_not_collide(tmp_path):
    first, second = _scope(), _scope()
    path = tmp_path / "content.sqlite3"
    first_store = SQLiteContentIndexStore(path, scope=first)
    second_store = SQLiteContentIndexStore(path, scope=second)
    first_store.initialize()
    second_store.initialize()
    first_store.save_results(
        site_key="main",
        peer_type="channel",
        peer_id=77,
        model_version="fake-1",
        rows=[{"message_id": 9, "text_hash": "a" * 64, "predictions": []}],
    )
    second_store.save_results(
        site_key="main",
        peer_type="channel",
        peer_id=77,
        model_version="fake-1",
        rows=[{"message_id": 9, "text_hash": "b" * 64, "predictions": []}],
    )
    first_store.start_run(
        job_id="same-job", site_key="main", peer_type="channel", peer_id=77,
        labels=[], summary={},
    )
    second_store.start_run(
        job_id="same-job", site_key="main", peer_type="channel", peer_id=77,
        labels=[], summary={},
    )
    first_store.add_feedback(
        site_key="main", source_key="channel:77:9", label_id=1,
        label_name="A", decision="accept",
    )

    assert first_store.list_results(site_key="main", peer_type="channel", peer_id=77)[0]["text_hash"] == "a" * 64
    assert second_store.list_results(site_key="main", peer_type="channel", peer_id=77)[0]["text_hash"] == "b" * 64
    assert second_store.list_feedback(site_key="main") == ()
    with sqlite3.connect(path) as connection:
        site_keys = {row[0] for row in connection.execute("SELECT site_key FROM index_results")}
        job_keys = {row[0] for row in connection.execute("SELECT job_id FROM index_runs")}
    assert site_keys == {first.key("content-site", "main"), second.key("content-site", "main")}
    assert job_keys == {first.key("content-job", "same-job"), second.key("content-job", "same-job")}


def test_compositions_are_scoped_by_account_and_app_user_in_one_shared_file(tmp_path):
    first, second = _scope(), _scope()
    user_a, user_b = str(uuid4()), str(uuid4())
    path = tmp_path / "compositions.json"
    first_a = JsonCompositionStore(path, scope=first, owner_app_user_id=user_a)
    first_b = JsonCompositionStore(path, scope=first, owner_app_user_id=user_b)
    second_a = JsonCompositionStore(path, scope=second, owner_app_user_id=user_a)

    first_a.save(_composition(title="first-a", post_id=1))
    first_b.save(_composition(title="first-b", post_id=2))
    second_a.save(_composition(title="second-a", post_id=3))

    assert first_a.get("main", "same-composition").title == "first-a"
    assert first_b.get("main", "same-composition").title == "first-b"
    assert second_a.get("main", "same-composition").title == "second-a"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 3
    assert all("password" not in key.casefold() for key in payload["records"])


def test_wordpress_is_shared_for_active_users_but_management_is_admin_only(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    database.initialize()
    admin, user, disabled = str(uuid4()), str(uuid4()), str(uuid4())
    with sqlite3.connect(database.path) as connection:
        for app_user_id, role, status in (
            (admin, "admin", "active"),
            (user, "user", "active"),
            (disabled, "user", "disabled"),
        ):
            connection.execute(
                """
                INSERT INTO app_users(id,display_name,global_role,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?)
                """,
                (app_user_id, role, role, status, "2026-08-11T00:00:00+00:00", "2026-08-11T00:00:00+00:00"),
            )
    records = database.reconcile_wordpress_integrations(
        [{"integration_key": "main", "display_name": "Shared WordPress"}]
    )

    assert records[0].safe_summary()["integration_key"] == "main"
    assert set(records[0].safe_summary()) == {
        "integration_id", "integration_type", "integration_key", "display_name", "status"
    }
    assert database.require_app_integration_access(
        app_user_id=admin, integration_type="wordpress", integration_key="main", operation="use"
    ).status == "active"
    assert database.require_app_integration_access(
        app_user_id=user, integration_type="wordpress", integration_key="main", operation="use"
    ).status == "active"
    with pytest.raises(CoordinatorSchemaError) as denied:
        database.require_app_integration_access(
            app_user_id=user, integration_type="wordpress", integration_key="main", operation="manage"
        )
    assert denied.value.code == "app_integration_manage_denied"
    with pytest.raises(CoordinatorSchemaError) as inactive:
        database.require_app_integration_access(
            app_user_id=disabled, integration_type="wordpress", integration_key="main"
        )
    assert inactive.value.code == "app_integration_actor_inactive"

    with sqlite3.connect(database.path) as connection:
        persisted = "\n".join(
            str(value or "")
            for row in connection.execute(
                "SELECT integration_key,display_name FROM app_integrations"
            )
            for value in row
        )
    assert "http" not in persisted.casefold()
    assert "password" not in persisted.casefold()


def test_client_writable_account_context_is_rejected_at_any_json_depth():
    rejected = BridgeApplicationApi._untrusted_account_context_fields(
        {
            "body": {"items": [{"messenger_account_id": str(uuid4())}]},
            "query": {"account_id": str(uuid4())},
        }
    )
    assert rejected == {"messenger_account_id", "account_id"}

