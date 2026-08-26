from __future__ import annotations

import ast
import json
from pathlib import Path
import threading

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.diagnostics import EVENT_CATALOG


def _records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_safe_default_does_not_start_or_orphan_auto_index_thread(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    entered = threading.Event()
    release = threading.Event()

    def controlled_legacy_loop(self) -> None:
        entered.set()
        release.wait(5)

    monkeypatch.setattr(
        BridgeApplicationApi,
        "_run_auto_indexer",
        controlled_legacy_loop,
        raising=False,
    )
    before = {thread.ident for thread in threading.enumerate()}
    api = BridgeApplicationApi(config_file)
    spawned: list[threading.Thread] = []
    try:
        legacy_loop_started = entered.wait(1)
        spawned = [
            thread
            for thread in threading.enumerate()
            if thread.ident not in before and thread.name == "bridge-auto-indexer"
        ]
        api.close()
        alive_after_close = any(thread.is_alive() for thread in spawned)
    finally:
        release.set()
        for thread in spawned:
            thread.join(timeout=1)

    assert legacy_loop_started is False
    assert spawned == []
    assert alive_after_close is False


def test_safe_default_emits_cataloged_correlated_scheduler_skipped_event(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    api.close()

    records = _records(config_file.parent / "runtime" / "logs" / "application.jsonl")
    selected = [
        item
        for item in records
        if item["event"] == "content_auto_index_scheduler_skipped"
    ]
    assert len(selected) == 1
    [record] = selected
    assert record["cataloged"] is True
    assert record["result"] == "rejected"
    assert record["reason_code"] == "content_auto_index_scheduler_disabled_safe_default"
    assert isinstance(record["correlation_id"], str)
    assert len(record["correlation_id"]) >= 12
    assert record["fields"] == {
        "manual_index_available": True,
        "mode": "disabled_safe_default",
        "request_id": record["correlation_id"],
    }
    assert "content_auto_index_scheduler_skipped" in EVENT_CATALOG


def test_broken_unbounded_auto_index_loop_is_removed_from_api_source():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "eitaa_bridge"
        / "application"
        / "api.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    thread_names = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "_run_auto_indexer" not in function_names
    assert "bridge-auto-indexer" not in thread_names


def test_manual_content_index_contract_remains_available():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "eitaa_bridge"
        / "application"
        / "api.py"
    )
    source = source_path.read_text(encoding="utf-8")
    for route in (
        "/api/v1/messages/index/start",
        "/api/v1/messages/index/status",
        "/api/v1/messages/index/cancel",
        "/api/v1/messages/index/results",
        "/api/v1/messages/index/feedback",
    ):
        assert route in source
    for method in (
        "def _content_index_start(",
        "def _content_index_status(",
        "def _content_index_cancel(",
        "def _content_index_results(",
        "def _content_index_feedback(",
    ):
        assert method in source


def test_repeated_start_close_has_no_auto_thread_accumulation_or_scope_leak(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    before = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name == "bridge-auto-indexer"
    }

    for _ in range(3):
        api = BridgeApplicationApi(config_file)
        api.close()

    after = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name == "bridge-auto-indexer"
    }
    records = _records(config_file.parent / "runtime" / "logs" / "application.jsonl")
    skipped = [
        item
        for item in records
        if item["event"] == "content_auto_index_scheduler_skipped"
    ]

    assert after == before
    assert len(skipped) == 3
    correlations = [str(item["correlation_id"]) for item in skipped]
    assert len(set(correlations)) == 3
    assert all(len(item) >= 12 for item in correlations)
    assert all(
        item["fields"]
        == {
            "manual_index_available": True,
            "mode": "disabled_safe_default",
            "request_id": item["correlation_id"],
        }
        for item in skipped
    )
