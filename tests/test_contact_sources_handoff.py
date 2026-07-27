from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
import time

import pytest

from eitaa_core import Peer, PeerType, save_peer_file

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.contact_store import SQLiteContactStore


def _wait_for_contact_job(api: BridgeApplicationApi, job_id: str) -> dict:
    for _ in range(500):
        response = api.dispatch(
            "GET", f"/api/v1/contacts/import/status?job_id={job_id}"
        )
        job = response.payload["job"]
        if job["state"] not in {"queued", "running", "cancelling"}:
            return job
        time.sleep(0.01)
    raise AssertionError("contact import job did not finish")


def test_eitaa_id_merge_preserves_opt_out_and_rejects_cross_identity(tmp_path) -> None:
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    category = store.save_category(name="اعضا")
    first = store.upsert_contact(
        {
            "eitaa_user_id": 101,
            "access_hash": "first-secret",
            "sendable": False,
            "opt_out": True,
            "category_ids": [category["id"]],
        },
        duplicate_policy="update",
        category_policy="merge",
    )
    merged = store.upsert_contact(
        {
            "first_name": "به‌روزشده",
            "phones": ["09121234567"],
            "eitaa_user_id": 101,
            "access_hash": "second-secret",
            "sendable": True,
        },
        duplicate_policy="update",
        category_policy="merge",
    )
    assert merged["id"] == first["id"]
    assert merged["merged"] is True
    assert merged["opt_out"] is True
    assert merged["sendable"] is True
    assert [item["name"] for item in merged["categories"]] == ["اعضا"]

    store.upsert_contact({"phones": ["09351234567"], "eitaa_user_id": 202})
    with pytest.raises(ValueError, match="different existing contacts"):
        store.upsert_contact(
            {"phones": ["09351234567"], "eitaa_user_id": 101},
            duplicate_policy="update",
        )


def test_local_member_and_phone_list_imports_bypass_scheduler_and_hide_secrets(
    config_file, monkeypatch
) -> None:
    api = BridgeApplicationApi(config_file)
    monkeypatch.setattr(
        api,
        "_run_eitaa",
        lambda *args, **kwargs: pytest.fail(
            "local source imports must not use the Eitaa scheduler"
        ),
    )
    root = config_file.parent
    community = Peer(
        type=PeerType.CHANNEL, id=700, access_hash=900, title="گروه آزمون"
    )
    peer_file = root / "community.json"
    save_peer_file(peer_file, community)

    user_peer = SimpleNamespace(
        id=501, access_hash=987654321, username="member501"
    )
    member_user = SimpleNamespace(
        peer=user_peer,
        first_name="عضو",
        last_name="آزمایشی",
        username="member501",
        phone="+989121234567",
        is_deleted=False,
    )
    member = SimpleNamespace(user=member_user, is_sendable=True)
    member_page = SimpleNamespace(
        members=(member,), total_count=1, next_offset=None
    )

    resolved_user = SimpleNamespace(
        peer=user_peer,
        first_name="عضو تازه",
        last_name="آزمایشی",
        username="member501",
        is_deleted=False,
    )
    resolved_entry = SimpleNamespace(
        user=resolved_user,
        phone="+989121234567",
        first_name="نام فهرست",
        last_name="",
        resolved_at=datetime.now(timezone.utc),
    )
    phone_list = SimpleNamespace(total_rows=1)
    fake_phone_lists = SimpleNamespace(
        status=lambda list_id: phone_list,
        entries=lambda list_id, offset, limit: (
            (resolved_entry,) if offset == 0 else ()
        ),
    )
    fake_core = SimpleNamespace(
        members=SimpleNamespace(search_local=lambda query: member_page),
        phone_lists=fake_phone_lists,
    )
    fake_bridge = SimpleNamespace(core=fake_core)

    @contextmanager
    def open_fake_bridge(*args, **kwargs):
        yield fake_bridge

    monkeypatch.setattr(api, "_open_bridge", open_fake_bridge)

    category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "ورودی ایتا"}
    ).payload["category"]
    started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/community/start",
        body={
            "site_key": "medical-site",
            "peer_file": str(peer_file),
            "member_ids": [501],
            "category_ids": [category["id"]],
        },
    )
    assert started.status == 202
    assert "987654321" not in repr(started.payload)
    member_job = _wait_for_contact_job(api, started.payload["job"]["job_id"])
    assert member_job["state"] == "completed"
    assert member_job["progress"]["imported"] == 1

    listed = api.dispatch("POST", "/api/v1/contacts/list", body={})
    contact = listed.payload["contacts"][0]
    assert contact["eitaa_user_id"] == 501
    assert contact["access_hash_present"] is True
    assert "987654321" not in repr(listed.payload)

    api.dispatch(
        "POST",
        "/api/v1/contacts/upsert",
        body={
            "duplicate_policy": "update",
            "contact": {
                "id": contact["id"],
                "first_name": contact["first_name"],
                "phones": contact["phones"],
                "sendable": False,
                "opt_out": True,
                "category_ids": [category["id"]],
            },
        },
    )
    started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/phone-list/start",
        body={
            "site_key": "medical-site",
            "list_id": "resolved-list-1",
            "category_ids": [category["id"]],
        },
    )
    phone_job = _wait_for_contact_job(api, started.payload["job"]["job_id"])
    assert phone_job["state"] == "completed"
    assert phone_job["progress"]["updated"] == 1
    after = api.dispatch("POST", "/api/v1/contacts/list", body={}).payload[
        "contacts"
    ][0]
    assert after["opt_out"] is True
    assert after["sendable"] is False
    assert after["first_name"] == "عضو تازه"
    api.close()
