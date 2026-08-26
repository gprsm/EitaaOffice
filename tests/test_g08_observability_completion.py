from __future__ import annotations

import json
import inspect
import importlib.util
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.diagnostics import EVENT_CATALOG, RuntimeLogger


def _write_jsonl(path, *records: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_scanner_enumerates_every_account_log_without_disclosing_account_ids(tmp_path):
    from scripts.phase10_log_redaction_verify import scan_runtime_logs

    first_id = "account-private-alpha"
    second_id = "account-private-beta"
    application = tmp_path / "runtime" / "logs" / "application.jsonl"
    first = tmp_path / "runtime" / "accounts" / first_id / "logs" / "worker.jsonl"
    first_rotated = first.with_name("worker.jsonl.1")
    second = tmp_path / "runtime" / "accounts" / second_id / "logs" / "worker.jsonl"
    for path in (application, first, first_rotated, second):
        _write_jsonl(path, {"event": "safe", "fields": {"count": 1}})

    result = scan_runtime_logs(tmp_path)

    assert result["format"] == "eitaa-bridge-log-redaction-verification-v2"
    assert result["verified"] is True
    assert result["account_scope_count"] == 2
    assert len(result["files"]) == 4
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert first_id not in encoded
    assert second_id not in encoded
    assert str(tmp_path) not in encoded
    assert {item["scope"] for item in result["files"]} == {
        "application",
        "account-0001",
        "account-0002",
    }


def test_scanner_fails_closed_on_malformed_or_unsafe_records_in_any_account(tmp_path):
    from scripts.phase10_log_redaction_verify import scan_runtime_logs

    first_id = "account-private-alpha"
    second_id = "account-private-beta"
    application = tmp_path / "runtime" / "logs" / "application.jsonl"
    first = tmp_path / "runtime" / "accounts" / first_id / "logs" / "worker.jsonl"
    second = tmp_path / "runtime" / "accounts" / second_id / "logs" / "worker.jsonl"
    _write_jsonl(application, {"event": "safe", "fields": {"count": 1}})
    _write_jsonl(first, {"event": "safe", "fields": {"count": 1}})
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_text(
        '{"event":"unsafe","token":"synthetic-provider-token-value"}\n{broken\n',
        encoding="utf-8",
    )

    result = scan_runtime_logs(tmp_path)

    assert result["verified"] is False
    assert result["finding_count"] == 2
    assert sum(item["invalid_json"] for item in result["files"]) == 1
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert first_id not in encoded
    assert second_id not in encoded
    assert "synthetic-provider-token-value" not in encoded


def test_runtime_logger_contains_write_failure_and_exposes_safe_health(tmp_path, monkeypatch):
    logger = RuntimeLogger(tmp_path / "application.jsonl", source="test")
    handler = logger._logger.handlers[0]

    def fail_write(_record):
        raise OSError("private path and payload must not escape")

    monkeypatch.setattr(handler, "emit", fail_write)
    logger.emit("application_started", result="succeeded")
    summary = logger.health_summary()
    logger.close()

    assert summary == {
        "status": "degraded",
        "write_failures": 1,
        "last_failure_type": "OSError",
    }
    encoded = json.dumps(summary, ensure_ascii=False)
    assert "private path" not in encoded
    assert str(tmp_path) not in encoded


def test_runtime_logger_counts_stream_failure_swallowed_by_logging_handler(tmp_path):
    logger = RuntimeLogger(tmp_path / "application.jsonl", source="test")
    handler = logger._logger.handlers[0]
    original_stream = handler.stream

    class BrokenStream:
        def write(self, _value):
            raise OSError("private stream failure")

        def flush(self):
            return None

        def seek(self, _offset, _whence=0):
            return 0

        def tell(self):
            return 0

    handler.stream = BrokenStream()
    try:
        logger.emit("application_started", result="succeeded")
        summary = logger.health_summary()
    finally:
        handler.stream = original_stream
        logger.close()

    assert summary["status"] == "degraded"
    assert summary["write_failures"] == 1
    assert summary["last_failure_type"] == "OSError"


def test_runtime_retention_and_disk_health_are_bounded_and_path_free(tmp_path, monkeypatch):
    from eitaa_bridge.infrastructure.diagnostics import (
        enforce_runtime_log_retention,
        observability_disk_health,
    )

    current = tmp_path / "runtime" / "logs" / "application.jsonl"
    current_worker = (
        tmp_path / "runtime" / "accounts" / "private-account" / "logs" / "worker.jsonl"
    )
    old_application = current.with_name("application.jsonl.2")
    newest_application = current.with_name("application.jsonl.1")
    old_worker = current_worker.with_name("worker.jsonl.2")
    for path in (current, current_worker, old_application, newest_application, old_worker):
        _write_jsonl(path, {"event": "safe"})
    stale = time.time() - 60 * 86400
    for path in (old_application, old_worker):
        os.utime(path, (stale, stale))

    retention = enforce_runtime_log_retention(
        tmp_path,
        keep_newest_rotations=1,
        max_age_days=30,
        max_total_bytes=10_000,
    )
    monkeypatch.setattr(
        "shutil.disk_usage",
        lambda _path: SimpleNamespace(total=0, used=0, free=0),
    )
    health = observability_disk_health(tmp_path, minimum_free_bytes=1024)

    assert current.exists() and current_worker.exists() and newest_application.exists()
    assert not old_application.exists() and not old_worker.exists()
    assert retention == {"scanned": 3, "removed": 2, "failed": 0, "remaining_bytes": 57}
    assert health == {
        "status": "degraded",
        "available_free_bytes": 0,
        "minimum_free_bytes": 1024,
    }
    encoded = json.dumps({"retention": retention, "health": health})
    assert "private-account" not in encoded
    assert str(tmp_path) not in encoded


def test_runtime_retention_budget_deletes_oldest_rotation_but_never_current(tmp_path):
    current = tmp_path / "runtime" / "logs" / "application.jsonl"
    newest = current.with_name("application.jsonl.1")
    oldest = current.with_name("application.jsonl.2")
    current.parent.mkdir(parents=True)
    current.write_bytes(b"c" * 20)
    newest.write_bytes(b"n" * 100)
    oldest.write_bytes(b"o" * 100)
    now = time.time()
    os.utime(newest, (now, now))
    os.utime(oldest, (now - 10, now - 10))

    from eitaa_bridge.infrastructure.diagnostics import enforce_runtime_log_retention

    result = enforce_runtime_log_retention(
        tmp_path,
        keep_newest_rotations=5,
        max_age_days=30,
        max_total_bytes=150,
    )

    assert current.exists()
    assert newest.exists()
    assert not oldest.exists()
    assert result == {"scanned": 2, "removed": 1, "failed": 0, "remaining_bytes": 120}


def test_material_bootstrap_lifecycle_security_and_manual_job_events_are_cataloged():
    required = {
        "application_started",
        "application_start_failed",
        "application_stopping",
        "application_stopped",
        "application_stop_failed",
        "auth_challenge_created",
        "auth_challenge_denied",
        "auth_runtime_close_failed",
        "provider_capability_check_rejected",
        "diagnostics_pruned",
        "background_task_failed",
        "content_index_job_started",
        "content_index_job_succeeded",
        "content_index_job_cancelled",
        "content_index_job_failed",
        "content_index_job_cleanup_failed",
        "read_receipt_failed",
    }
    assert required <= set(EVENT_CATALOG)


def test_background_worker_emits_balanced_correlated_operation(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    correlation_id = "d" * 32
    token = RuntimeLogger.bind_correlation_id(correlation_id)
    try:
        started = api._start_background(
            kind="g08.synthetic.success",
            callback=lambda: {"count": 1},
        )
    finally:
        RuntimeLogger.reset_correlation_id(token)
    task_id = str(started["task"]["task_id"])
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = api._background_status({"task_id": task_id})["task"]["status"]
        if state == "completed":
            break
        time.sleep(0.01)
    assert state == "completed"
    api.close()

    records = [
        json.loads(line)
        for line in (config_file.parent / "runtime" / "logs" / "application.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    operation_records = [
        item
        for item in records
        if item.get("operation") == "background.g08.synthetic.success"
    ]
    assert [item["event"] for item in operation_records] == [
        "operation_started",
        "operation_succeeded",
    ]
    assert {item["correlation_id"] for item in operation_records} == {correlation_id}


def test_background_failure_is_correlated_and_does_not_log_exception_message(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    correlation_id = "e" * 32

    def fail():
        raise RuntimeError("private synthetic failure message")

    token = RuntimeLogger.bind_correlation_id(correlation_id)
    try:
        started = api._start_background(kind="g08.synthetic.failure", callback=fail)
    finally:
        RuntimeLogger.reset_correlation_id(token)
    task_id = str(started["task"]["task_id"])
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = api._background_status({"task_id": task_id})["task"]["status"]
        if state == "failed":
            break
        time.sleep(0.01)
    assert state == "failed"
    api.close()

    encoded = (config_file.parent / "runtime" / "logs" / "application.jsonl").read_text(
        encoding="utf-8"
    )
    records = [json.loads(line) for line in encoded.splitlines() if line]
    relevant = [
        item
        for item in records
        if item.get("operation") == "background.g08.synthetic.failure"
        or item.get("event") == "background_task_failed"
    ]
    assert [item["event"] for item in relevant] == [
        "operation_started",
        "operation_failed",
        "background_task_failed",
    ]
    assert {item["correlation_id"] for item in relevant} == {correlation_id}
    assert "private synthetic failure message" not in encoded


def test_best_effort_and_manual_background_failures_have_explicit_events():
    read_worker = inspect.getsource(BridgeApplicationApi._run_read_receipt_worker)
    content_worker = inspect.getsource(BridgeApplicationApi._run_content_index_job)
    assert '"read_receipt_failed"' in read_worker
    for event in (
        "content_index_job_started",
        "content_index_job_succeeded",
        "content_index_job_cancelled",
        "content_index_job_failed",
    ):
        assert f'"{event}"' in content_worker


def test_support_bundle_normalizes_malformed_jsonl_without_retaining_private_values(
    tmp_path,
    monkeypatch,
):
    root = Path(__file__).resolve().parents[1]
    runtime_state = _load_script("g08_runtime_state", root / "scripts" / "runtime_state.py")
    monkeypatch.setitem(sys.modules, "runtime_state", runtime_state)
    creator = _load_script(
        "g08_create_diagnostics_bundle",
        root / "scripts" / "create_diagnostics_bundle.py",
    )
    source = tmp_path / "application.jsonl"
    private_phone = "+999123456789"
    private_token = "Bearer " + "g08" + "x" * 28
    source.write_text(
        json.dumps({"event": "safe", "identity_hint": private_phone})
        + "\n"
        + '{"broken":"'
        + private_token
        + "\n",
        encoding="utf-8",
    )

    normalized = creator.safe_jsonl_tail(source)
    records = [json.loads(line) for line in normalized.splitlines() if line]

    assert len(records) == 2
    assert records[-1]["event"] == "support_bundle_source_record_omitted"
    assert records[-1]["fields"] == {"reason_code": "invalid_jsonl", "omitted_count": 1}
    assert private_phone not in normalized
    assert private_token not in normalized


def test_support_bundle_scanner_report_never_echoes_archive_or_member_names(tmp_path):
    from scripts.scan_diagnostics_bundle import scan_bundle

    private_archive_name = "private-user-account-support.zip"
    private_member_name = "logs/private-account-identity.jsonl"
    archive_path = tmp_path / private_archive_name
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(private_member_name, "{broken\n")

    result = scan_bundle(archive_path)
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert result["verified"] is False
    assert "invalid_jsonl" in {item["kind"] for item in result["findings"]}
    assert private_archive_name not in encoded
    assert private_member_name not in encoded


def test_observability_health_endpoint_is_numeric_and_path_free(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    response = api.dispatch("GET", "/api/v2/observability/health")
    api.close()

    assert response.status == 200
    assert response.payload["ok"] is True
    assert response.payload["runtime_logger"]["status"] == "healthy"
    assert response.payload["runtime_logger"]["write_failures"] == 0
    assert response.payload["disk"]["status"] in {"healthy", "degraded", "unknown"}
    encoded = json.dumps(response.payload, ensure_ascii=False)
    assert str(config_file.parent) not in encoded
