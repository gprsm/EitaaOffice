from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ui" / "src" / "App.tsx"
API = ROOT / "src" / "eitaa_bridge" / "application" / "api.py"


def test_third_pane_dialog_operations_are_connected():
    app = APP.read_text(encoding="utf-8")
    assert "props.openBulk(props.dialog && props.dialog.display_kind !== 'personal' ? 'members' : 'numbers')" in app
    assert "دعوت شماره‌ها" in app
    assert "شماره‌های جدید" in app
    assert "onClick={props.openMembers}" in app
    assert '<button className="btn btn-neutral btn-sm" disabled>ارسال به اعضا</button>' not in app


def test_members_modal_supports_sync_selection_and_targeted_send():
    app = APP.read_text(encoding="utf-8")
    assert "function CommunityMembersModal" in app
    assert "/api/v1/community/members/sync/start" in app
    assert "/api/v1/community/members/list" in app
    assert "ارسال به {selected.length.toLocaleString('fa-IR')} عضو انتخاب‌شده" in app
    assert "member_ids: memberIds.length ? memberIds : undefined" in app


def test_bulk_file_path_has_preflight_progress_and_failure_details():
    app = APP.read_text(encoding="utf-8")
    assert "/api/v1/community/bulk/validate" in app
    assert "/api/v1/community/bulk/recipients" in app
    assert "file-preflight" in app
    assert "operation-progress-counts" in app
    assert "recipient-failures" in app
    assert "response.task.error?.message" in app


def test_background_errors_keep_safe_core_details():
    api = API.read_text(encoding="utf-8")
    assert 'state["error"] = error' in api
    assert 'elif isinstance(exc, EitaaCoreError):' in api
    assert '"background_task_failed"' in api


def test_bulk_jobs_can_be_paused_resumed_and_cancelled_from_ui():
    app = APP.read_text(encoding="utf-8")
    assert "controlJob = async (action: 'pause' | 'resume' | 'cancel')" in app
    assert "ادامه گیرندگان باقی‌مانده" in app
    assert "توقف موقت" in app
    assert "لغو وظیفه" in app


def test_local_operation_reports_do_not_wait_for_remote_scheduler_lock():
    api = API.read_text(encoding="utf-8")
    jobs_start = api.index("def _community_bulk_jobs")
    recipients_start = api.index("def _community_bulk_recipients")
    action_start = api.index("def _community_bulk_action")
    assert "with self._eitaa_lock" not in api[jobs_start:recipients_start]
    assert "with self._eitaa_lock" not in api[recipients_start:action_start]
