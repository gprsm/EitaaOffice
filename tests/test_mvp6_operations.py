from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from eitaa_core import Peer, PeerType, save_peer_file

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.facade import EitaaBridge


class Context:
    def __init__(self, bridge):
        self.bridge = bridge

    def __enter__(self):
        return self.bridge

    def __exit__(self, exc_type, exc, tb):
        return False


class Summary:
    def __init__(self, payload):
        self.payload = payload

    def safe_summary(self):
        return self.payload


def test_mvp6_schema_exposes_bulk_and_site_settings(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    routes = api.dispatch("GET", "/api/v1/schema").payload["routes"]
    assert {"method": "GET", "path": "/api/v1/settings/sites"} in routes
    assert {"method": "POST", "path": "/api/v1/community/bulk/create"} in routes
    assert {"method": "POST", "path": "/api/v1/community/members/remove/start"} in routes
    assert {"method": "POST", "path": "/api/v1/community/members/invite/start"} in routes
    assert {"method": "POST", "path": "/api/v1/phone-lists/import"} in routes
    assert {"method": "POST", "path": "/api/v1/membership/run"} in routes


def test_site_settings_upsert_writes_config_env_and_backup(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    env_file = config_file.parent / ".env"
    env_file.write_text("TEST_WP_USERNAME=editor\nTEST_WP_APP_PASSWORD=password\n", encoding="utf-8")
    api = BridgeApplicationApi(config_file)

    response = api.dispatch(
        "POST",
        "/api/v1/settings/sites/upsert",
        body={
            "site_key": "second-site",
            "base_url": "https://second.example.test",
            "default_status": "draft",
            "default_category_id": None,
            "verify_tls": True,
            "retry_attempts": 2,
            "timeout_seconds": 15,
            "username": "news-editor",
            "application_password": "app-password",
            "is_default": True,
        },
    )

    assert response.status == 200
    assert response.payload["default_site_key"] == "second-site"
    second = next(item for item in response.payload["sites"] if item["site_key"] == "second-site")
    assert second["credentials_configured"] is True
    raw = json.loads(config_file.read_text(encoding="utf-8"))
    assert raw["default_site_key"] == "second-site"
    assert len(raw["wordpress_sites"]) == 2
    env_text = env_file.read_text(encoding="utf-8")
    assert "EITAA_BRIDGE_WP_SECOND_SITE_USERNAME=news-editor" in env_text
    assert "EITAA_BRIDGE_WP_SECOND_SITE_APP_PASSWORD=app-password" in env_text
    assert list((config_file.parent / "backups" / "settings").glob("bridge.*.json"))


def test_site_settings_do_not_return_saved_secret(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    (config_file.parent / ".env").write_text(
        "TEST_WP_USERNAME=editor\nTEST_WP_APP_PASSWORD=secret-value\n", encoding="utf-8"
    )
    response = BridgeApplicationApi(config_file).dispatch("GET", "/api/v1/settings/sites")
    serialized = json.dumps(response.payload)
    assert "secret-value" not in serialized
    assert response.payload["sites"][0]["credentials_configured"] is True


def test_community_bulk_preview_uses_public_core_service(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "group.json"
    save_peer_file(peer_file, Peer(id=44, type=PeerType.CHANNEL, access_hash=123))
    captured = {}

    class Bulk:
        def preview(self, community, **kwargs):
            captured["peer"] = community
            captured["kwargs"] = kwargs
            return Summary({"eligible_count": 12, "selected_count": 5, "skipped_unsendable": 1})

    fake = SimpleNamespace(core=SimpleNamespace(bulk_send=Bulk()))
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    response = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/community/bulk/preview",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "test_limit": 5,
            "include_bots": False,
        },
    )
    assert response.status == 200
    assert response.payload["preview"]["selected_count"] == 5
    assert captured["peer"].id == 44
    assert captured["kwargs"]["test_limit"] == 5
    assert captured["kwargs"]["member_ids"] is None

    selected = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/community/bulk/preview",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "member_scope": "selected",
            "member_ids": [9, 9, 10],
        },
    )
    assert selected.status == 200
    assert captured["kwargs"]["member_ids"] == [9, 10]


