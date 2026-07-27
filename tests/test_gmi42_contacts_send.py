from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from eitaa_core import Contact, ContactSnapshot, Peer, PeerType, User, save_peer_file

from eitaa_bridge.application.api import BridgeApplicationApi


def test_quick_send_uses_current_peer_and_staged_upload(config_file, tmp_path, monkeypatch):
    api = BridgeApplicationApi(config_file)
    peer_file = tmp_path / "peer.json"
    peer = Peer(id=101, type=PeerType.CHANNEL, access_hash=202)
    save_peer_file(peer_file, peer)
    calls: list[tuple[str, object]] = []

    class Result:
        def safe_summary(self):
            return {"message_id": 77}

    class Send:
        def send_text(self, target, text):
            calls.append(("text", (target.id, text)))
            return Result()

        def send_photo(self, target, path, *, caption=""):
            calls.append(("photo", (target.id, path.name, caption)))
            return Result()

        def send_file(self, target, path, *, caption="", mime_type=""):
            calls.append(("file", (target.id, path.name, caption, mime_type)))
            return Result()

    fake_bridge = SimpleNamespace(core=SimpleNamespace(send=Send()))
    monkeypatch.setattr(api, "_open_bridge", lambda *args, **kwargs: nullcontext(fake_bridge))
    monkeypatch.setattr(api, "_run_eitaa", lambda *args, **kwargs: kwargs["callback"]())

    text = api.dispatch("POST", "/api/v1/messages/send", body={
        "site_key": "medical-site", "peer_file": str(peer_file), "text": "سلام",
    })
    assert text.status == 201
    assert calls[-1] == ("text", (101, "سلام"))

    upload_dir = api.base_directory / "runtime" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload = upload_dir / "image.jpg"
    upload.write_bytes(b"fake")
    photo = api.dispatch("POST", "/api/v1/messages/send", body={
        "site_key": "medical-site", "peer_file": str(peer_file), "text": "شرح",
        "upload_path": str(upload), "send_as": "photo", "cleanup_upload": True,
    })
    assert photo.status == 201
    assert calls[-1][0] == "photo"
    assert not upload.exists()
    api.close()


def test_real_eitaa_contacts_can_sync_into_local_categories(config_file, monkeypatch):
    api = BridgeApplicationApi(config_file)
    category = api.dispatch("POST", "/api/v1/contacts/categories/save", body={"name": "همکاران"}).payload["category"]
    user = User(
        peer=Peer(id=404, type=PeerType.USER, access_hash=505),
        first_name="مریم", last_name="احمدی", username="maryam", phone="+989121234567",
        is_contact=True,
    )
    snapshot = ContactSnapshot(contacts=(Contact(user=user, mutual=True),))
    fake_bridge = SimpleNamespace(core=SimpleNamespace(contacts=SimpleNamespace(list=lambda refresh=True: snapshot)))
    monkeypatch.setattr(api, "_open_bridge", lambda *args, **kwargs: nullcontext(fake_bridge))
    monkeypatch.setattr(api, "_run_eitaa", lambda *args, **kwargs: kwargs["callback"]())

    response = api.dispatch("POST", "/api/v1/eitaa-contacts/list", body={
        "site_key": "medical-site", "refresh": True, "sync_local": True,
        "category_ids": [category["id"]],
    })
    assert response.status == 200
    assert response.payload["contacts"][0]["peer_key"] == "user:404"
    assert response.payload["synced_local"] == 1
    local = api.dispatch("POST", "/api/v1/contacts/list", body={"category_ids": [category["id"]]})
    assert local.payload["total"] == 1
    assert local.payload["contacts"][0]["source"] == "eitaa_contact_sync"
    api.close()


