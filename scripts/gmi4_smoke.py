"""Deterministic no-network smoke suite for source and installed-wheel validation."""

from __future__ import annotations

import json
import gc
import os
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace

from eitaa_core import Peer, PeerType, save_peer_file

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.contact_import import map_contact_rows, parse_tabular
from eitaa_bridge.infrastructure.contact_store import CONTACT_SCHEMA, SQLiteContactStore
from eitaa_bridge.version import __version__
if os.getenv("GMI4_SKIP_LAB") != "1":
    from lab.multi_account_coordinator import (
        AccountWorkerSpec,
        IsolatedAccountCoordinator,
        RecipientTask,
    )


checks = 0


def expect(condition: bool, message: str) -> None:
    global checks
    if not condition:
        raise AssertionError(message)
    checks += 1


def config(root: Path) -> Path:
    payload = {
        "schema_version": 1,
        "default_site_key": "test-site",
        "bridge": {"diagnostics_root": "diagnostics/bridge", "diagnostics_enabled": False},
        "core": {
            "session_file": ".session.json",
            "database_file": "data/messages.sqlite3",
            "media_directory": "data/media",
            "diagnostics_root": "diagnostics/core",
            "diagnostics_enabled": False,
            "timeout_seconds": 30,
        },
        "wordpress_sites": [{
            "site_key": "test-site",
            "base_url": "https://example.test",
            "default_status": "draft",
            "default_category_id": 12,
            "verify_tls": True,
            "username_env": "TEST_WP_USER",
            "application_password_env": "TEST_WP_PASSWORD",
        }],
    }
    path = root / "bridge.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


