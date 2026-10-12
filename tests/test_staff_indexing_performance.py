"""Tests for staff attribution in content indexing, manager overrides, KPI calculation, and defect tasks."""

from datetime import datetime, timezone
import tempfile
from pathlib import Path
import pytest

from eitaa_bridge.infrastructure.content_index_store import (
    CONTENT_INDEX_SCHEMA,
    SQLiteContentIndexStore,
)


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_content_index.db"
        store = SQLiteContentIndexStore(db_path)
        store.initialize()
        yield store


def test_schema_version_and_settings(temp_store: SQLiteContentIndexStore):
    assert CONTENT_INDEX_SCHEMA == 5
    default_strategy = temp_store.get_setting("auto_index_on_load", "false")
    assert default_strategy == "false"

    temp_store.set_setting("auto_index_on_load", "true")
    assert temp_store.get_setting("auto_index_on_load") == "true"


def test_staff_feedback_attribution_and_manager_override(temp_store: SQLiteContentIndexStore):
    site_key = "local"
    peer_type = "channel"
    peer_id = 6015778
    message_id = 1001
    label_id = 80402
    label_name = "مناسبت‌های ملی و مذهبی"

    # 1. Staff employee "user_ali" accepts the index
    fb_id1 = temp_store.add_feedback(
        site_key=site_key,
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="accept",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="usr_ali_123",
        operator_name="علی محمدی",
        operator_role="user",
    )
    assert fb_id1 > 0

    # Verify that list_results shows Ali's attribution and pending review status
    results = temp_store.list_results(site_key="different_account_site", peer_type=peer_type, peer_id=peer_id)
    assert len(results) == 1
    assert results[0]["message_id"] == message_id
    assert results[0]["operator_name"] == "علی محمدی"
    assert results[0]["operator_role"] == "user"
    assert results[0]["review_status"] == "pending"
    preds = results[0]["predictions"]
    assert len(preds) == 1
    assert preds[0]["label_id"] == label_id
    assert preds[0]["operator_name"] == "علی محمدی"

    # Check action logs
    actions = temp_store.list_actions(operator_id="usr_ali_123")
    assert len(actions) == 1
    assert actions[0]["operator_name"] == "علی محمدی"
    assert actions[0]["new_decision"] == "accept"
    assert actions[0]["is_manager_override"] is False

    # 2. Manager "admin_reza" overrides Ali's decision by rejecting this label
    fb_id2 = temp_store.add_feedback(
        site_key=site_key,
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="reject",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="adm_reza_999",
        operator_name="رضا مدیر",
        operator_role="admin",
    )
    assert fb_id2 > 0

    # Verify that list_actions records manager override
    mgr_actions = temp_store.list_actions(limit=10)
    assert len(mgr_actions) == 2
    assert mgr_actions[0]["operator_role"] == "admin"
    assert mgr_actions[0]["is_manager_override"] is True
    assert mgr_actions[0]["previous_decision"] == "accept"
    assert mgr_actions[0]["new_decision"] == "reject"

    # Verify performance scorecard for Ali reflects the manager override
    perf = temp_store.get_staff_performance()
    ali_perf = next((item for item in perf if item["operator_id"] == "usr_ali_123"), None)
    assert ali_perf is not None
    assert ali_perf["total_actions"] == 1
    assert ali_perf["override_count"] == 1
    # 0% accuracy since 1 out of 1 was overridden
    assert ali_perf["accuracy_rate"] == 0.0

    # 3. Ali indexes a second message correctly and manager does not override it
    temp_store.add_feedback(
        site_key=site_key,
        source_key=f"{peer_type}:{peer_id}:1002",
        label_id=80501,
        label_name= "ترویج نماز",
        decision="accept",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=1002,
        operator_id="usr_ali_123",
        operator_name="علی محمدی",
        operator_role="user",
    )

    perf2 = temp_store.get_staff_performance()
    ali_perf2 = next((item for item in perf2 if item["operator_id"] == "usr_ali_123"), None)
    assert ali_perf2 is not None
    assert ali_perf2["total_actions"] == 2
    assert ali_perf2["override_count"] == 1
    # 1 out of 2 overridden => 50% accuracy
    assert ali_perf2["accuracy_rate"] == 50.0