def test_selected_eitaa_contacts_can_add_move_and_remove_local_categories(config_file, monkeypatch):
    api = BridgeApplicationApi(config_file)
    first_category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "همکاران"}
    ).payload["category"]
    second_category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "پشتیبانی"}
    ).payload["category"]
    users = (
        User(
            peer=Peer(id=601, type=PeerType.USER, access_hash=701),
            first_name="مریم", last_name="احمدی", username="maryam",
            phone="+989121111111", is_contact=True,
        ),
        User(
            peer=Peer(id=602, type=PeerType.USER, access_hash=702),
            first_name="رضا", last_name="کریمی", username="reza",
            phone="", is_contact=True,
        ),
    )
    snapshot = ContactSnapshot(contacts=tuple(Contact(user=user) for user in users))
    fake_bridge = SimpleNamespace(
        core=SimpleNamespace(contacts=SimpleNamespace(list=lambda refresh=True: snapshot))
    )
    monkeypatch.setattr(api, "_open_bridge", lambda *args, **kwargs: nullcontext(fake_bridge))
    monkeypatch.setattr(api, "_run_eitaa", lambda *args, **kwargs: kwargs["callback"]())

    listed = api.dispatch("POST", "/api/v1/eitaa-contacts/list", body={
        "site_key": "medical-site", "refresh": True, "limit": 50, "offset": 0,
    })
    selected = listed.payload["contacts"]
    categorized = api.dispatch("POST", "/api/v1/eitaa-contacts/categorize", body={
        "site_key": "medical-site",
        "category_ids": [first_category["id"]],
        "contacts": selected,
    })
    assert categorized.status == 200
    assert categorized.payload["categorized_count"] == 2

    merged = api.dispatch("POST", "/api/v1/eitaa-contacts/categorize", body={
        "site_key": "medical-site",
        "category_ids": [second_category["id"]],
        "contacts": [next(item for item in selected if item["user_id"] == 601)],
    })
    assert merged.status == 200
    refreshed = api.dispatch("POST", "/api/v1/eitaa-contacts/list", body={
        "site_key": "medical-site", "refresh": False, "limit": 50, "offset": 0,
    })
    by_user_id = {item["user_id"]: item for item in refreshed.payload["contacts"]}
    assert {item["name"] for item in by_user_id[601]["local_categories"]} == {
        "همکاران", "پشتیبانی"
    }
    assert [item["name"] for item in by_user_id[602]["local_categories"]] == ["همکاران"]
    assert by_user_id[602]["local_contact_id"] is not None

    moved = api.dispatch("POST", "/api/v1/eitaa-contacts/categorize", body={
        "site_key": "medical-site",
        "operation": "replace",
        "category_ids": [second_category["id"]],
        "contacts": [next(item for item in selected if item["user_id"] == 601)],
    })
    assert moved.status == 200
    assert moved.payload["operation"] == "replace"
    assert [item["name"] for item in moved.payload["contacts"][0]["local_categories"]] == ["پشتیبانی"]

    removed = api.dispatch("POST", "/api/v1/eitaa-contacts/categorize", body={
        "site_key": "medical-site",
        "operation": "remove",
        "category_ids": [second_category["id"]],
        "contacts": [next(item for item in selected if item["user_id"] == 601)],
    })
    assert removed.status == 200
    assert removed.payload["operation"] == "remove"
    assert removed.payload["contacts"][0]["local_categories"] == []

    missing = api.dispatch("POST", "/api/v1/eitaa-contacts/categorize", body={
        "site_key": "medical-site",
        "operation": "remove",
        "category_ids": [first_category["id"]],
        "contacts": [{"user_id": 999, "phone": "", "first_name": "ثبت‌نشده"}],
    })
    assert missing.status == 200
    assert missing.payload["updated_count"] == 0
    assert missing.payload["contacts"][0]["local_contact_id"] is None
    assert api.dispatch("POST", "/api/v1/contacts/list", body={"limit": 250}).payload["total"] == 2
    api.close()


def test_target_category_filter_is_strict_and_empty_selection_is_empty(config_file):
    api = BridgeApplicationApi(config_file)
    first = api.dispatch("POST", "/api/v1/contacts/categories/save", body={"name": "الف"}).payload["category"]
    second = api.dispatch("POST", "/api/v1/contacts/categories/save", body={"name": "ب"}).payload["category"]
    api.dispatch("POST", "/api/v1/contacts/upsert", body={"contact": {"first_name": "یک", "phones": ["09120000001"], "category_ids": [first["id"]]}})
    api.dispatch("POST", "/api/v1/contacts/upsert", body={"contact": {"first_name": "دو", "phones": ["09120000002"], "category_ids": [second["id"]]}})

    selected = api.dispatch("POST", "/api/v1/contacts/list", body={"category_ids": [first["id"]], "limit": 250})
    assert selected.payload["total"] == 1
    assert selected.payload["contacts"][0]["first_name"] == "یک"
    api.close()


