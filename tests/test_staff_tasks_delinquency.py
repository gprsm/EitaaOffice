"""Unit and integration tests for staff delinquency tracking, manager escalation,
overdue task penalties, and macro-category isolation in reporting events.
"""

from datetime import date, datetime, timezone, timedelta
import tempfile
from pathlib import Path
import pytest

from eitaa_bridge.infrastructure.content_index_store import (
    CONTENT_INDEX_SCHEMA,
    SQLiteContentIndexStore,
)
from eitaa_bridge.reporting.model import ReportedEvent, ProgramKind, ProgramId, UnitScope
from eitaa_bridge.reporting.store import ReportingStore
from eitaa_bridge.reporting.aggregate import aggregate_program_report, build_traceability_manifest


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_delinquency.db"
        store = SQLiteContentIndexStore(db_path)
        store.initialize()
        yield store


@pytest.fixture
def temp_reporting_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_delinquency_reporting.db"
        store = ReportingStore(db_path)
        store.initialize()
        yield store


# =========================================================================
# 1. Delinquency and Reassignment Provenance Tests
# =========================================================================

def test_delinquent_staff_reassignment_penalty(temp_store: SQLiteContentIndexStore):
    """When a task is revoked from a negligent staff member and reassigned,
    the negligent staff member must NOT have their delinquency erased, and their
    resolution rate must be penalized accordingly."""
    # Manager creates task for negligent employee Ali
    created = temp_store.create_task(
        title="ثبت گزارش عملکرد پایگاه بسیج",
        peer_type="channel",
        peer_id=777,
        message_id=101,
        assigned_to_user_id="usr_ali_negligent",
        assigned_to_name="علی اهمال‌کار",
        priority="high",
        due_date=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),  # overdue!
    )
    task_id = created["task_id"]
    assert task_id

    # Ali ignored the task. Manager Reza reassigns it to diligent employee Saeed
    reassigned = temp_store.reassign_task(
        task_id=task_id,
        new_assigned_to_user_id="usr_saeed_diligent",
        new_assigned_to_name="سعید پرتلاش",
        reassigned_by_id="mgr_reza",
        reassigned_by_name="رضا مدیر",
        reason="عدم اقدام در مهلت مقرر",
    )
    assert reassigned["assigned_to_user_id"] == "usr_saeed_diligent"
    assert reassigned["reassigned_from_user_id"] == "usr_ali_negligent"

    # Check task metadata in list_tasks
    tasks = temp_store.list_tasks()
    task = next(t for t in tasks if t["task_id"] == task_id)
    assert task["assigned_to_user_id"] == "usr_saeed_diligent"
    assert task["assigned_to_name"] == "سعید پرتلاش"
    assert task["reassigned_from_user_id"] == "usr_ali_negligent"
    assert task["reassigned_from_name"] == "علی اهمال‌کار"

    # Saeed resolves the task
    temp_store.resolve_task(
        task_id=task_id,
        resolution_notes="تکمیل و ارسال شد",
        user_id="usr_saeed_diligent",
        user_name="سعید پرتلاش",
    )

    # Evaluate performance for all staff
    perf = temp_store.get_staff_performance()
    perf_by_id = {p["operator_id"]: p for p in perf}

    # Verify Ali: 0 assigned, 1 revoked, 0 resolved -> resolution rate must be 0.0%, NOT 100%!
    ali_perf = perf_by_id["usr_ali_negligent"]
    assert ali_perf["assigned_tasks"] == 0
    assert ali_perf["revoked_tasks"] == 1
    assert ali_perf["resolved_tasks"] == 0
    assert ali_perf["task_resolution_rate"] == 0.0

    # Verify Saeed: 1 assigned, 0 revoked, 1 resolved -> resolution rate 100.0%
    saeed_perf = perf_by_id["usr_saeed_diligent"]
    assert saeed_perf["assigned_tasks"] == 1
    assert saeed_perf["revoked_tasks"] == 0
    assert saeed_perf["resolved_tasks"] == 1
    assert saeed_perf["task_resolution_rate"] == 100.0


