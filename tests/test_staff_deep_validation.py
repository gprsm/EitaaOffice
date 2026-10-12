"""Deep, rigorous end-to-end validation for staff indexing, global consistency, KPI isolation, and task workflows."""

from datetime import datetime, timezone, timedelta
import tempfile
from pathlib import Path
import pytest

from eitaa_bridge.infrastructure.content_index_store import (
    CONTENT_INDEX_SCHEMA,
    SQLiteContentIndexStore,
)
from eitaa_bridge.reporting.indexer import EitaaIntentIndexer, MessageIntent


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_deep_validation.db"
        store = SQLiteContentIndexStore(db_path)
        store.initialize()
        yield store


def test_global_multi_account_consistency(temp_store: SQLiteContentIndexStore):
    """Verify that indexes are shared globally across messenger accounts, and edits by one account
    are immediately visible to all other accounts without stale per-site caching."""
    peer_type = "channel"
    peer_id = 998877
    message_id = 555
    label_id = 80402
    label_name = "مناسبت‌های ملی و مذهبی"

    # Account 1 records an initial AI prediction
    temp_store.save_results(
        site_key="account_phone_1",
        peer_type=peer_type,
        peer_id=peer_id,
        model_version="v1_ai",
        rows=[
            {
                "message_id": message_id,
                "text_hash": "hash_msg_555",
                "predictions": [
                    {
                        "label_id": 80101,
                        "label_name": "نامربوط اولیه",
                        "score": 0.65,
                        "evidence": ["پیشنهاد خودکار"],
                    }
                ],
            }
        ],
    )

    # Account 2 queries results for this channel
    res_acc2 = temp_store.list_results(site_key="account_phone_2", peer_type=peer_type, peer_id=peer_id)
    assert len(res_acc2) == 1
    assert res_acc2[0]["message_id"] == message_id
    assert res_acc2[0]["predictions"][0]["label_id"] == 80101

    # Staff member "Saeed" using Account 2 modifies the index
    temp_store.add_feedback(
        site_key="account_phone_2",
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="accept",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="usr_saeed",
        operator_name="سعید کارمند",
        operator_role="user",
    )

    # Now Account 1 and Account 3 query list_results: both MUST see Saeed's updated index!
    for test_site in ["account_phone_1", "account_phone_3", "local"]:
        res = temp_store.list_results(site_key=test_site, peer_type=peer_type, peer_id=peer_id)
        assert len(res) == 1
        msg = res[0]
        assert msg["operator_name"] == "سعید کارمند"
        assert msg["operator_role"] == "user"
        assert msg["review_status"] == "pending"
        labels = [p["label_id"] for p in msg["predictions"]]
        assert label_id in labels

    # Manager on Account 3 overrides and approves a specific final label
    temp_store.add_feedback(
        site_key="account_phone_3",
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="reject",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="adm_reza",
        operator_name="رضا مدیر",
        operator_role="admin",
    )

    # All accounts must now see the label removed and review_status approved
    for test_site in ["account_phone_1", "account_phone_2", "account_phone_3"]:
        res = temp_store.list_results(site_key=test_site, peer_type=peer_type, peer_id=peer_id)
        assert len(res) == 1
        msg = res[0]
        assert msg["operator_name"] == "رضا مدیر"
        assert msg["operator_role"] == "admin"
        assert msg["review_status"] == "approved"
        labels = [p["label_id"] for p in msg["predictions"]]
        assert label_id not in labels