def test_phone_list_import_accepts_pasted_numbers(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    captured = {}

    class PhoneLists:
        def import_file(self, source, **kwargs):
            captured["source"] = Path(source)
            captured["content"] = Path(source).read_text(encoding="utf-8")
            return Summary({"id": "phones-1", "name": kwargs["name"], "valid_unique": 2})

    fake = SimpleNamespace(core=SimpleNamespace(phone_lists=PhoneLists()))
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    response = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/phone-lists/import",
        body={
            "site_key": "medical-site",
            "name": "اداره",
            "numbers": "+989121111111\n+989122222222",
        },
    )
    assert response.status == 201
    assert response.payload["phone_list"]["id"] == "phones-1"
    assert "+989121111111" in captured["content"]
    assert captured["source"].suffix == ".txt"


def test_bulk_create_validates_text_and_uses_core(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "group.json"
    save_peer_file(peer_file, Peer(id=44, type=PeerType.CHANNEL, access_hash=123))
    captured = {}

    class Bulk:
        def create_job(self, community, spec, options, **kwargs):
            captured["spec"] = spec
            captured["options"] = options
            return Summary({"id": "job-1", "recipient_count": 10, "status": "draft"})

    fake = SimpleNamespace(core=SimpleNamespace(bulk_send=Bulk()))
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    response = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/community/bulk/create",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "kind": "text",
            "text": "پیام آزمایشی",
            "delay_seconds": 1.5,
            "test_limit": 10,
        },
    )
    assert response.status == 201
    assert response.payload["job"]["id"] == "job-1"
    assert captured["spec"].text == "پیام آزمایشی"
    assert captured["options"].test_limit == 10


def test_site_settings_reject_credential_line_breaks_before_write(config_file, monkeypatch):
    from eitaa_bridge.infrastructure.config import WordPressSiteSettings
    from eitaa_bridge.errors import BridgeConfigurationError

    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    original = config_file.read_text(encoding="utf-8")
    settings = WordPressSiteSettings(config_file, config_file.parent / ".env")
    try:
        settings.upsert({
            "site_key": "medical-site",
            "base_url": "https://example.test",
            "username_env": "TEST_WP_USERNAME",
            "application_password_env": "TEST_WP_APP_PASSWORD",
            "application_password": "line1\nline2",
        })
    except BridgeConfigurationError:
        pass
    else:
        raise AssertionError("line-breaking credential should be rejected")
    assert config_file.read_text(encoding="utf-8") == original