def test_overdue_tasks_deduction_penalty(temp_store: SQLiteContentIndexStore):
    """Active overdue tasks must decrement the task_resolution_rate score."""
    # Employee Hossein has 2 assigned tasks: 1 resolved, 1 active overdue
    c1 = temp_store.create_task(
        title="وظیفه اول",
        peer_type="channel",
        peer_id=888,
        message_id=201,
        assigned_to_user_id="usr_hossein",
        assigned_to_name="حسین علوی",
        due_date=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    )
    t1 = c1["task_id"]

    c2 = temp_store.create_task(
        title="وظیفه دوم به تعویق افتاده",
        peer_type="channel",
        peer_id=888,
        message_id=202,
        assigned_to_user_id="usr_hossein",
        assigned_to_name="حسین علوی",
        due_date=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),  # overdue
    )
    t2 = c2["task_id"]

    # Hossein resolves task 1, leaves task 2 pending
    temp_store.resolve_task(task_id=t1, resolution_notes="انجام شد")

    perf = temp_store.get_staff_performance()
    h_perf = next(p for p in perf if p["operator_id"] == "usr_hossein")
    assert h_perf["assigned_tasks"] == 2
    assert h_perf["resolved_tasks"] == 1
    assert h_perf["overdue_tasks"] == 1
    # Base rate = 1 / 2 = 50.0%. Overdue penalty = 1 * 10.0% = 10.0% deduction -> 40.0%
    assert h_perf["task_resolution_rate"] == 40.0


# =========================================================================
# 2. Manager Escalation Mechanism Tests
# =========================================================================

def test_manager_task_escalation(temp_store: SQLiteContentIndexStore):
    """Manager escalates an overdue or neglected task, elevating priority and recording notes."""
    created = temp_store.create_task(
        title="بررسی فوری نقص آمار نمازخانه",
        peer_type="group",
        peer_id=999,
        message_id=301,
        assigned_to_user_id="usr_mehdi",
        assigned_to_name="مهدی کریمی",
        priority="low",
    )
    task_id = created["task_id"]

    # Manager escalates
    esc_result = temp_store.escalate_task(
        task_id=task_id,
        escalated_by_id="mgr_reza",
        escalated_by_name="رضا مدیر",
        notes="تذکر: مهلت انجام گذشته است، اولویت به اضطراری ارتقا یافت.",
    )
    assert esc_result["is_escalated"] is True
    assert esc_result["priority"] == "high"

    # Retrieve task
    tasks = temp_store.list_tasks()
    task = next(t for t in tasks if t["task_id"] == task_id)
    assert task["is_escalated"] is True
    assert task["priority"] == "high"
    assert "تذکر: مهلت انجام گذشته است" in task["escalation_notes"]
    assert task["escalated_at"] is not None


# =========================================================================
# 3. Macro Category & Custom Topic Reporting Tests
# =========================================================================

def test_macro_category_and_custom_topic_segregation(temp_reporting_store: ReportingStore):
    """Events with macro_category='other_cultural' must be segregated from canonical workbook sheets."""
    # 1. Canonical workbook event
    ev1 = ReportedEvent(
        event_id="ev_canonical_001",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(2024, 6, 24),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="مرکز استان",
        occasion="مراسم عید غدیر",
        macro_category="workbook_approved",
    )
    temp_reporting_store.save_event(ev1)

    # 2. Non-canonical other cultural event (custom topic, not in 7 canonical sheets)
    ev2 = ReportedEvent(
        event_id="ev_custom_002",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(2024, 6, 25),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="حوزه قضایی شهرستان",
        occasion="مسابقه نقاشی مهدکودک فرزندان پرسنل",
        macro_category="other_cultural",
        custom_topic="برنامه غیرابلاغی مهدکودک",
    )
    temp_reporting_store.save_event(ev2)

    # Verify retrieval from store preserves macro_category and custom_topic
    loaded_ev1 = temp_reporting_store.get_event("ev_canonical_001")
    assert loaded_ev1 is not None
    assert loaded_ev1.macro_category == "workbook_approved"
    assert loaded_ev1.custom_topic == ""

    loaded_ev2 = temp_reporting_store.get_event("ev_custom_002")
    assert loaded_ev2 is not None
    assert loaded_ev2.macro_category == "other_cultural"
    assert loaded_ev2.custom_topic == "برنامه غیرابلاغی مهدکودک"

    # Run workbook report aggregation
    all_events = temp_reporting_store.list_events()
    assert len(all_events) == 2

    # Aggregate for ceremonies program
    ceremonies_report = aggregate_program_report(ProgramId.CEREMONIES, all_events)
    # The canonical ceremonies report should count ev1, NOT ev2!
    # Because ev1 has CEREMONY kind, and ev2 was skipped due to macro_category="other_cultural"
    assert ceremonies_report.counts.get("ceremony", 0) == 1

    # Verify build_traceability_manifest also segregates other_cultural
    manifest = build_traceability_manifest(all_events)
    ceremony_manifest = manifest.get("programs", {}).get("ceremonies", {})
    manifest_event_ids = ceremony_manifest.get("event_ids", [])
    assert "ev_canonical_001" in manifest_event_ids
    assert "ev_custom_002" not in manifest_event_ids