def test_staff_tasks_workflow(temp_store: SQLiteContentIndexStore):
    # Manager creates a defect follow-up task
    task = temp_store.create_task(
        title="نقص در تعداد نفرات نماز جماعت",
        description="لطفاً با رابط سوادکوه تماس بگیرید و تعداد نمازگزاران را دریافت کنید.",
        defect_type="missing_attendees",
        priority="high",
        peer_type="channel",
        peer_id=6015778,
        message_id=1005,
        assigned_to_user_id="usr_ali_123",
        assigned_to_name="علی محمدی",
        created_by_user_id="adm_reza_999",
        created_by_name="رضا مدیر",
    )
    assert task["task_id"]
    assert task["status"] == "open"
    assert task["priority"] == "high"

    # Ali lists his assigned tasks
    ali_tasks = temp_store.list_tasks(assigned_to_user_id="usr_ali_123", status="open")
    assert len(ali_tasks) == 1
    task_id = ali_tasks[0]["task_id"]
    assert ali_tasks[0]["title"] == "نقص در تعداد نفرات نماز جماعت"

    # Ali resolves the task
    res = temp_store.resolve_task(
        task_id=task_id,
        resolution_notes="تعداد ۳۵ نفر اعلام شد و در فرم ثبت گردید.",
        user_id="usr_ali_123",
        user_name="علی محمدی",
    )
    assert res["status"] == "resolved"

    # Manager closes the task
    close_res = temp_store.close_task(
        task_id=task_id,
        manager_id="adm_reza_999",
        manager_name="رضا مدیر",
    )
    assert close_res["status"] == "closed"

    # Verify task resolution is reflected in staff performance
    perf = temp_store.get_staff_performance()
    ali_perf = next((item for item in perf if item["operator_id"] == "usr_ali_123"), None)
    if ali_perf:
        assert ali_perf["assigned_tasks"] == 1
        assert ali_perf["resolved_tasks"] == 1
        assert ali_perf["task_resolution_rate"] == 100.0


def test_api_staff_and_indexing_endpoints(temp_store: SQLiteContentIndexStore, monkeypatch):
    from eitaa_bridge.application.api import BridgeApplicationApi
    from unittest.mock import MagicMock

    # Create dummy API instance with mocked config/runtime
    api = MagicMock(spec=BridgeApplicationApi)
    api._content_index_store = temp_store
    api._content_index_lock = MagicMock()
    api.config = MagicMock()
    api.config.features.multi_session.enabled = False

    # Bind the actual methods under test from BridgeApplicationApi
    api._staff_performance = BridgeApplicationApi._staff_performance.__get__(api)
    api._staff_tasks_list = BridgeApplicationApi._staff_tasks_list.__get__(api)
    api._staff_tasks_create = BridgeApplicationApi._staff_tasks_create.__get__(api)
    api._staff_tasks_resolve = BridgeApplicationApi._staff_tasks_resolve.__get__(api)
    api._staff_tasks_close = BridgeApplicationApi._staff_tasks_close.__get__(api)
    api._staff_tasks_reassign = BridgeApplicationApi._staff_tasks_reassign.__get__(api)
    api._staff_tasks_checklist = BridgeApplicationApi._staff_tasks_checklist.__get__(api)
    api._indexing_strategy_get = BridgeApplicationApi._indexing_strategy_get.__get__(api)
    api._indexing_strategy_set = BridgeApplicationApi._indexing_strategy_set.__get__(api)

    # 1. Test indexing strategy GET and POST
    res_strat_get = api._indexing_strategy_get()
    assert res_strat_get.status == 200
    assert res_strat_get.payload["auto_index_on_load"] is False

    res_strat_set = api._indexing_strategy_set(payload={"auto_index_on_load": True})
    assert res_strat_set.status == 200
    assert res_strat_set.payload["auto_index_on_load"] is True
    assert api._indexing_strategy_get().payload["auto_index_on_load"] is True

    # 2. Test staff performance endpoint
    res_perf = api._staff_performance(query={})
    assert res_perf.status == 200
    assert res_perf.payload["ok"] is True
    assert "summary" in res_perf.payload
    assert "staff" in res_perf.payload

    # 3. Test staff tasks lifecycle via API
    create_res = api._staff_tasks_create(
        payload={
            "message_ref": "channel:100:200",
            "defect_type": "ambiguous_program",
            "description": "نیاز به بررسی نوع مراسم",
            "assigned_to": "usr_reza",
            "assigned_to_name": "رضا کارمند",
            "priority": "high",
        }
    )
    assert create_res.status == 201
    task_id = create_res.payload["task_id"]
    assert bool(task_id)

    list_res = api._staff_tasks_list(query={"status": "open"})
    assert list_res.status == 200
    assert len(list_res.payload["tasks"]) >= 1

    resolve_res = api._staff_tasks_resolve(
        payload={
            "task_id": task_id,
            "resolution_notes": "نوع مراسم بررسی و مراسم جشن تعیین شد.",
            "resolved_by": "رضا کارمند",
        }
    )
    assert resolve_res.status == 200
    assert resolve_res.payload["ok"] is True

    close_res = api._staff_tasks_close(
        payload={
            "task_id": task_id,
            "approved": True,
            "feedback_notes": "تایید شد، متشکرم.",
            "closed_by": "مدیر سیستم",
        }
    )
    assert close_res.status == 200
    assert close_res.payload["status"] == "closed"