def test_peer_to_peer_edits_not_penalized_as_manager_override(temp_store: SQLiteContentIndexStore):
    """Verify that a peer staff member editing another staff member's index is NOT treated as
    a manager override, but a manager edit IS treated as an override."""
    peer_type = "channel"
    peer_id = 998877
    message_id = 601
    label_id = 80501
    label_name = "ترویج نماز"

    # Staff 1 (Ali) accepts
    temp_store.add_feedback(
        site_key="site1",
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="accept",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="usr_ali",
        operator_name="علی محمدی",
        operator_role="user",
    )

    # Staff 2 (Hassan) rejects the same label
    temp_store.add_feedback(
        site_key="site1",
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="reject",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="usr_hassan",
        operator_name="حسن صادقی",
        operator_role="user",
    )

    # Check actions: Hassan's edit must NOT be a manager override
    actions = temp_store.list_actions(limit=10)
    assert len(actions) == 2
    hassan_action = actions[0]
    assert hassan_action["operator_id"] == "usr_hassan"
    assert hassan_action["is_manager_override"] is False

    # Check staff scorecards: Ali has NOT suffered a manager override, Hassan has 0 overrides
    perf = temp_store.get_staff_performance()
    ali_perf = next(p for p in perf if p["operator_id"] == "usr_ali")
    hassan_perf = next(p for p in perf if p["operator_id"] == "usr_hassan")
    assert ali_perf["override_count"] == 0
    assert ali_perf["accuracy_rate"] == 100.0
    assert hassan_perf["override_count"] == 0
    assert hassan_perf["accuracy_rate"] == 100.0

    # Now Manager overrules Hassan by accepting the label back
    temp_store.add_feedback(
        site_key="site1",
        source_key=f"{peer_type}:{peer_id}:{message_id}",
        label_id=label_id,
        label_name=label_name,
        decision="accept",
        peer_type=peer_type,
        peer_id=peer_id,
        message_id=message_id,
        operator_id="adm_reza",
        operator_name="رضا مدیر",
        operator_role="admin",
    )

    # Re-check scorecards: Hassan's decision was overridden by manager, so Hassan's accuracy drops
    perf2 = temp_store.get_staff_performance()
    hassan_perf2 = next(p for p in perf2 if p["operator_id"] == "usr_hassan")
    ali_perf2 = next(p for p in perf2 if p["operator_id"] == "usr_ali")
    assert hassan_perf2["override_count"] == 1
    assert hassan_perf2["accuracy_rate"] == 0.0
    # Ali still has 100% accuracy because Ali's accept decision was confirmed by the manager!
    assert ali_perf2["override_count"] == 0
    assert ali_perf2["accuracy_rate"] == 100.0


def test_isolated_time_window_kpis(temp_store: SQLiteContentIndexStore):
    """Verify that from_date and to_date filters completely isolate actions, overrides,
    and tasks to the requested time window."""
    # Seed past action in August 2026
    august_date = "2026-08-15T10:00:00Z"
    september_date = "2026-09-15T10:00:00Z"
    october_date = "2026-10-10T10:00:00Z"

    with temp_store._connect() as conn:
        # August: Ali does 1 action, overridden by manager in August
        conn.execute(
            """
            INSERT INTO index_actions (
                site_key, peer_type, peer_id, message_id, label_id, label_name,
                previous_decision, new_decision, operator_id, operator_name,
                operator_role, is_manager_override, overridden_operator_id, created_at
            ) VALUES ('local', 'channel', 100, 1, 801, 'موضوع الف', '', 'accept', 'usr_ali', 'علی', 'user', 0, '', ?)
            """,
            (august_date,),
        )
        conn.execute(
            """
            INSERT INTO index_actions (
                site_key, peer_type, peer_id, message_id, label_id, label_name,
                previous_decision, new_decision, operator_id, operator_name,
                operator_role, is_manager_override, overridden_operator_id, created_at
            ) VALUES ('local', 'channel', 100, 1, 801, 'موضوع الف', 'accept', 'reject', 'adm_reza', 'رضا', 'admin', 1, 'usr_ali', ?)
            """,
            (august_date,),
        )

        # October: Ali does 4 correct actions, 0 overrides
        for i in range(2, 6):
            conn.execute(
                """
                INSERT INTO index_actions (
                    site_key, peer_type, peer_id, message_id, label_id, label_name,
                    previous_decision, new_decision, operator_id, operator_name,
                    operator_role, is_manager_override, overridden_operator_id, created_at
                ) VALUES ('local', 'channel', 100, ?, 802, 'موضوع ب', '', 'accept', 'usr_ali', 'علی', 'user', 0, '', ?)
                """,
                (i, october_date),
            )

        # August task for Ali (resolved in August)
        conn.execute(
            """
            INSERT INTO staff_tasks (
                task_id, peer_type, peer_id, message_id, title, defect_type,
                status, assigned_to_user_id, assigned_to_name, created_at, updated_at
            ) VALUES ('task_aug_1', 'channel', 100, 1, 'نقص مرداد', 'missing_info', 'closed', 'usr_ali', 'علی', ?, ?)
            """,
            (august_date, august_date),
        )

        # October task for Ali (open)
        conn.execute(
            """
            INSERT INTO staff_tasks (
                task_id, peer_type, peer_id, message_id, title, defect_type,
                status, assigned_to_user_id, assigned_to_name, created_at, updated_at
            ) VALUES ('task_oct_1', 'channel', 100, 2, 'نقص مهر', 'missing_info', 'open', 'usr_ali', 'علی', ?, ?)
            """,
            (october_date, october_date),
        )

    # 1. Query October window only
    oct_perf = temp_store.get_staff_performance(
        from_date="2026-10-01T00:00:00Z",
        to_date="2026-10-31T23:59:59Z",
    )
    ali_oct = next(p for p in oct_perf if p["operator_id"] == "usr_ali")
    assert ali_oct["total_actions"] == 4
    assert ali_oct["override_count"] == 0
    assert ali_oct["accuracy_rate"] == 100.0
    assert ali_oct["assigned_tasks"] == 1
    assert ali_oct["resolved_tasks"] == 0
    assert ali_oct["task_resolution_rate"] == 0.0

    # 2. Query August window only
    aug_perf = temp_store.get_staff_performance(
        from_date="2026-08-01T00:00:00Z",
        to_date="2026-08-31T23:59:59Z",
    )
    ali_aug = next(p for p in aug_perf if p["operator_id"] == "usr_ali")
    assert ali_aug["total_actions"] == 1
    assert ali_aug["override_count"] == 1
    assert ali_aug["accuracy_rate"] == 0.0
    assert ali_aug["assigned_tasks"] == 1
    assert ali_aug["resolved_tasks"] == 1
    assert ali_aug["task_resolution_rate"] == 100.0


