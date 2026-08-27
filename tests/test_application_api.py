from __future__ import annotations

import json
from pathlib import Path
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

from eitaa_core import DialogEntry, Message, Peer, PeerType, save_peer_file
from eitaa_core.errors import NetworkError, RpcError

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.scheduler import EitaaPriority
from eitaa_bridge.facade import EitaaBridge


PEER = Peer(id=14394054, type=PeerType.CHANNEL, access_hash=987654321)


class Context:
    def __init__(self, bridge):
        self.bridge = bridge

    def __enter__(self):
        return self.bridge

    def __exit__(self, exc_type, exc, tb):
        close = getattr(self.bridge, "close", None)
        if callable(close):
            close()
        return False


def test_api_health_and_schema(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    health = api.dispatch("GET", "/api/v1/health")
    assert health.status == 200
    assert health.payload["ok"] is True
    assert health.payload["api_version"] == "v1"
    assert health.payload["core_product"] == "0.6.0-core7.4.5-gmi1"
    assert health.payload["core_package"] == "0.6.0.dev19"
    schema = api.dispatch("GET", "/api/v1/schema")
    assert schema.status == 200
    assert schema.payload["composer"]["allowed_post_statuses"] == ["draft", "publish"]
    assert {"method": "POST", "path": "/api/v1/auth/reset-local-session"} in schema.payload["routes"]


def test_api_optional_bearer_auth(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file, bearer_token="local-secret")
    denied = api.dispatch("GET", "/api/v1/health")
    assert denied.status == 401
    allowed = api.dispatch(
        "GET", "/api/v1/health", authorization="Bearer local-secret"
    )
    assert allowed.status == 200


def test_api_message_list_returns_ui_text_and_usage(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "selected_private_channel.json"
    save_peer_file(peer_file, PEER)

    class FakeBridge:
        def application_messages(self, peer, *, limit, before_id):
            assert peer.id == PEER.id
            assert limit == 25
            assert before_id is None
            return {
                "site_key": "medical-site",
                "peer": peer.safe_summary(),
                "message_count": 1,
                "next_before_id": 11802,
                "messages": [{
                    "id": 11802,
                    "date": "2026-07-17T00:00:00+00:00",
                    "text": "متن واقعی پیام",
                    "usage": {"used": False, "usage_state": "unused"},
                }],
            }

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch(
        "POST",
        "/api/v1/messages/list",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "limit": 25,
        },
    )
    assert response.status == 200
    assert response.payload["messages"][0]["text"] == "متن واقعی پیام"
    assert response.payload["messages"][0]["usage"]["usage_state"] == "unused"


def test_api_message_sender_names_prefer_eitaa_contacts_then_members(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "sender-directory-channel.json"
    save_peer_file(peer_file, PEER)

    member_users = {
        123: SimpleNamespace(display_name="نام نمایشی عضو", username="member-contact", is_contact=True),
        456: SimpleNamespace(display_name="نام نمایشی ایتا", username="member-user", is_contact=False),
    }

    class FakeMembers:
        @staticmethod
        def get(peer, user_id):
            assert peer.id == PEER.id
            user = member_users.get(user_id)
            return SimpleNamespace(user=user) if user else None

    class FakeBridge:
        core = SimpleNamespace(members=FakeMembers())

        def application_messages(self, peer, *, limit, before_id):
            return {
                "site_key": "medical-site",
                "peer": peer.safe_summary(),
                "message_count": 5,
                "messages": [
                    {"id": 1, "sender_key": "user:123", "usage": {"used": False}},
                    {"id": 2, "sender_key": "user:456", "usage": {"used": False}},
                    {"id": 3, "sender_key": "user:789", "usage": {"used": False}},
                    {"id": 4, "sender_key": "user:999", "usage": {"used": False}},
                    {"id": 5, "sender_key": "self", "usage": {"used": False}},
                ],
            }

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    api._contact_store.upsert_contact({
        "first_name": "نام",
        "last_name": "دفترچه مخاطبان",
        "username": "saved-contact",
        "eitaa_user_id": 123,
        "source": "eitaa_contact_sync",
        "phones": [],
    })
    api._contact_store.upsert_contact({
        "first_name": "Eitaa",
        "last_name": "",
        "username": "generic-contact-title",
        "eitaa_user_id": 456,
        "source": "eitaa_contact_sync",
        "phones": [],
    })
    api._sender_directory.upsert_users([
        SimpleNamespace(
            peer=Peer(id=789, type=PeerType.USER),
            display_name="نام پاسخ تاریخچه",
            username="history-user",
            is_contact=False,
        )
    ])

    response = api.dispatch("POST", "/api/v1/messages/list", body={
        "site_key": "medical-site",
        "peer_file": str(peer_file),
        "limit": 25,
    })

    assert response.status == 200
    messages = {item["sender_key"]: item for item in response.payload["messages"]}
    assert messages["user:123"]["sender_display_name"] == "نام دفترچه مخاطبان"
    assert messages["user:123"]["sender_is_eitaa_contact"] is True
    assert messages["user:123"]["sender_resolution"] == "eitaa_contact"
    assert messages["user:456"]["sender_display_name"] == "نام نمایشی ایتا"
    assert messages["user:456"]["sender_is_eitaa_contact"] is True
    assert messages["user:456"]["sender_resolution"] == "eitaa_contact"
    assert messages["user:789"]["sender_display_name"] == "نام پاسخ تاریخچه"
    assert messages["user:789"]["sender_resolution"] == "history_user"
    assert messages["user:999"]["sender_display_name"] is None
    assert messages["user:999"]["sender_resolution"] == "unknown"
    assert messages["self"]["sender_display_name"] == "پیام‌های ارسالی من"


def test_api_composition_preview_accepts_json_request(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "selected_private_channel.json"
    save_peer_file(peer_file, PEER)
    captured = {}

    class FakeBridge:
        def preview_wordpress_composition(self, request):
            captured["request"] = request
            captured["thread"] = threading.current_thread().name
            return SimpleNamespace(
                safe_summary=lambda: {
                    "outcome": "composition_preview",
                    "plan": request.safe_summary(),
                }
            )

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch(
        "POST",
        "/api/v1/compositions/preview",
        body={
            "composition": {
                "composition_key": "api-roundup",
                "site_key": "medical-site",
                "title": "عنوان",
                "post_status": "publish",
                "confirm_publish": True,
                "sources": [{"peer_file": str(peer_file), "message_id": 11802}],
            }
        },
    )
    assert response.status == 200
    assert response.payload["outcome"] == "composition_preview"
    assert captured["request"].post_status == "publish"
    assert captured["request"].confirm_publish is True
    assert captured["thread"] == "eitaa-operation-scheduler"


def test_api_rejects_publish_without_confirmation(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "selected_private_channel.json"
    save_peer_file(peer_file, PEER)
    api = BridgeApplicationApi(config_file)
    response = api.dispatch(
        "POST",
        "/api/v1/compositions/preview",
        body={
            "composition_key": "api-roundup",
            "site_key": "medical-site",
            "title": "عنوان",
            "post_status": "publish",
            "confirm_publish": False,
            "sources": [{"peer_file": str(peer_file), "message_id": 11802}],
        },
    )
    assert response.status == 400
    assert response.payload["ok"] is False
    assert response.payload["error"]["error_code"] == "composition_publish_confirmation_required"
    assert "confirm_publish" in response.payload["error"]["message"]


def test_api_unknown_route_is_404(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("GET", "/api/v1/missing")
    assert response.status == 404
    assert response.payload["error"]["error_code"] == "api_route_not_found"



def test_api_auth_status_requires_login_when_session_missing(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("GET", "/api/v1/auth/status")
    assert response.status == 200
    assert response.payload["authenticated"] is False
    assert response.payload["session_present"] is False



def test_api_auth_status_preserves_present_session_on_transient_open_failure(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    config_payload = json.loads(config_file.read_text(encoding="utf-8"))
    session_path = config_file.parent / config_payload["core"]["session_file"]
    session_path.write_text("{}", encoding="utf-8")

    def fail_open(*args, **kwargs):
        raise PermissionError("temporary lock")

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaCore.open", fail_open)
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("GET", "/api/v1/auth/status")

    assert response.status == 200
    assert response.payload["authenticated"] is False
    assert response.payload["session_present"] is True
    assert response.payload["session_error"] is True
    assert response.payload["session_error_code"] == "auth_session_open_failed"
    assert response.payload["session_error_type"] == "PermissionError"


def test_api_auth_request_code_wraps_unexpected_runtime_failure(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")

    def fail_open(*args, **kwargs):
        raise OSError("runtime unavailable")

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaAuth.open", fail_open)
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("POST", "/api/v1/auth/request-code", body={"phone": "+989121234567"})

    assert response.status == 400
    assert response.payload["ok"] is False
    assert response.payload["error"]["error_code"] == "auth_request_code_failed"
    assert response.payload["error"]["component"] == "authentication"
    assert response.payload["error"]["safe_context"]["error_type"] == "OSError"


def test_api_auth_request_code_reports_provider_network_failure(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")

    class AuthService:
        def request_code(self, phone):
            raise NetworkError(
                "provider endpoint unavailable",
                safe_context={"endpoint": "https://provider.invalid/api"},
            )

    class Runtime:
        auth = AuthService()

        def close(self):
            pass

    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: Runtime(),
    )
    api = BridgeApplicationApi(config_file)
    response = api.dispatch(
        "POST",
        "/api/v1/auth/request-code",
        body={"phone": "+989121234567"},
    )

    assert response.status == 400
    assert response.payload["ok"] is False
    assert (
        response.payload["error"]["error_code"]
        == "auth_provider_network_unreachable"
    )
    assert response.payload["error"]["component"] == "authentication"
    assert response.payload["error"]["safe_context"] == {
        "error_type": "NetworkError"
    }
    serialized = json.dumps(response.payload, ensure_ascii=False)
    assert "provider.invalid" not in serialized
    assert "+989121234567" not in serialized

def test_api_auth_request_code_keeps_secret_challenge_in_memory(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")

    class Challenge:
        def safe_summary(self):
            return {"phone": "+98***", "delivery_type": "app", "code_length": 5}

    class AuthService:
        def request_code(self, phone):
            assert phone == "+989121234567"
            return Challenge()

    class Runtime:
        auth = AuthService()
        def close(self):
            pass

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaAuth.open", lambda *a, **k: Runtime())
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("POST", "/api/v1/auth/request-code", body={"phone": "+989121234567"})
    assert response.status == 200
    assert response.payload["step"] == "code"
    assert "phone_code_hash" not in json.dumps(response.payload)


def test_api_dialogs_list_exposes_ui_title_and_saves_peer_file(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer = Peer(id=14394054, type=PeerType.CHANNEL, access_hash=123, title="کانال پزشکی")

    class Discovery:
        def cached_dialogs(self, **kwargs):
            return (DialogEntry(peer=peer, top_message_id=11802, unread_count=3),)
        def list_all_dialogs(self, **kwargs):
            return SimpleNamespace(
                dialogs=(DialogEntry(peer=peer, top_message_id=11802, unread_count=3),),
                total_count=1,
                pages_fetched=1,
                duplicate_count=0,
                complete=True,
                parse_warnings=(),
                stored_count=1,
            )
        def save_peer(self, selected, path):
            save_peer_file(path, selected)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery())
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("POST", "/api/v1/dialogs/list", body={"site_key": "medical-site"})
    assert response.status == 200
    dialog = response.payload["dialogs"][0]
    assert dialog["peer"]["title"] == "کانال پزشکی"
    assert dialog["unread_count"] == 3
    assert (config_file.parent / dialog["peer_file"]).exists()


def test_api_media_preview_handles_text_only_message(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "selected_private_channel.json"
    save_peer_file(peer_file, PEER)
    message = Message(id=11802, peer=PEER, date=datetime.now(timezone.utc), text="text")

    class FakeBridge:
        core = SimpleNamespace(messages=SimpleNamespace(get=lambda peer, message_id: message))
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("POST", "/api/v1/messages/media-preview", body={
        "site_key": "medical-site", "peer_file": str(peer_file), "message_id": 11802,
    })
    assert response.status == 200
    assert response.payload["media_present"] is False


def test_api_compositions_include_local_edit_fields(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    record = SimpleNamespace(
        title="عنوان واقعی", excerpt="چکیده واقعی", post_url="https://example.test/?p=7",
        safe_summary=lambda: {
            "composition_key": "roundup", "site_key": "medical-site", "post_id": 7,
            "post_slug": "roundup", "status": "draft", "category_ids": [13],
            "tag_ids": [55], "source_keys": ["channel:1:2"], "updated_at": "2026-07-17T00:00:00+00:00",
        },
    )

    class FakeBridge:
        def wordpress_compositions(self, *, limit):
            return (record,)
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("GET", "/api/v1/compositions?site_key=medical-site")
    assert response.status == 200
    assert response.payload["compositions"][0]["title"] == "عنوان واقعی"
    assert response.payload["compositions"][0]["excerpt"] == "چکیده واقعی"


def test_api_manual_dialog_persists_group_display_kind(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer = Peer(id=900, type=PeerType.CHANNEL, access_hash=22, title="سوپرگروه نمونه")

    class Discovery:
        def resolve_username(self, username):
            assert username == "samplegroup"
            return SimpleNamespace(peer=peer)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery())
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    added = api.dispatch("POST", "/api/v1/dialogs/manual", body={
        "site_key": "medical-site", "mode": "username", "username": "@samplegroup", "display_kind": "group",
    })
    assert added.status == 201
    assert added.payload["dialog"]["display_kind"] == "group"
    assert added.payload["dialog"]["display_kind_locked"] is True
    listed = api.dispatch("POST", "/api/v1/dialogs/list", body={"site_key": "medical-site", "refresh_if_empty": False})
    assert listed.payload["dialogs"][0]["peer_key"] == "channel:900"


def test_api_dialog_favorite_and_kind_override(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    peer = Peer(id=901, type=PeerType.CHANNEL, access_hash=23, title="گروه")
    peer_file = config_file.parent / "manual-peer.json"
    save_peer_file(peer_file, peer)
    api.dialog_catalog.upsert(peer=peer, peer_file=peer_file, source="manual")
    favorite = api.dispatch("POST", "/api/v1/dialogs/favorite", body={"site_key": "medical-site", "peer_key": "channel:901", "favorite": True})
    kind = api.dispatch("POST", "/api/v1/dialogs/display-kind", body={"site_key": "medical-site", "peer_key": "channel:901", "display_kind": "group"})
    assert favorite.payload["dialog"]["favorite"] is True
    assert kind.payload["dialog"]["display_kind"] == "group"
    assert kind.payload["dialog"]["display_kind_locked"] is True


def test_api_create_tag_exposes_created_term(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")

    class FakeBridge:
        def create_wordpress_tag(self, *, name, slug=None):
            assert name == "کلمه جدید"
            return SimpleNamespace(safe_summary=lambda: {"id": 44, "name": name, "slug": "new-tag", "taxonomy": "post_tag"})
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("POST", "/api/v1/wordpress/tags", body={"site_key": "medical-site", "name": "کلمه جدید"})
    assert response.status == 201
    assert response.payload["term"]["id"] == 44


def test_api_wordpress_post_returns_editable_metadata(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")

    class FakeBridge:
        def wordpress_post(self, post_id):
            assert post_id == 599
            return SimpleNamespace(
                id=599, status="draft", title_raw="عنوان زنده", excerpt_raw="چکیده زنده",
                link="https://example.test/?p=599", category_ids=(12, 13), tag_ids=(4, 9),
                safe_summary=lambda: {"id": 599, "status": "draft", "category_ids": [12, 13], "tag_ids": [4, 9]},
            )
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("POST", "/api/v1/wordpress/post", body={"site_key": "medical-site", "post_id": 599})
    assert response.status == 200
    assert response.payload["post"]["title"] == "عنوان زنده"
    assert response.payload["post"]["category_ids"] == [12, 13]


def test_api_reset_without_active_session_opens_clean_login(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)

    result = api.dispatch("POST", "/api/v1/auth/reset-local-session", body={"confirm": True})
    assert result.status == 200
    assert result.payload["session_present"] is False
    assert result.payload["archived"] is False
    assert result.payload["login_ready"] is True


def test_api_archives_invalid_local_session_before_fresh_login(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    config_payload = json.loads(config_file.read_text(encoding="utf-8"))
    session_path = config_file.parent / config_payload["core"]["session_file"]
    session_path.write_text("{invalid", encoding="utf-8")
    api = BridgeApplicationApi(config_file)

    denied = api.dispatch("POST", "/api/v1/auth/reset-local-session", body={"confirm": False})
    assert denied.status == 400
    assert denied.payload["error"]["error_code"] == "api_session_reset_confirmation_required"
    assert session_path.exists()

    result = api.dispatch("POST", "/api/v1/auth/reset-local-session", body={"confirm": True})
    assert result.status == 200
    assert result.payload["archived"] is True
    assert result.payload["login_ready"] is True
    assert not session_path.exists()
    backups = list(session_path.parent.glob(session_path.name + ".invalid.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{invalid"


def test_api_logout_archives_local_session_when_remote_login_is_already_invalid(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    config_payload = json.loads(config_file.read_text(encoding="utf-8"))
    session_path = config_file.parent / config_payload["core"]["session_file"]
    session_contents = json.dumps({"token": "expired-token", "imei": "abc__web"})
    session_path.write_text(session_contents, encoding="utf-8")

    class Account:
        def logout(self, *, archive_local_session):
            assert archive_local_session is True
            raise RpcError(401, "INVALID_LOGIN")

    class FakeBridge:
        core = SimpleNamespace(account=Account())

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)

    response = api.dispatch("POST", "/api/v1/auth/logout")

    assert response.status == 200
    assert response.payload["ok"] is True
    assert response.payload["session_present"] is False
    assert response.payload["login_ready"] is True
    assert response.payload["logout"]["remote_ok"] is False
    assert response.payload["logout"]["remote_session_already_invalid"] is True
    assert response.payload["logout"]["local_session_archived"] is True
    assert not session_path.exists()
    backups = list(session_path.parent.glob(session_path.name + ".invalid.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == session_contents


def test_api_dialog_sync_uses_core_complete_collection_and_supergroup_kind(config_file, monkeypatch):
    from eitaa_core import DialogKind

    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer = Peer(id=555, type=PeerType.CHANNEL, access_hash=123, title="گروه آزمایشی")
    entry = DialogEntry(
        peer=peer,
        top_message_id=900,
        top_message_date=1700000000,
        unread_count=7,
        kind=DialogKind.SUPERGROUP,
        megagroup=True,
        participants_count=42,
    )

    class Discovery:
        def list_dialogs(self, **kwargs):
            assert kwargs["limit"] == 100
            return SimpleNamespace(
                dialogs=(entry,), total_count=1, response_type="messages.dialogs",
                next_cursor=None, parse_warnings=(),
            )
        def store_dialog_snapshot(self, collection):
            assert len(collection.dialogs) == 1
            return 1
        def save_peer(self, selected, path):
            save_peer_file(path, selected)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery())
        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch(
        "POST", "/api/v1/dialogs/sync",
        body={"site_key": "medical-site", "page_size": 100, "max_pages": 100},
    )
    assert response.status == 200
    assert response.payload["sync"]["completed"] is True
    assert response.payload["sync"]["server_total_count"] == 1
    dialog = response.payload["dialogs"][0]
    assert dialog["technical_kind"] == "supergroup"
    assert dialog["display_kind"] == "group"
    assert dialog["unread_count"] == 7
    assert dialog["participants_count"] == 42


def test_api_dialog_live_sync_merges_first_page_without_hiding_older_dialogs(config_file, monkeypatch):
    from eitaa_core import DialogKind

    older_peer = Peer(id=554, type=PeerType.CHAT, title="گفتگوی قدیمی")
    recent_peer = Peer(id=555, type=PeerType.CHANNEL, access_hash=123, title="گفتگوی تازه")
    recent = DialogEntry(
        peer=recent_peer,
        top_message_id=901,
        unread_count=3,
        kind=DialogKind.CHANNEL,
    )

    class Discovery:
        def list_dialogs(self, **kwargs):
            assert kwargs == {
                "limit": 100,
                "offset_date": 0,
                "offset_id": 0,
                "offset_peer": None,
                "exclude_pinned": False,
            }
            return SimpleNamespace(
                dialogs=(recent,), total_count=2, response_type="messages.dialogsSlice",
                next_cursor=None, parse_warnings=(),
            )

        def save_peer(self, selected, path):
            save_peer_file(path, selected)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery())

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    monkeypatch.setattr(
        "eitaa_bridge.application.api.consume_dialog_account_roles",
        lambda: {"channel:555": "admin"},
    )
    api = BridgeApplicationApi(config_file)
    api.dialog_catalog.upsert(
        peer=older_peer,
        peer_file=config_file.parent / "data" / "peers" / "chat-554.json",
        source="remote",
        unread_count=0,
        active=True,
    )

    response = api.dispatch(
        "POST", "/api/v1/dialogs/live-sync", body={"site_key": "medical-site"}
    )

    assert response.status == 200
    assert response.payload["sync"]["mode"] == "first_page_merge"
    assert response.payload["sync"]["merged_count"] == 1
    assert response.payload["dialog_count"] == 2
    by_key = {item["peer_key"]: item for item in response.payload["dialogs"]}
    assert by_key["chat:554"]["active"] is True
    assert by_key["channel:555"]["unread_count"] == 3
    assert by_key["channel:555"]["account_role"] == "admin"
    assert by_key["channel:555"]["can_manage_community"] is True


def test_api_dialog_sync_skips_unusable_remote_peer_without_losing_valid_dialogs(config_file, monkeypatch):
    from eitaa_core import DialogKind

    valid_peer = Peer(id=556, type=PeerType.CHANNEL, access_hash=124, title="کانال سالم")
    invalid_peer = Peer(id=557, type=PeerType.USER, access_hash=None, title="حساب حذف‌شده")
    valid = DialogEntry(peer=valid_peer, top_message_id=10, kind=DialogKind.CHANNEL)
    invalid = DialogEntry(peer=invalid_peer, top_message_id=9, kind=DialogKind.PRIVATE)

    class Discovery:
        def list_dialogs(self, **kwargs):
            return SimpleNamespace(
                dialogs=(valid, invalid), total_count=2, response_type="messages.dialogs",
                next_cursor=None, parse_warnings=(),
            )

        def store_dialog_snapshot(self, collection):
            assert collection.complete is True
            assert [item.peer.id for item in collection.dialogs] == [valid_peer.id]
            return 1

        def save_peer(self, selected, path):
            assert selected.access_hash is not None
            save_peer_file(path, selected)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery())

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    response = api.dispatch(
        "POST", "/api/v1/dialogs/sync",
        body={"site_key": "medical-site", "page_size": 100, "max_pages": 100},
    )
    assert response.status == 200
    assert response.payload["dialog_count"] == 1
    assert response.payload["sync"]["completed"] is True
    assert response.payload["sync"]["skipped_unusable_count"] == 1
    assert response.payload["sync"]["warning_codes"] == [
        "page1:unusable_peer_missing_access_hash:1"
    ]


def test_api_auth_status_probes_remote_session_before_workspace(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    config_payload = json.loads(config_file.read_text(encoding="utf-8"))
    session_path = config_file.parent / config_payload["core"]["session_file"]
    session_path.write_text(json.dumps({"token": "valid-looking", "imei": "abc__web"}), encoding="utf-8")

    class FakeSession:
        def safe_summary(self):
            return {"token_present": True}

    class Discovery:
        def list_dialogs(self, **kwargs):
            assert kwargs["limit"] == 1
            raise OSError("network or remote auth failure")

    class FakeCore:
        session = FakeSession()
        discovery = Discovery()
        def close(self):
            pass

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaCore.open", lambda *a, **k: FakeCore())
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("GET", "/api/v1/auth/status")
    assert response.status == 200
    assert response.payload["authenticated"] is True
    assert response.payload["session_present"] is True
    assert response.payload["remote_probe"] is False
    assert response.payload["remote_warning"] is True
    assert response.payload["remote_error_type"] == "OSError"
    assert response.payload["fresh_login_available"] is False


def test_api_auth_status_routes_rpc_401_to_session_recovery(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    config_payload = json.loads(config_file.read_text(encoding="utf-8"))
    session_path = config_file.parent / config_payload["core"]["session_file"]
    session_path.write_text(
        json.dumps({"token": "expired-token", "imei": "abc__web"}),
        encoding="utf-8",
    )

    class FakeSession:
        def safe_summary(self):
            return {"token_present": True}

    class Discovery:
        def list_dialogs(self, **kwargs):
            assert kwargs["limit"] == 1
            raise RpcError(401, "INVALID_LOGIN")

    class FakeCore:
        session = FakeSession()
        discovery = Discovery()

        def close(self):
            pass

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaCore.open", lambda *a, **k: FakeCore())
    api = BridgeApplicationApi(config_file)

    response = api.dispatch("GET", "/api/v1/auth/status")

    assert response.status == 200
    assert response.payload["authenticated"] is False
    assert response.payload["session_present"] is True
    assert response.payload["session_error"] is True
    assert response.payload["session_invalid"] is True
    assert response.payload["session_error_code"] == "auth_session_invalid"
    assert response.payload["remote_error_code"] == 401
    assert response.payload["fresh_login_available"] is True


def test_api_rpc_401_uses_stable_session_invalid_error_contract():
    response = BridgeApplicationApi._error_response(RpcError(401, "INVALID_LOGIN"))

    assert response.status == 401
    assert response.payload["ok"] is False
    assert response.payload["error"]["component"] == "authentication"
    assert response.payload["error"]["error_code"] == "auth_session_invalid"
    assert response.payload["error"]["safe_context"] == {
        "error_type": "RpcError",
        "remote_code": 401,
        "recovery_available": True,
    }


def test_api_messages_read_marks_server_and_local_catalog(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "peer.json"
    save_peer_file(peer_file, PEER)

    class ReadResult:
        accepted = True
        def safe_summary(self):
            return {"peer": PEER.safe_summary(), "max_id": 11802, "accepted": True}

    class History:
        def mark_read(self, peer, max_id, *, remaining_unread_count=None):
            assert peer.id == PEER.id
            assert max_id == 11802
            assert remaining_unread_count is None
            return ReadResult()

    class FakeBridge:
        core = SimpleNamespace(history=History())
        def close(self): pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    api.dialog_catalog.upsert(
        peer=PEER, peer_file=peer_file, source="remote", unread_count=7, unread_mark=True,
    )
    response = api.dispatch("POST", "/api/v1/messages/read", body={
        "site_key": "medical-site", "peer_file": str(peer_file), "max_id": 11802,
    })
    assert response.status == 200
    assert response.payload["read"]["accepted"] is True
    assert response.payload["dialog"]["unread_count"] == 0
    assert response.payload["dialog"]["unread_mark"] is False



def test_api_messages_read_enqueue_is_non_blocking_and_updates_catalog(config_file, tmp_path, monkeypatch):
    import time
    import threading

    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "peer-queued.json"
    save_peer_file(peer_file, PEER)
    completed = threading.Event()

    class ReadResult:
        accepted = True
        def safe_summary(self):
            return {"peer": PEER.safe_summary(), "max_id": 11810, "accepted": True}

    class History:
        def mark_read(self, peer, max_id, *, remaining_unread_count=None):
            assert peer.id == PEER.id
            assert max_id == 11810
            assert remaining_unread_count == 3
            completed.set()
            return ReadResult()

    class FakeBridge:
        core = SimpleNamespace(history=History())
        def close(self): pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    api._read_receipt_delay_seconds = 0.01
    api.dialog_catalog.upsert(
        peer=PEER, peer_file=peer_file, source="remote", unread_count=7,
        read_inbox_max_id=11800, unread_mark=True,
    )
    response = api.dispatch("POST", "/api/v1/messages/read/enqueue", body={
        "site_key": "medical-site", "peer_file": str(peer_file),
        "max_id": 11810, "remaining_unread_count": 3,
    })
    assert response.status == 202
    assert response.payload["queued"] is True
    assert completed.wait(1.0)
    for _ in range(100):
        stored = api.dialog_catalog.get(f"channel:{PEER.id}")
        if stored and stored["read_inbox_max_id"] == 11810:
            break
        time.sleep(0.01)
    assert stored["unread_count"] == 3
    assert stored["unread_mark"] is True
    assert stored["read_inbox_max_id"] == 11810

def test_api_dialog_sync_job_runs_in_background(config_file, monkeypatch):
    import time
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    monkeypatch.setattr(api, "_sync_dialog_catalog", lambda **kwargs: {
        "completed": True, "pages_fetched": 6, "remote_unique_count": 452,
        "server_total_count": 452, "warning_codes": [],
    })
    started = api.dispatch("POST", "/api/v1/dialogs/sync/start", body={"site_key": "medical-site"})
    assert started.status == 202
    job_id = started.payload["job"]["job_id"]
    for _ in range(50):
        status = api.dispatch("GET", f"/api/v1/dialogs/sync/status?job_id={job_id}")
        if status.payload["job"]["state"] == "completed":
            break
        time.sleep(0.01)
    assert status.payload["job"]["state"] == "completed"
    assert status.payload["job"]["result"]["sync"]["remote_unique_count"] == 452


def test_api_dialog_avatar_without_photo_is_safe(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "peer.json"
    save_peer_file(peer_file, PEER)

    class Discovery:
        def cached_dialogs(self, **kwargs):
            return (DialogEntry(peer=PEER, top_message_id=1, photo=None),)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery())
        def close(self): pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    api.dialog_catalog.upsert(peer=PEER, peer_file=peer_file, source="remote")
    response = api.dispatch("POST", "/api/v1/dialogs/avatar", body={
        "site_key": "medical-site", "peer_key": f"channel:{PEER.id}",
    })
    assert response.status == 200
    assert response.payload["avatar_present"] is False


def test_api_cached_only_avatar_never_opens_remote_core(config_file, tmp_path, monkeypatch):
    peer_file = tmp_path / "peer-cached-only.json"
    save_peer_file(peer_file, PEER)
    monkeypatch.setattr(
        EitaaBridge,
        "open",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote Core must not open")),
    )
    api = BridgeApplicationApi(config_file)
    api.dialog_catalog.upsert(peer=PEER, peer_file=peer_file, source="remote")
    response = api.dispatch("POST", "/api/v1/dialogs/avatar", body={
        "site_key": "medical-site",
        "peer_key": f"channel:{PEER.id}",
        "cached_only": True,
    })
    assert response.status == 200
    assert response.payload["avatar_present"] is False
    assert response.payload["cached_only"] is True


def test_api_active_avatar_repairs_corrupt_cache_at_active_avatar_priority(
    config_file, tmp_path, monkeypatch
):
    peer_file = tmp_path / "peer-avatar-repair.json"
    corrupt = tmp_path / "corrupt-avatar.jpg"
    recovered = tmp_path / "recovered-avatar.jpg"
    save_peer_file(peer_file, PEER)
    corrupt.write_bytes(b"")
    captured = {}
    photo = SimpleNamespace(photo_id=88)

    class Discovery:
        def cached_dialogs(self, **kwargs):
            return (DialogEntry(peer=PEER, top_message_id=1, photo=photo),)

        def set_cached_photo_path(self, peer, photo_id, path):
            assert peer == PEER
            assert photo_id == 88
            assert path == recovered

    class Media:
        def download(self, selected_photo, options):
            assert selected_photo is photo
            assert options.overwrite is True
            recovered.write_bytes(b"\xff\xd8\xffrecovered")
            return SimpleNamespace(path=recovered)

    class FakeBridge:
        core = SimpleNamespace(discovery=Discovery(), media=Media())
        config = SimpleNamespace(core=SimpleNamespace(media_directory=tmp_path / "media"))

        def close(self):
            pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api = BridgeApplicationApi(config_file)
    api.dialog_catalog.upsert(
        peer=PEER,
        peer_file=peer_file,
        source="remote",
        photo_cached_path=str(corrupt),
    )

    def run_immediately(**kwargs):
        captured.update(kwargs)
        return kwargs["callback"]()

    monkeypatch.setattr(api, "_run_eitaa", run_immediately)
    response = api.dispatch(
        "POST",
        "/api/v1/dialogs/avatar",
        body={
            "site_key": "medical-site",
            "peer_key": f"channel:{PEER.id}",
            "request_priority": "active",
        },
    )

    assert response.status == 200
    assert response.payload["avatar_present"] is True
    assert response.payload["mime_type"] == "image/jpeg"
    assert captured["priority"] is EitaaPriority.ACTIVE_AVATAR
    assert api.dialog_catalog.get(f"channel:{PEER.id}")["photo_cached_path"] == "recovered-avatar.jpg"

def test_api_date_range_sync_uses_active_message_priority(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    peer_file = tmp_path / "peer-date.json"
    save_peer_file(peer_file, PEER)
    captured = {}

    class FakeBridge:
        def sync_application_messages_date_range(self, peer, **kwargs):
            captured.update(kwargs)
            return {"matched": 4, "pages": 2}
        def close(self): pass

    monkeypatch.setattr(EitaaBridge, "open", lambda *args, **kwargs: Context(FakeBridge()))
    api_instance = BridgeApplicationApi(config_file)
    response = api_instance.dispatch("POST", "/api/v1/messages/date-range/sync", body={
        "site_key": "medical-site",
        "peer_file": str(peer_file),
        "date_from": "2026-07-01T00:00:00+00:00",
        "date_to": "2026-07-19T00:00:00+00:00",
    })
    assert response.status == 200
    assert response.payload["sync"]["matched"] == 4
    assert captured["date_from"].tzinfo is not None
    assert captured["date_to"].tzinfo is not None


def test_api_registers_media_cache_with_opaque_token(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    media = tmp_path / "preview.jpg"
    media.write_bytes(b"jpeg-data")
    api = BridgeApplicationApi(config_file)
    token = api.register_media_cache_file(media, "image/jpeg")
    assert len(token) == 32
    assert str(media) not in token
    assert api.resolve_media_cache_file(token) == (media.resolve(), "image/jpeg")
    assert api.resolve_media_cache_file("../preview.jpg") is None
    api.close()