with tempfile.TemporaryDirectory(prefix="eitaa-gmi4-smoke-", ignore_cleanup_errors=True) as selected:
    expect(__version__ == "0.7.0-ui-mvp6.1.1-gmi4.2", "GMI4 product version")
    root = Path(selected)
    path = root / "contacts.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE legacy_probe(value TEXT)")
    store = SQLiteContactStore(path)
    store.initialize()
    expect(
        any(root.glob("contacts.schema0.*.bak.sqlite3")),
        "schema-0 contact database must be backed up",
    )
    with sqlite3.connect(path) as connection:
        expect(connection.execute("PRAGMA user_version").fetchone()[0] == CONTACT_SCHEMA, "contact schema")

    category_a = store.save_category(name="دوستان")
    category_b = store.save_category(name="پروژه")
    contact = store.upsert_contact(
        {
            "first_name": "مریم",
            "phones": ["09121234567", "+98 912 123 4568"],
            "category_ids": [category_a["id"], category_b["id"]],
        }
    )
    expect(len(contact["phones"]) == 2, "multiple phones")
    expect(len(contact["categories"]) == 2, "multiple categories")
    duplicate = store.upsert_contact({"first_name": "تکراری", "phones": ["00989121234567"]})
    expect(duplicate.get("duplicate") is True, "duplicate phone prevention")
    store.delete_category(category_b["id"])
    expect(len(store.list_contacts()) == 1, "category deletion must preserve contact")
    store.upsert_contact({"id": contact["id"], "phones": contact["phones"], "opt_out": True})
    targets = store.build_targets()
    expect(targets["target_count"] == 0 and targets["omitted"]["opt_out"] == 1, "opt-out target exclusion")

    headers, rows = parse_tabular(
        "نام,شماره تماس,دسته\nرضا,09120000001,همکاران\n".encode("utf-8"),
        "contacts.csv",
    )
    mapped = map_contact_rows(headers, rows, {"first_name": 0, "phone": 1, "category": 2})
    expect(mapped[0]["category_names"] == ["همکاران"], "CSV mapping")
    cancellation = threading.Event()
    cancellation.set()
    cancelled = store.import_rows(mapped, cancel_event=cancellation)
    expect(cancelled["cancelled"] is True and cancelled["processed"] == 0, "import cancellation")

    if os.getenv("GMI4_SKIP_LAB") != "1":
        workers = [
            AccountWorkerSpec(
                account_id=name,
                scheduler_id=f"scheduler-{name}",
                session_path=root / name / "session.json",
                database_path=root / name / "state.sqlite3",
                diagnostics_path=root / name / "diagnostics",
                max_tasks_per_plan=2,
            )
            for name in ("a", "b")
        ]
        plan = IsolatedAccountCoordinator(workers).plan(
            [
                RecipientTask("one", "+989120000001"),
                RecipientTask("duplicate", "+989120000001"),
                RecipientTask("optout", "+989120000002", opt_out=True),
                RecipientTask("two", "+989120000003"),
            ]
        )
        expect(len(plan.assignments) == 2, "multi-account assignments")
        expect(plan.omitted_duplicates == ("duplicate",), "multi-account duplicate prevention")
        expect(plan.omitted_opt_out == ("optout",), "multi-account opt-out prevention")
        expect(
            len({item.scheduler_id for item in plan.assignments}) == 2,
            "workers own distinct schedulers",
        )

    api = BridgeApplicationApi(config(root))
    api._run_eitaa = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("local contact/index operation touched the Eitaa scheduler")
    )
    saved_category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "API"}
    )
    expect(saved_category.status == 200, "contact category API")
    saved_contact = api.dispatch(
        "POST",
        "/api/v1/contacts/upsert",
        body={"contact": {"first_name": "API", "phones": ["09120000007"]}},
    )
    expect(saved_contact.status == 200, "contact upsert API")
    import_content = base64.b64encode(
        "نام,شماره تماس,دسته\nفایل,09120000008,استان تهران\n".encode("utf-8")
    ).decode("ascii")
    preview = api.dispatch(
        "POST",
        "/api/v1/contacts/import/preview",
        body={"file_name": "contacts.csv", "content_base64": import_content},
    )
    expect(preview.payload["row_count"] == 1, "contact import preview API")
    started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/start",
        body={
            "file_name": "contacts.csv",
            "content_base64": import_content,
            "mapping": {"first_name": 0, "phone": 1, "category": 2},
            "category_ids": [],
        },
    )
    job_id = started.payload["job"]["job_id"]
    status = None
    for _ in range(200):
        status = api.dispatch("GET", f"/api/v1/contacts/import/status?job_id={job_id}")
        if status.payload["job"]["state"] not in {"queued", "running", "cancelling"}:
            break
        time.sleep(0.01)
    expect(status is not None and status.payload["job"]["state"] == "completed", "async contact import")
    imported_contacts = api.dispatch("POST", "/api/v1/contacts/list", body={})
    expect(len(imported_contacts.payload["contacts"]) == 2, "imported contact visible")
    imported_categories = api.dispatch("GET", "/api/v1/contacts/categories")
    expect(
        any(item["name"] == "استان تهران" for item in imported_categories.payload["categories"]),
        "category column import",
    )

    peer = Peer(type=PeerType.CHANNEL, id=1234, access_hash=5678, title="آزمون")
    peer_file = root / "peer.json"
    save_peer_file(peer_file, peer)
    api._content_index_store.initialize()
    api._content_index_store.save_results(
        site_key="test-site",
        peer_type=peer.type.value,
        peer_id=peer.id,
        model_version="smoke",
        rows=[{
            "message_id": 41,
            "text_hash": "hash",
            "predictions": [{"label_id": 12, "label_name": "قدیمی", "score": .8, "evidence": [], "accepted": True}],
        }],
    )
    api.dispatch(
        "POST",
        "/api/v1/messages/index/feedback",
        body={
            "site_key": "test-site",
            "peer_file": str(peer_file),
            "message_id": 41,
            "label_id": 12,
            "label_name": "قدیمی",
            "decision": "reject",
        },
    )
    api.dispatch(
        "POST",
        "/api/v1/messages/index/feedback",
        body={
            "site_key": "test-site",
            "peer_file": str(peer_file),
            "message_id": 41,
            "label_id": 15,
            "label_name": "اصلاح‌شده",
            "decision": "accept",
        },
    )
    result = api.dispatch(
        "POST",
        "/api/v1/messages/index/results",
        body={"site_key": "test-site", "peer_file": str(peer_file)},
    )
    predictions = result.payload["results"][0]["predictions"]
    expect([item["label_id"] for item in predictions] == [15], "immediate manual correction")
    expect(predictions[0]["manual"] is True, "manual correction marker")

    source_category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "منبع ایتا"}
    ).payload["category"]
    user_peer = SimpleNamespace(
        id=501, access_hash=987654321, username="member501"
    )
    member_user = SimpleNamespace(
        peer=user_peer,
        first_name="عضو",
        last_name="آزمایشی",
        username="member501",
        phone="+989121234569",
        is_deleted=False,
    )
    member = SimpleNamespace(user=member_user, is_sendable=True)
    member_page = SimpleNamespace(members=(member,), total_count=1, next_offset=None)
    resolved_user = SimpleNamespace(
        peer=user_peer,
        first_name="عضو تازه",
        last_name="آزمایشی",
        username="member501",
        is_deleted=False,
    )
    resolved_entry = SimpleNamespace(
        user=resolved_user,
        phone="+989121234569",
        first_name="نام فهرست",
        last_name="",
        resolved_at=datetime.now(timezone.utc),
    )
    fake_phone_lists = SimpleNamespace(
        status=lambda list_id: SimpleNamespace(total_rows=1),
        entries=lambda list_id, offset, limit: (
            (resolved_entry,) if offset == 0 else ()
        ),
    )
    fake_bridge = SimpleNamespace(
        core=SimpleNamespace(
            members=SimpleNamespace(search_local=lambda query: member_page),
            phone_lists=fake_phone_lists,
        )
    )

    @contextmanager
    def open_fake_bridge(*args, **kwargs):
        yield fake_bridge

    api._open_bridge = open_fake_bridge

    def wait_contact_job(job_id: str) -> dict:
        for _ in range(500):
            response = api.dispatch(
                "GET", f"/api/v1/contacts/import/status?job_id={job_id}"
            )
            job = response.payload["job"]
            if job["state"] not in {"queued", "running", "cancelling"}:
                return job
            time.sleep(0.01)
        raise AssertionError("contact source import timeout")

    member_started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/community/start",
        body={
            "site_key": "test-site",
            "peer_file": str(peer_file),
            "member_ids": [501],
            "category_ids": [source_category["id"]],
        },
    )
    expect(member_started.status == 202, "community contact import start")
    expect(
        "987654321" not in repr(member_started.payload),
        "community import response hides access hash",
    )
    member_job = wait_contact_job(member_started.payload["job"]["job_id"])
    expect(
        member_job["state"] == "completed"
        and member_job["progress"]["imported"] == 1,
        "community contact import completion",
    )
    source_contact = next(
        item
        for item in api.dispatch(
            "POST", "/api/v1/contacts/list", body={}
        ).payload["contacts"]
        if item["eitaa_user_id"] == 501
    )
    expect(
        source_contact["access_hash_present"]
        and "987654321" not in repr(source_contact),
        "contact summary hides stored access hash",
    )
    api._contact_store.upsert_contact(
        {
            "id": source_contact["id"],
            "phones": source_contact["phones"],
            "sendable": False,
            "opt_out": True,
            "category_ids": [source_category["id"]],
        },
        duplicate_policy="update",
    )
    phone_started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/phone-list/start",
        body={
            "site_key": "test-site",
            "list_id": "resolved-list-1",
            "category_ids": [source_category["id"]],
        },
    )
    phone_job = wait_contact_job(phone_started.payload["job"]["job_id"])
    expect(
        phone_job["state"] == "completed"
        and phone_job["progress"]["updated"] == 1,
        "resolved phone-list contact import completion",
    )
    source_after = next(
        item
        for item in api.dispatch(
            "POST", "/api/v1/contacts/list", body={}
        ).payload["contacts"]
        if item["eitaa_user_id"] == 501
    )
    expect(
        source_after["opt_out"] is True and source_after["sendable"] is False,
        "source merge preserves operator safety status",
    )
    source_targets = api.dispatch(
        "POST",
        "/api/v1/contacts/targets/preview",
        body={"category_ids": [source_category["id"]]},
    )
    expect(
        source_targets.payload["target_count"] == 0
        and source_targets.payload["omitted"]["opt_out"] == 1,
        "target builder blocks imported opt-out contact",
    )
    expected_wheel = "dist\\eitaa_bridge-0.7.0.dev31-py3-none-any.whl"
    for installer_name in ("setup_venv.bat", "BUILD_OFFICE_SETUP_EXE.bat"):
        installer_text = (Path(__file__).resolve().parents[1] / installer_name).read_text(
            encoding="utf-8"
        )
        expect(
            expected_wheel in installer_text
            and "eitaa_bridge-0.7.0.dev27-py3-none-any.whl" not in installer_text,
            f"{installer_name} references the GMI4 bundled wheel",
        )
    api.close()
    del api
    gc.collect()

print(f"GMI4_SMOKE_OK checks={checks}")