def test_defect_task_reopening_lifecycle(temp_store: SQLiteContentIndexStore):
    """Test defect task lifecycle including manager reopening and re-resolution."""
    task = temp_store.create_task(
        title="نقص در اسامی مدعوین شورای حل اختلاف",
        description="نام سخنران اصلی ذکر نشده است.",
        defect_type="missing_attendees",
        priority="urgent",
        peer_type="channel",
        peer_id=7788,
        message_id=990,
        assigned_to_user_id="usr_zahra",
        assigned_to_name="زهرا حسینی",
        created_by_user_id="adm_reza",
        created_by_name="رضا مدیر",
    )
    task_id = task["task_id"]

    # Staff resolves with notes
    res = temp_store.resolve_task(
        task_id=task_id,
        resolution_notes="سخنران جلسه آقای محمدی اعلام شد.",
        user_id="usr_zahra",
        user_name="زهرا حسینی",
    )
    assert res["status"] == "resolved"

    # Manager rejects resolution and reopens
    reopen_res = temp_store.close_task(
        task_id=task_id,
        manager_id="adm_reza",
        manager_name="رضا مدیر",
        reopen=True,
    )
    assert reopen_res["status"] == "in_progress"

    # Staff re-resolves with complete info
    res2 = temp_store.resolve_task(
        task_id=task_id,
        resolution_notes="آقای دکتر محمدی معاون قضایی رئیس کل دادگستری استان ثبت شد.",
        user_id="usr_zahra",
        user_name="زهرا حسینی",
    )
    assert res2["status"] == "resolved"

    # Manager approves and closes
    final_res = temp_store.close_task(
        task_id=task_id,
        manager_id="adm_reza",
        manager_name="رضا مدیر",
        reopen=False,
    )
    assert final_res["status"] == "closed"
    assert final_res["closed_at"] is not None


def test_persian_unicode_and_safety_resilience(temp_store: SQLiteContentIndexStore):
    """Test unicode resilience with non-ASCII Persian characters, zero-width non-joiners,
    quotes and symbols in operator names, labels and task notes."""
    complex_name = "سیّدمحمّدعلی‌رضا طباطبایی‌فر (کارشناس ارشد) ' \" ` <script>"
    complex_title = "بررسی نواقص گزارش شمارهٔ ۱۴۰۴/۷۸۶؛ «جلسهٔ ارتقای سلامت نظام اداری»"
    complex_notes = "پیگیری شد: تعداد ۴۵ نفر با احتساب اعضای افتخاری ✔ — بدون نقص."

    task = temp_store.create_task(
        title=complex_title,
        description=complex_notes,
        defect_type="general",
        priority="high",
        peer_type="channel",
        peer_id=123,
        message_id=456,
        assigned_to_user_id="usr_complex",
        assigned_to_name=complex_name,
        created_by_user_id="adm_complex",
        created_by_name="مدیر کل دادگستری",
    )
    assert task["assigned_to_name"] == complex_name
    assert task["title"] == complex_title

    # Test indexing feedback with complex Persian text
    fb_id = temp_store.add_feedback(
        site_key="local",
        source_key="channel:123:456",
        label_id=9999,
        label_name="کارگاه‌های آموزشی و سبک زندگی ایرانی–اسلامی",
        decision="accept",
        peer_type="channel",
        peer_id=123,
        message_id=456,
        operator_id="usr_complex",
        operator_name=complex_name,
        operator_role="user",
    )
    assert fb_id > 0

    results = temp_store.list_results(site_key="local", peer_type="channel", peer_id=123)
    assert len(results) == 1
    assert results[0]["operator_name"] == complex_name
    assert results[0]["predictions"][0]["label_name"] == "کارگاه‌های آموزشی و سبک زندگی ایرانی–اسلامی"


