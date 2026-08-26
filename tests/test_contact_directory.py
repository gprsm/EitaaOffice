from __future__ import annotations

import base64
from io import BytesIO
import json
import sqlite3
import threading
import time
import zipfile

import pytest

from eitaa_bridge.application.contact_import import map_contact_rows, parse_tabular
from eitaa_bridge.infrastructure.contact_store import (
    CONTACT_SCHEMA,
    SQLiteContactStore,
    normalize_phone,
)
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.errors import CompositionValidationError


def _wait_for_import(api: BridgeApplicationApi, job_id: str) -> dict:
    for _ in range(500):
        job = api.dispatch(
            "GET", f"/api/v1/contacts/import/status?job_id={job_id}"
        ).payload["job"]
        if job["state"] not in {"queued", "running", "cancelling"}:
            return job
        time.sleep(0.01)
    raise AssertionError("contact import did not finish")


def test_phone_normalization_and_multi_phone_deduplication(tmp_path) -> None:
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    first = store.upsert_contact(
        {
            "first_name": "علی",
            "phones": ["09121234567", "+98 912 123 4568"],
            "source": "manual",
        }
    )
    assert first["phones"] == ["+989121234567", "+989121234568"]
    duplicate = store.upsert_contact(
        {"first_name": "رکورد تکراری", "phones": ["0098 912 123 4567"]}
    )
    assert duplicate["id"] == first["id"]
    assert duplicate["duplicate"] is True
    assert len(store.list_contacts()) == 1
    assert normalize_phone("9121234567") == "+989121234567"


def test_many_to_many_categories_and_safe_category_delete(tmp_path) -> None:
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    friends = store.save_category(name="دوستان")
    project = store.save_category(name="پروژه")
    contact = store.upsert_contact(
        {
            "first_name": "زهرا",
            "phones": ["09120000000"],
            "category_ids": [friends["id"], project["id"]],
        }
    )
    assert {item["name"] for item in contact["categories"]} == {"دوستان", "پروژه"}
    store.delete_category(project["id"])
    remaining = store.list_contacts()[0]
    assert [item["name"] for item in remaining["categories"]] == ["دوستان"]
    assert len(store.list_contacts()) == 1


def test_target_builder_excludes_opt_out_not_sendable_and_duplicate_numbers(tmp_path) -> None:
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    category = store.save_category(name="هدف")
    common = {"category_ids": [category["id"]]}
    store.upsert_contact({**common, "first_name": "مجاز", "phones": ["09120000001"]})
    store.upsert_contact({**common, "first_name": "انصراف", "phones": ["09120000002"], "opt_out": True})
    store.upsert_contact({**common, "first_name": "مسدود", "phones": ["09120000003"], "sendable": False})
    result = store.build_targets(category_ids=[category["id"]])
    assert result["target_count"] == 1
    assert result["targets"][0]["phone"] == "+989120000001"
    assert result["omitted"]["opt_out"] == 1
    assert result["omitted"]["not_sendable"] == 1


def test_import_missing_optional_columns_and_cancel(tmp_path) -> None:
    headers, rows = parse_tabular(
        "نام,شماره تماس\nمریم,09120000004\n,09120000005\n".encode("utf-8"),
        "contacts.csv",
    )
    mapped = map_contact_rows(headers, rows, {"first_name": 0, "phone": 1})
    assert len(mapped) == 2
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    cancelled = threading.Event()
    cancelled.set()
    result = store.import_rows(mapped, cancel_event=cancelled)
    assert result["cancelled"] is True
    assert result["processed"] == 0