def test_material_ui_sources_expose_rtl_contacts_quick_send_and_template_slot():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "ui" / "src"
    app = (root / "App.tsx").read_text(encoding="utf-8")
    contacts = (root / "ContactDirectoryModal.tsx").read_text(encoding="utf-8")
    quick = (root / "QuickSendBar.tsx").read_text(encoding="utf-8")
    theme = (root / "theme.ts").read_text(encoding="utf-8")
    css = (root / "styles.css").read_text(encoding="utf-8")

    assert '<QuickSendBar siteKey={siteKey}' in app
    assert 'مدیریت مخاطبان ایتا و محلی' in app
    assert '/api/v1/eitaa-contacts/list' in contacts
    assert '/api/v1/eitaa-contacts/categorize' in contacts
    assert "operation: eitaaCategoryOperation" in contacts
    assert "const batchSize = 250" in contacts
    assert "انتقال — جایگزینی همه دسته‌های قبلی" in contacts
    assert 'فهرست پیمایشی مخاطبان ایتا' in contacts
    assert 'ارسال پیام' in contacts
    assert 'فقط مخاطبان دسته‌های علامت‌خورده نمایش داده می‌شوند' in contacts
    assert 'selectUploadFile' in quick
    assert 'تمپلیت‌های پیام' in quick
    assert "direction: 'rtl'" in theme
    assert 'background: #07090d !important' in css
    assert '@media (max-width: 599px)' in css
    assert '[data-media-display="dynamic"]' in css


def test_eitaa_contacts_are_cached_searched_and_paged(config_file, monkeypatch):
    api = BridgeApplicationApi(config_file)
    calls = {"count": 0}
    contacts = tuple(
        Contact(user=User(
            peer=Peer(id=1000 + index, type=PeerType.USER, access_hash=2000 + index),
            first_name=f"همکار {index:03d}", last_name="آزمون", username=f"user{index}",
            phone=f"+9891200{index:04d}", is_contact=True,
        )) for index in range(120)
    )
    def list_contacts(refresh=False):
        calls["count"] += 1
        return ContactSnapshot(contacts=contacts)
    fake_bridge = SimpleNamespace(core=SimpleNamespace(contacts=SimpleNamespace(list=list_contacts)))
    monkeypatch.setattr(api, "_open_bridge", lambda *args, **kwargs: nullcontext(fake_bridge))
    monkeypatch.setattr(api, "_run_eitaa", lambda *args, **kwargs: kwargs["callback"]())

    first = api.dispatch("POST", "/api/v1/eitaa-contacts/list", body={
        "site_key": "medical-site", "refresh": True, "limit": 50, "offset": 0,
    })
    second = api.dispatch("POST", "/api/v1/eitaa-contacts/list", body={
        "site_key": "medical-site", "refresh": False, "limit": 50, "offset": 50,
    })
    searched = api.dispatch("POST", "/api/v1/eitaa-contacts/list", body={
        "site_key": "medical-site", "refresh": False, "search": "همکار 119", "limit": 50, "offset": 0,
    })
    assert calls["count"] == 1
    assert first.payload["total"] == 120 and len(first.payload["contacts"]) == 50
    assert second.payload["offset"] == 50 and len(second.payload["contacts"]) == 50
    assert second.payload["cache_hit"] is True
    assert searched.payload["total"] == 1
    assert searched.payload["contacts"][0]["user_id"] == 1119
    api.close()


def test_avatar_source_catalog_is_scanned_once_per_cache_window(config_file):
    api = BridgeApplicationApi(config_file)
    calls = {"count": 0}
    peer = Peer(id=808, type=PeerType.CHANNEL, access_hash=909)
    photo = SimpleNamespace(photo_id=123)
    def cached_dialogs(*, active_only=False, limit=10_000):
        calls["count"] += 1
        return (SimpleNamespace(peer=peer, photo=photo),)
    bridge = SimpleNamespace(core=SimpleNamespace(discovery=SimpleNamespace(cached_dialogs=cached_dialogs)))
    first = api._dialog_avatar_source(bridge, "medical-site", "channel:808")
    second = api._dialog_avatar_source(bridge, "medical-site", "channel:808")
    assert first == (peer, photo)
    assert second == first
    assert calls["count"] == 1
    api.close()