def test_rulebook_edge_cases_classification():
    """Verify sections 21-28 of UNIFIED_CULTURAL_INDEXING_RULEBOOK in EitaaIntentIndexer."""
    indexer = EitaaIntentIndexer()

    # 1. Chatter / courtesy filtering
    chatter_text = "سلام و عرض ادب و احترام خدمت همکاران گرامی. خسته نباشید همگی."
    chatter_res = indexer.classify(chatter_text, message_ref="msg1", dialog_label="گروه فرهنگی")
    assert chatter_res.intent == MessageIntent.CHATTER_COURTESY
    assert chatter_res.is_event_report is False

    # 2. HR evaluation notice
    hr_text = "امور اداری و ارزشیابی کارکنان: کلیه همکاران محترم موظف به رعایت نظم حضور و غیاب هستند."
    hr_res = indexer.classify(hr_text, message_ref="msg2", dialog_label="گروه اداری")
    assert hr_res.intent == MessageIntent.HR_EVALUATION
    assert hr_res.is_event_report is False

    # 3. Veterans affairs classification
    veterans_text = "دیدار با جانباز سرافراز دفاع مقدس با حضور دادگستری برگزار شد و تجلیل انجام شد."
    vet_res = indexer.classify(veterans_text, message_ref="msg3", dialog_label="امور ایثارگران")
    assert vet_res.intent == MessageIntent.VETERANS_AFFAIRS

    # 4. External congratulations distinction
    congrat_text = "تبریک به فرزند همکار گرامی به مناسبت کسب رتبه در مسابقات آموزش و پرورش"
    cong_res = indexer.classify(congrat_text, message_ref="msg4", dialog_label="گروه همکاران")
    assert cong_res.intent == MessageIntent.EXTERNAL_CONGRATULATION
    assert cong_res.is_event_report is False

    # 5. Judiciary involvement verification on general municipal stations
    station_text = "موکب و ایستگاه صلواتی به مناسبت میلاد برگزار شد و ۵۰ نفر حضور داشتند."
    st_res = indexer.classify(station_text, message_ref="msg5", dialog_label="گروه شهری")
    assert st_res.needs_judiciary_verification is True


def test_concurrent_feedback_and_query_stress(temp_store: SQLiteContentIndexStore):
    """Stress test: 12 concurrent threads reading and writing feedback and tasks simultaneously
    to ensure zero SQLite locking errors or transaction deadlocks."""
    import concurrent.futures

    def worker(worker_id: int):
        for i in range(10):
            msg_id = 1000 + worker_id * 20 + i
            temp_store.add_feedback(
                site_key=f"site_{worker_id % 3}",
                source_key=f"channel:5000:{msg_id}",
                label_id=80400 + (i % 5),
                label_name=f"موضوع آزمون {i}",
                decision="accept" if i % 2 == 0 else "reject",
                peer_type="channel",
                peer_id=5000,
                message_id=msg_id,
                operator_id=f"usr_worker_{worker_id}",
                operator_name=f"کارمند شماره {worker_id}",
                operator_role="user",
            )
            # Create a task
            temp_store.create_task(
                title=f"نقص پیام {msg_id}",
                peer_type="channel",
                peer_id=5000,
                message_id=msg_id,
                assigned_to_user_id=f"usr_worker_{worker_id}",
                assigned_to_name=f"کارمند {worker_id}",
            )
            # Query results simultaneously
            res = temp_store.list_results(site_key="local", peer_type="channel", peer_id=5000, limit=50)
            assert len(res) > 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, w_id) for w_id in range(8)]
        for f in concurrent.futures.as_completed(futures):
            f.result()  # Will raise if any thread failed

    # Verify all 80 actions and 80 tasks exist
    perf = temp_store.get_staff_performance()
    assert len(perf) == 8
    for staff in perf:
        assert staff["total_actions"] == 10
        assert staff["assigned_tasks"] == 10
        assert staff["accuracy_rate"] == 100.0


def test_setting_persistence_across_reboots(temp_store: SQLiteContentIndexStore):
    """Verify that settings such as auto_index_on_load persist across separate store instances."""
    temp_store.set_setting("auto_index_on_load", "true")
    db_file = temp_store.path

    # Instantiate a brand new store pointing to the same sqlite file
    rebooted_store = SQLiteContentIndexStore(db_file)
    rebooted_store.initialize()
    assert rebooted_store.get_setting("auto_index_on_load") == "true"
    assert rebooted_store.get_setting("non_existent_key", "default_val") == "default_val"