def test_enterprise_task_macro_categories_checklist_and_reassignment(temp_store: SQLiteContentIndexStore):
    from eitaa_bridge.application.api import BridgeApplicationApi
    from unittest.mock import MagicMock

    api = MagicMock(spec=BridgeApplicationApi)
    api._content_index_store = temp_store
    api._staff_tasks_list = BridgeApplicationApi._staff_tasks_list.__get__(api)
    api._staff_tasks_create = BridgeApplicationApi._staff_tasks_create.__get__(api)
    api._staff_tasks_resolve = BridgeApplicationApi._staff_tasks_resolve.__get__(api)
    api._staff_tasks_close = BridgeApplicationApi._staff_tasks_close.__get__(api)
    api._staff_tasks_reassign = BridgeApplicationApi._staff_tasks_reassign.__get__(api)
    api._staff_tasks_checklist = BridgeApplicationApi._staff_tasks_checklist.__get__(api)

    # 1. Create a task with macro_category = 'workbook_approved' and multi-program codes
    task1 = api._staff_tasks_create(
        payload={
            "title": "برگزاری مشترک مسابقات و اردوی زیارتی",
            "macro_category": "workbook_approved",
            "program_codes": ["80401", "80402"],
            "task_kind": "field_execution",
            "unit_scope": "judicial_domain",
            "unit_name": "دادگستری شهرستان کاشان",
            "priority": "high",
            "assigned_to": "usr_sara",
            "assigned_to_name": "سارا محمدی",
            "due_date": "2026-11-01",
            "checklist": [
                {"id": "c1", "text": "اخذ بیمه‌نامه معتبر پیش از حرکت", "done": False},
                {"id": "c2", "text": "ثبت احکام داوران مسابقات", "done": False},
            ],
            "requires_manager_approval": True,
        }
    )
    assert task1.status == 201
    tid1 = task1.payload["task_id"]

    # 2. Create a task with macro_category = 'other_cultural' (out-of-sheet activity)
    task2 = api._staff_tasks_create(
        payload={
            "title": "پویش همدلی و توزیع بسته‌های معیشتی غدیر",
            "macro_category": "other_cultural",
            "custom_topic": "کمک‌های مؤمنانه و پویش جهادی غدیر",
            "task_kind": "field_execution",
            "unit_scope": "provincial_hq",
            "unit_name": "ستاد کل استان",
            "priority": "urgent",
            "assigned_to": "usr_ali",
            "assigned_to_name": "علی اکبری",
            "due_date": "2026-10-20",
            "checklist": [
                {"id": "c1", "text": "هماهنگی با ستاد اجرایی فرمان امام", "done": True},
                {"id": "c2", "text": "تهیه مستندات تصویری جهت انتشار", "done": False},
            ],
        }
    )
    assert task2.status == 201
    tid2 = task2.payload["task_id"]

    # 3. Filter by macro_category = 'workbook_approved'
    wb_list = api._staff_tasks_list(query={"macro_category": "workbook_approved"})
    assert wb_list.status == 200
    assert any(t["task_id"] == tid1 for t in wb_list.payload["tasks"])
    assert not any(t["task_id"] == tid2 for t in wb_list.payload["tasks"])
    t1_retrieved = next(t for t in wb_list.payload["tasks"] if t["task_id"] == tid1)
    assert t1_retrieved["program_codes"] == ["80401", "80402"]
    assert t1_retrieved["unit_name"] == "دادگستری شهرستان کاشان"
    assert len(t1_retrieved["checklist"]) == 2

    # 4. Filter by macro_category = 'other_cultural'
    other_list = api._staff_tasks_list(query={"macro_category": "other_cultural"})
    assert other_list.status == 200
    assert any(t["task_id"] == tid2 for t in other_list.payload["tasks"])
    t2_retrieved = next(t for t in other_list.payload["tasks"] if t["task_id"] == tid2)
    assert t2_retrieved["custom_topic"] == "کمک‌های مؤمنانه و پویش جهادی غدیر"

    # 5. Interactive Checklist update via API
    chk_res = api._staff_tasks_checklist(
        payload={
            "task_id": tid1,
            "checklist": [
                {"id": "c1", "text": "اخذ بیمه‌نامه معتبر پیش از حرکت", "done": True},
                {"id": "c2", "text": "ثبت احکام داوران مسابقات", "done": True},
            ],
        }
    )
    assert chk_res.status == 200
    assert chk_res.payload["ok"] is True

    # 6. Reassignment due to employee negligence / handover
    reassign_res = api._staff_tasks_reassign(
        payload={
            "task_id": tid2,
            "new_user_id": "usr_hossein",
            "new_user_name": "حسین کریمی",
            "reassigned_by_name": "مدیر اداره",
            "reason": "عدم اقدام کارمند در مهلت مقرر و فوریت موضوع",
        }
    )
    assert reassign_res.status == 200
    assert reassign_res.payload["assigned_to_user_id"] == "usr_hossein"
    assert reassign_res.payload["assigned_to_name"] == "حسین کریمی"
    assert reassign_res.payload["status"] == "open"
    assert "عدم اقدام کارمند در مهلت مقرر" in reassign_res.payload["resolution_notes"]

    # 7. Complete and close task 1
    api._staff_tasks_resolve(
        payload={
            "task_id": tid1,
            "resolution_notes": "بیمه‌نامه اخذ و اسامی داوران در کاربرگ درج گردید.",
            "resolved_by": "سارا محمدی",
        }
    )
    closed = api._staff_tasks_close(
        payload={"task_id": tid1, "approved": True, "closed_by": "مدیر فرهنگی"}
    )
    assert closed.status == 200
    assert closed.payload["status"] == "closed"