def test_ui3_schema_exposes_dialog_operation_routes(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    routes = BridgeApplicationApi(config_file).dispatch("GET", "/api/v1/schema").payload["routes"]
    assert {"method": "POST", "path": "/api/v1/community/members/sync/start"} in routes
    assert {"method": "POST", "path": "/api/v1/community/bulk/validate"} in routes
    assert {"method": "POST", "path": "/api/v1/community/bulk/recipients"} in routes


def test_ui3_member_list_returns_safe_members(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "group.json"
    save_peer_file(peer_file, Peer(id=44, type=PeerType.CHANNEL, access_hash=123))

    class Member:
        user = SimpleNamespace(
            peer=Peer(id=501, type=PeerType.USER, access_hash=987),
            is_contact=True,
        )

        def safe_summary(self):
            return {
                "user": {
                    "peer": {"id": 501, "type": "user"},
                    "display_name": "Member One",
                    "is_contact": True,
                },
                "role": "member",
                "state": "active",
                "sendable": True,
            }

    class Page:
        members = (Member(),)
        total_count = 1

        def safe_summary(self):
            return {"count": 1, "total_count": 1, "offset": 0, "limit": 100, "next_offset": None}

    class Members:
        def search_local(self, query):
            assert query.community.id == 44
            return Page()

    fake = SimpleNamespace(core=SimpleNamespace(members=Members()))
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    api = BridgeApplicationApi(config_file)
    api._contact_store.upsert_contact({
        "first_name": "نام",
        "last_name": "دفترچه",
        "eitaa_user_id": 501,
        "source": "eitaa_contact_sync",
        "phones": [],
    })
    response = api.dispatch(
        "POST",
        "/api/v1/community/members/list",
        body={"site_key": "medical-site", "peer_file": str(peer_file), "limit": 100},
    )
    assert response.status == 200
    assert response.payload["page"]["members"][0]["user"]["display_name"] == "Member One"
    assert response.payload["page"]["members"][0]["contact"]["state"] == "eitaa"
    assert response.payload["page"]["members"][0]["contact"]["is_eitaa_contact"] is True
    assert response.payload["page"]["members"][0]["contact"]["display_name"] == "نام دفترچه"
    assert response.payload["page"]["snapshot_total_count"] == 1


def test_ui3_bulk_media_preflight_reports_file_metadata(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    selected = tmp_path / "report.pdf"
    selected.write_bytes(b"pdf-test")
    response = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/community/bulk/validate",
        body={
            "site_key": "medical-site",
            "kind": "file",
            "file_path": str(selected),
            "caption": "caption",
        },
    )
    assert response.status == 200
    assert response.payload["file"]["name"] == "report.pdf"
    assert response.payload["file"]["size_bytes"] == 8
    assert response.payload["file"]["mime_type"] == "application/pdf"


def test_ui3_photo_preflight_rejects_non_image(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    selected = tmp_path / "report.pdf"
    selected.write_bytes(b"pdf-test")
    response = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/community/bulk/validate",
        body={"site_key": "medical-site", "kind": "photo", "file_path": str(selected)},
    )
    assert response.status == 400
    assert response.payload["error"]["error_code"] == "api_photo_requires_image"


def test_ui3_bulk_recipient_failures_are_exposed_safely(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")

    class Recipient:
        def safe_summary(self):
            return {
                "user": {"peer": {"id": 701, "type": "user"}, "display_name": "Failed Member"},
                "status": "failed",
                "error_code": "RPC_400_FILE_PART_INVALID",
                "error_type": "RpcError",
            }

    class Bulk:
        def recipients(self, job_id, *, status=None, limit=1000):
            assert job_id == "job-file-1"
            assert status.value == "failed"
            assert limit == 25
            return (Recipient(),)

    fake = SimpleNamespace(core=SimpleNamespace(bulk_send=Bulk()))
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    response = BridgeApplicationApi(config_file).dispatch(
        "POST",
        "/api/v1/community/bulk/recipients",
        body={"site_key": "medical-site", "job_id": "job-file-1", "status": "failed", "limit": 25},
    )
    assert response.status == 200
    assert response.payload["recipients"][0]["error_code"] == "RPC_400_FILE_PART_INVALID"


def test_ui3_members_sync_start_is_non_blocking_and_uses_core(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "group.json"
    save_peer_file(peer_file, Peer(id=44, type=PeerType.CHANNEL, access_hash=123))
    captured = {}

    class Members:
        def sync_all(self, community, **kwargs):
            captured["community"] = community
            captured["kwargs"] = kwargs
            return Summary({"fetched": 12, "complete_snapshot": True})

    fake = SimpleNamespace(core=SimpleNamespace(members=Members()))
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    api = BridgeApplicationApi(config_file)

    def immediate(*, kind, callback, priority):
        captured["kind"] = kind
        captured["result"] = callback()
        return {"ok": True, "task": {"task_id": "sync-task", "status": "queued"}}

    monkeypatch.setattr(api, "_start_background", immediate)
    response = api.dispatch(
        "POST",
        "/api/v1/community/members/sync/start",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "page_size": 100,
            "expected_total": 20,
        },
    )
    assert response.status == 202
    assert captured["kind"] == "community.members.sync"
    assert captured["community"].id == 44
    assert captured["result"]["sync"]["fetched"] == 12
    assert captured["kwargs"]["expected_total"] == 20
    assert captured["result"]["sync"]["expected_total"] == 20
    assert captured["result"]["sync"]["missing_count"] == 8


def test_member_remove_start_requires_confirmation_and_processes_selected_members(
    config_file, tmp_path, monkeypatch
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "source-group.json"
    source = Peer(id=44, type=PeerType.CHANNEL, access_hash=123)
    user_peer = Peer(id=501, type=PeerType.USER, access_hash=987)
    save_peer_file(peer_file, source)
    captured = {"marked": []}
    member = SimpleNamespace(
        user=SimpleNamespace(is_bot=False),
        send_peer=user_peer,
    )

    class MemberStore:
        def mark_member_left(self, community, user_id):
            captured["marked"].append((community.id, user_id))

    class Members:
        store = MemberStore()

        @staticmethod
        def get(community, user_id):
            return member if community.id == 44 and user_id == 501 else None

    class Remote:
        @staticmethod
        def remove_member(community, user, **kwargs):
            captured["removed"] = (community.id, user.id, kwargs)
            return SimpleNamespace(accepted=True)

    fake = SimpleNamespace(
        core=SimpleNamespace(
            members=Members(),
            membership=SimpleNamespace(remote=Remote()),
        )
    )
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    api = BridgeApplicationApi(config_file)

    rejected = api.dispatch(
        "POST",
        "/api/v1/community/members/remove/start",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "member_ids": [501],
        },
    )
    assert rejected.status == 400

    def immediate(*, kind, callback, priority):
        captured["kind"] = kind
        captured["result"] = callback()
        return {"ok": True, "task": {"task_id": "remove-task", "status": "queued"}}

    monkeypatch.setattr(api, "_start_background", immediate)
    response = api.dispatch(
        "POST",
        "/api/v1/community/members/remove/start",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "member_ids": [501],
            "delay_seconds": 0,
            "confirm": True,
        },
    )
    assert response.status == 202
    assert captured["kind"] == "community.members.remove"
    assert captured["result"]["report"]["succeeded"] == 1
    assert captured["removed"][0:2] == (44, 501)
    assert captured["marked"] == [(44, 501)]


def test_member_invite_all_syncs_complete_snapshot_and_uses_every_local_page(
    config_file, tmp_path, monkeypatch
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    source_file = tmp_path / "source.json"
    target_file = tmp_path / "target.json"
    source = Peer(id=44, type=PeerType.CHANNEL, access_hash=123)
    target = Peer(id=55, type=PeerType.CHANNEL, access_hash=456)
    save_peer_file(source_file, source)
    save_peer_file(target_file, target)
    invited: list[tuple[int, int]] = []
    members = tuple(
        SimpleNamespace(
            user=SimpleNamespace(is_bot=False),
            send_peer=Peer(id=user_id, type=PeerType.USER, access_hash=1000 + user_id),
        )
        for user_id in (501, 502)
    )

    class Members:
        @staticmethod
        def sync_all(community, **kwargs):
            assert community.id == 44
            assert kwargs["max_pages"] == 10_000
            return SimpleNamespace(
                complete_snapshot=True,
                safe_summary=lambda: {"complete_snapshot": True, "fetched": 2},
            )

        @staticmethod
        def search_local(query):
            return SimpleNamespace(members=members, next_offset=None)

    class Remote:
        @staticmethod
        def add_member(selected_target, user, **kwargs):
            invited.append((selected_target.id, user.id))
            return SimpleNamespace(accepted=True)

    fake = SimpleNamespace(
        core=SimpleNamespace(
            members=Members(),
            membership=SimpleNamespace(remote=Remote()),
        )
    )
    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(fake))
    api = BridgeApplicationApi(config_file)
    captured = {}

    def immediate(*, kind, callback, priority):
        captured["kind"] = kind
        captured["result"] = callback()
        return {"ok": True, "task": {"task_id": "invite-task", "status": "queued"}}

    monkeypatch.setattr(api, "_start_background", immediate)
    response = api.dispatch(
        "POST",
        "/api/v1/community/members/invite/start",
        body={
            "site_key": "medical-site",
            "source_peer_file": str(source_file),
            "target_peer_file": str(target_file),
            "all_members": True,
            "delay_seconds": 0,
            "confirm": True,
        },
    )
    assert response.status == 202
    assert captured["kind"] == "community.members.invite"
    assert captured["result"]["report"]["candidate_count"] == 2
    assert captured["result"]["report"]["succeeded"] == 2
    assert invited == [(55, 501), (55, 502)]


def test_ui3_background_task_keeps_safe_core_error(config_file, monkeypatch):
    import time
    from eitaa_core.errors import UploadPartError

    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)

    def fail():
        raise UploadPartError(
            "Upload part failed safely.",
            safe_context={"part_index": 2, "total_parts": 4},
        )

    started = api._start_background(kind="community.bulk.run", callback=fail)
    task_id = started["task"]["task_id"]
    task = None
    for _ in range(100):
        task = api._background_status({"task_id": task_id})["task"]
        if task["status"] == "failed":
            break
        time.sleep(0.01)
    assert task is not None
    assert task["status"] == "failed"
    assert task["error"]["component"] == "upload"
    assert task["error"]["message"] == "Upload part failed safely."
    assert task["error"]["safe_context"]["part_index"] == 2
