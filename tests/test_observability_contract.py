from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.diagnostics import (
    EVENT_CATALOG,
    EVENT_SCHEMA_VERSION,
    RuntimeLogger,
    catalog_payload,
)


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_event_catalog_is_versioned_and_contains_material_boundaries():
    payload = catalog_payload()
    assert payload["schema_version"] == EVENT_SCHEMA_VERSION == 1
    for event in (
        "application_started",
        "api_request",
        "renderer_error_reported",
        "desktop_api_request_failed",
        "operation_uncertain",
    ):
        assert event in EVENT_CATALOG
        assert event in payload["events"]
    assert payload["events"]["operation_uncertain"]["audit_required"] is True


def test_runtime_logger_emits_versioned_correlated_redacted_envelope(tmp_path):
    path = tmp_path / "application.jsonl"
    logger = RuntimeLogger(path, source="test")
    try:
        logger.emit(
            "renderer_error_reported",
            level="error",
            result="failed",
            reason_code="renderer_unhandled_error",
            correlation_id="a" * 32,
            fields={
                "error_type": "TypeError",
                "password": "never-store-this",
                "message": "private message text",
                "phone": "+989000000000",
            },
        )
    finally:
        logger.close()
    [record] = _records(path)
    assert record["schema_version"] == 1
    assert record["source"] == "test"
    assert record["cataloged"] is True
    assert record["result"] == "failed"
    assert record["reason_code"] == "renderer_unhandled_error"
    assert record["correlation_id"] == "a" * 32
    encoded = json.dumps(record, ensure_ascii=False)
    assert "never-store-this" not in encoded
    assert "private message text" not in encoded
    assert "+989000000000" not in encoded


def test_observed_operation_balances_success_and_failure(tmp_path):
    path = tmp_path / "worker.jsonl"
    logger = RuntimeLogger(path, source="provider_worker")
    try:
        with logger.observed_operation("safe.success") as correlation_id:
            assert len(correlation_id) >= 12
        with pytest.raises(RuntimeError):
            with logger.observed_operation("safe.failure", correlation_id="b" * 32):
                raise RuntimeError("private exception message")
    finally:
        logger.close()
    records = _records(path)
    assert [item["event"] for item in records] == [
        "operation_started",
        "operation_succeeded",
        "operation_started",
        "operation_failed",
    ]
    encoded = json.dumps(records, ensure_ascii=False)
    assert "private exception message" not in encoded
    assert records[-1]["fields"]["error_type"] == "RuntimeError"


def test_client_diagnostic_endpoint_accepts_only_safe_allowlisted_shape(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    try:
        accepted = api.dispatch(
            "POST",
            "/api/v2/client-diagnostics",
            client_kind="test",
            correlation_id="c" * 32,
            body={
                "event": "renderer_unhandled_rejection",
                "level": "error",
                "error_type": "TypeError",
                "safe_context": {
                    "component_stack_present": False,
                    "document_visible": True,
                    "online": True,
                    "surface": "browser",
                },
            },
        )
        assert accepted.status == 202
        catalog = api.dispatch("GET", "/api/v2/observability/events")
        assert catalog.status == 200
        assert catalog.payload["catalog"]["schema_version"] == 1

        rejected = api.dispatch(
            "POST",
            "/api/v2/client-diagnostics",
            client_kind="test",
            body={
                "event": "renderer_unhandled_error",
                "level": "error",
                "error_type": "TypeError",
                "message": "do-not-record-this-private-value",
                "safe_context": {},
            },
        )
        assert rejected.status == 400
        assert rejected.payload["error"]["error_code"] == "client_diagnostic_fields_rejected"
    finally:
        api.close()

    records = _records(config_file.parent / "runtime" / "logs" / "application.jsonl")
    renderer = next(item for item in records if item["event"] == "renderer_error_reported")
    assert renderer["correlation_id"] == "c" * 32
    assert renderer["fields"]["error_type"] == "TypeError"
    encoded = json.dumps(records, ensure_ascii=False)
    assert "do-not-record-this-private-value" not in encoded


def test_client_diagnostic_endpoint_is_rate_limited(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    payload = {
        "event": "renderer_unhandled_error",
        "level": "warning",
        "error_type": "Error",
        "safe_context": {"surface": "renderer"},
    }
    try:
        statuses = [
            api.dispatch("POST", "/api/v2/client-diagnostics", body=payload).status
            for _ in range(21)
        ]
    finally:
        api.close()
    assert statuses[:20] == [202] * 20
    assert statuses[-1] == 429


def test_literal_runtime_events_are_registered_in_catalog():
    source_root = Path(__file__).resolve().parents[1] / "src" / "eitaa_bridge"
    literal_events: set[str] = set()
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "emit" or len(node.args) != 1:
                continue
            event_node = node.args[0]
            if isinstance(event_node, ast.Constant) and isinstance(event_node.value, str):
                literal_events.add(event_node.value)
    assert literal_events
    missing = sorted(literal_events - set(EVENT_CATALOG))
    assert not missing, f"uncataloged runtime events: {', '.join(missing)}"