# =========================================================================
# 4. API Endpoints Integration Tests
# =========================================================================

def test_api_staff_task_escalation_and_reassign(config_file: Path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    from eitaa_bridge.application.api import BridgeApplicationApi
    api = BridgeApplicationApi(config_file)

    # 1. Create a task via API
    create_resp = api.dispatch(
        "POST",
        "/api/v2/staff/tasks",
        body={
            "title": "ثبت مستندات مسابقات اذان",
            "peer_type": "channel",
            "peer_id": 12345,
            "message_id": 99,
            "assigned_to_user_id": "usr_api_delinquent",
            "assigned_to_name": "کارمند کم‌کار",
            "priority": "low",
        },
    )
    assert create_resp.status in (200, 201)
    assert create_resp.payload["ok"] is True
    task_id = create_resp.payload["task"]["task_id"]

    # 2. Escalate the task via manager endpoint
    esc_resp = api.dispatch(
        "POST",
        "/api/v2/staff/tasks/escalate",
        body={
            "task_id": task_id,
            "escalated_by_id": "mgr_api",
            "escalated_by_name": "مدیر کل",
            "notes": "اخطار انضباطی به دلیل تاخیر در انجام کار",
        },
    )
    assert esc_resp.status == 200
    assert esc_resp.payload["ok"] is True
    assert esc_resp.payload["task"]["is_escalated"] is True
    assert esc_resp.payload["task"]["priority"] == "high"

    # 3. Reassign to another user
    reassign_resp = api.dispatch(
        "POST",
        "/api/v2/staff/tasks/reassign",
        body={
            "task_id": task_id,
            "new_assigned_to_user_id": "usr_api_diligent",
            "new_assigned_to_name": "کارمند فعال",
            "reassigned_by_id": "mgr_api",
            "reassigned_by_name": "مدیر کل",
            "reason": "سلب صلاحیت به دلیل عدم اقدام",
        },
    )
    assert reassign_resp.status == 200
    assert reassign_resp.payload["ok"] is True
    assert reassign_resp.payload["task"]["assigned_to_user_id"] == "usr_api_diligent"
    assert reassign_resp.payload["task"]["reassigned_from_user_id"] == "usr_api_delinquent"

    # 4. Check staff performance via API
    perf_resp = api.dispatch("GET", "/api/v2/staff/performance")
    assert perf_resp.status == 200
    assert perf_resp.payload["ok"] is True
    summary = perf_resp.payload["summary"]
    assert "total_revoked" in summary
    assert "total_overdue" in summary
    assert summary["total_revoked"] >= 1


def test_api_reporting_events_macro_category(config_file: Path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    from eitaa_bridge.application.api import BridgeApplicationApi
    api = BridgeApplicationApi(config_file)

    # 1. Create an event with other_cultural macro_category and custom_topic
    ev_resp = api.dispatch(
        "POST",
        "/api/v2/reporting/events",
        body={
            "program_kinds": ["ceremony"],
            "occurred_on": "1403/06/15",
            "unit": "provincial_hq",
            "unit_name": "ستاد دادگستری",
            "occasion": "برنامه فرهنگی ورزشی پیاده‌روی خانوادگی",
            "macro_category": "other_cultural",
            "custom_topic": "پیاده‌روی سلامت پرسنل",
        },
    )
    assert ev_resp.status == 201
    assert ev_resp.payload["ok"] is True
    ev_id = ev_resp.payload["event_id"]

    # 2. List events with macro_category filter
    list_other = api.dispatch("GET", "/api/v2/reporting/events?macro_category=other_cultural")
    assert list_other.status == 200
    events_other = list_other.payload.get("events", [])
    matching = [e for e in events_other if e.get("event_id") == ev_id]
    assert len(matching) == 1
    assert matching[0]["macro_category"] == "other_cultural"
    assert matching[0]["custom_topic"] == "پیاده‌روی سلامت پرسنل"