def test_minimal_xlsx_mapping() -> None:
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1"><c r="A1" t="inlineStr"><is><t>نام</t></is></c><c r="B1" t="inlineStr"><is><t>شماره تماس</t></is></c></row>
                <row r="2"><c r="A2" t="inlineStr"><is><t>سارا</t></is></c><c r="B2" t="inlineStr"><is><t>09120000006</t></is></c></row>
              </sheetData>
            </worksheet>""",
        )
    headers, rows = parse_tabular(content.getvalue(), "contacts.xlsx")
    mapped = map_contact_rows(headers, rows, {"first_name": 0, "phone": 1})
    assert mapped[0]["first_name"] == "سارا"
    assert mapped[0]["phones"] == ["09120000006"]


def test_unmapped_optional_columns_are_not_emitted() -> None:
    mapped = map_contact_rows(
        ["نام", "شماره"],
        [["سارا", "09120000006"]],
        {"first_name": 0, "phone": 1},
    )
    assert mapped[0]["first_name"] == "سارا"
    assert "last_name" not in mapped[0]
    assert "notes" not in mapped[0]


def test_repeated_file_import_updates_one_contact_and_merges_categories(
    config_file,
) -> None:
    api = BridgeApplicationApi(config_file)
    first_category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "همکاران"}
    ).payload["category"]
    second_category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "پروژه دوم"}
    ).payload["category"]

    def import_csv(first_name: str, category_id: int) -> dict:
        content = f"نام,شماره\n{first_name},09121234567\n".encode("utf-8")
        started = api.dispatch(
            "POST",
            "/api/v1/contacts/import/start",
            body={
                "site_key": "medical-site",
                "file_name": "contacts.csv",
                "content_base64": base64.b64encode(content).decode("ascii"),
                "mapping": {"first_name": 0, "phone": 1},
                "category_ids": [category_id],
            },
        )
        assert started.status == 202
        return _wait_for_import(api, started.payload["job"]["job_id"])

    first = import_csv("نام اولیه", first_category["id"])
    second = import_csv("نام به‌روزشده", second_category["id"])
    assert first["progress"]["imported"] == 1
    assert second["progress"]["updated"] == 1

    listed = api.dispatch("POST", "/api/v1/contacts/list", body={}).payload
    assert listed["total"] == 1
    contact = listed["contacts"][0]
    assert contact["first_name"] == "نام به‌روزشده"
    assert {item["name"] for item in contact["categories"]} == {
        "همکاران",
        "پروژه دوم",
    }
    api.close()


def test_eitaa_file_import_requires_first_name_mapping(config_file) -> None:
    api = BridgeApplicationApi(config_file)
    content = base64.b64encode("شماره\n09121234567\n".encode("utf-8")).decode("ascii")
    response = api.dispatch(
        "POST",
        "/api/v1/contacts/import/start",
        body={
            "site_key": "medical-site",
            "file_name": "contacts.csv",
            "content_base64": content,
            "mapping": {"phone": 0},
            "add_to_eitaa": True,
        },
    )
    assert response.status == 400
    assert (
        response.payload["error"]["error_code"]
        == "api_contact_import_first_name_mapping_required"
    )
    api.close()


def test_file_import_continues_to_eitaa_with_json_compatible_contact_ids(
    config_file, monkeypatch
) -> None:
    api = BridgeApplicationApi(config_file)
    remote_calls: list[dict] = []

    def fake_add(payload):
        remote_calls.append(dict(payload))
        return {
            "ok": True,
            "contact_added": True,
            "contact_updated": False,
            "contact": {"user_id": 9000 + len(remote_calls)},
        }

    monkeypatch.setattr(api, "_eitaa_contacts_add", fake_add)
    content = base64.b64encode(
        b"first_name,phone\nTest One,09120000041\nTest Two,09120000042\n"
    ).decode("ascii")
    started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/start",
        body={
            "site_key": "medical-site",
            "file_name": "contacts.csv",
            "content_base64": content,
            "mapping": {"first_name": 0, "phone": 1},
            "add_to_eitaa": True,
        },
    )
    assert started.status == 202
    job = _wait_for_import(api, started.payload["job"]["job_id"])
    assert job["state"] == "completed"
    assert job["progress"]["remote_state"] == "completed"
    assert job["progress"]["eitaa_added"] == 2
    assert len(remote_calls) == 2
    api.close()


def test_file_import_surfaces_and_logs_remote_background_failure(
    config_file, monkeypatch
) -> None:
    api = BridgeApplicationApi(config_file)

    def reject_contact(payload):
        raise CompositionValidationError(
            "Remote contact import was rejected for this test.",
            code="api_test_remote_contact_error",
        )

    monkeypatch.setattr(api, "_eitaa_contacts_add", reject_contact)
    content = base64.b64encode(
        b"first_name,phone\nTest Contact,09120000043\n"
    ).decode("ascii")
    started = api.dispatch(
        "POST",
        "/api/v1/contacts/import/start",
        body={
            "site_key": "medical-site",
            "file_name": "contacts.csv",
            "content_base64": content,
            "mapping": {"first_name": 0, "phone": 1},
            "add_to_eitaa": True,
        },
    )
    job = _wait_for_import(api, started.payload["job"]["job_id"])
    assert job["state"] == "failed"
    assert job["error"]["message"] == "Remote contact import was rejected for this test."
    assert job["error"]["error_code"] == "eitaa_contact_import_all_failed"
    api.close()

    log_path = api.base_directory / "runtime" / "logs" / "application.jsonl"
    events = [
        json.loads(line)["event"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "eitaa_contact_import_item_failed" in events
    assert "contact_source_import_failed" in events
    assert "contact_import_failed" in events


def test_schema_rejects_newer_database_without_modifying_it(tmp_path) -> None:
    path = tmp_path / "contacts.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version={CONTACT_SCHEMA + 1}")
    with pytest.raises(Exception, match="newer"):
        SQLiteContactStore(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CONTACT_SCHEMA + 1


def test_contact_api_is_local_and_category_delete_preserves_contact(
    config_file, monkeypatch
) -> None:
    api = BridgeApplicationApi(config_file)
    monkeypatch.setattr(
        api,
        "_run_eitaa",
        lambda *args, **kwargs: pytest.fail("contact database operations must not use Eitaa scheduler"),
    )
    category = api.dispatch(
        "POST", "/api/v1/contacts/categories/save", body={"name": "همکاران"}
    )
    assert category.status == 200
    category_id = category.payload["category"]["id"]
    saved = api.dispatch(
        "POST",
        "/api/v1/contacts/upsert",
        body={
            "contact": {
                "first_name": "امین",
                "phones": ["09120000009"],
                "category_ids": [category_id],
            }
        },
    )
    assert saved.status == 200
    deleted = api.dispatch(
        "POST",
        "/api/v1/contacts/categories/delete",
        body={"category_id": category_id, "confirm": True},
    )
    assert deleted.payload["contacts_deleted"] == 0
    listed = api.dispatch("POST", "/api/v1/contacts/list", body={})
    assert len(listed.payload["contacts"]) == 1
    assert listed.payload["contacts"][0]["categories"] == []
    api.close()


def test_target_builder_caps_large_payloads_for_ui_stability(tmp_path) -> None:
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    for index in range(5):
        store.upsert_contact({"first_name": f"مخاطب {index}", "phones": [f"091200001{index:02d}"]})
    result = store.build_targets(max_targets=3)
    assert result["target_count"] == 3
    assert result["truncated"] is True
    assert result["max_targets"] == 3
    with pytest.raises(ValueError, match="max_targets"):
        store.build_targets(max_targets=10_001)
