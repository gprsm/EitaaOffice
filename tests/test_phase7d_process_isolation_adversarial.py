from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from uuid import uuid4

import pytest

from eitaa_bridge.application.process_runtime import (
    EitaaProcessRuntime,
    EitaaProcessWorkerClient,
)
from eitaa_bridge.errors import EitaaRuntimeError
from eitaa_bridge.infrastructure.coordinator import CoordinatorDatabase
from eitaa_bridge.infrastructure.worker_ipc import (
    WorkerIpcCodec,
    WorkerIpcSecret,
    WorkerIpcSecretFile,
    ipc_error_category,
)
from tests.test_phase7c_process_supervisor import (
    _bootstrap_account,
    _make_runnable,
    _registry,
    _write_config,
)


def _fake_process(
    root: Path,
    temporary_root: Path,
) -> tuple[subprocess.Popen[str], WorkerIpcCodec, WorkerIpcSecret, Path]:
    account_id = str(uuid4())
    material, secret_path = WorkerIpcSecretFile.create(
        temporary_root / "ipc",
        messenger_account_id=account_id,
        provider="fake",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(root / "src"), environment.get("PYTHONPATH", ""))
        if part
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "eitaa_bridge.interfaces.provider_worker",
            "--provider",
            "fake",
            "--messenger-account-id",
            account_id,
            "--secret-file",
            str(secret_path),
        ],
        cwd=root,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        bufsize=1,
    )
    return process, WorkerIpcCodec(material), material, secret_path


def _exchange(
    process: subprocess.Popen[str],
    codec: WorkerIpcCodec,
    raw: str,
):
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(raw + "\n")
    process.stdin.flush()
    response = process.stdout.readline()
    assert response
    return codec.decode(response.rstrip("\r\n"), expected_kind="response")


def test_real_fake_worker_can_be_killed_without_secret_or_orphaned_bootstrap(tmp_path):
    root = Path(__file__).resolve().parents[1]
    process, codec, material, secret_path = _fake_process(root, tmp_path)
    try:
        hello = _exchange(process, codec, codec.request("worker.hello"))
        worker_pid = int(hello.payload["worker_pid"])
        assert worker_pid != os.getpid()
        os.kill(worker_pid, signal.SIGTERM)
        process.wait(timeout=10)
        stdout_tail = process.stdout.read() if process.stdout is not None else ""
        stderr = process.stderr.read() if process.stderr is not None else ""
        encoded_secret = base64.urlsafe_b64encode(material.secret).decode("ascii")
        assert process.returncode != 0
        assert not secret_path.exists()
        assert encoded_secret not in stdout_tail
        assert encoded_secret not in stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_actual_fake_worker_rejects_signature_scope_and_replay_tampering(tmp_path):
    root = Path(__file__).resolve().parents[1]
    process, codec, material, secret_path = _fake_process(root, tmp_path)
    valid = codec.request("worker.health", nonce=uuid4().hex)
    tampered_payload = json.loads(valid)
    tampered_payload["payload"] = {"changed": True}
    tampered = json.dumps(tampered_payload, ensure_ascii=True, sort_keys=True)

    wrong_scope_material = WorkerIpcSecret(
        key_id=material.key_id,
        secret=material.secret,
        messenger_account_id=str(uuid4()),
        provider="fake",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    wrong_scope = WorkerIpcCodec(wrong_scope_material).request("worker.health")
    replay = codec.request("worker.health", nonce=uuid4().hex)
    stop = codec.request("worker.stop")
    assert process.stdin is not None
    stdout, stderr = process.communicate(
        "\n".join([tampered, wrong_scope, replay, replay, stop]) + "\n",
        timeout=15,
    )
    responses = [
        codec.decode(line, expected_kind="response")
        for line in stdout.splitlines()
        if line
    ]
    assert process.returncode == 0
    assert stderr == ""
    assert [response.payload for response in responses] == [
        {"error": {"code": "ipc_authentication_failed"}},
        {"error": {"code": "ipc_envelope_invalid"}},
        {
            "status": "ready",
            "request_count": 1,
            "uptime_ms": responses[2].payload["uptime_ms"],
        },
        {"error": {"code": "ipc_replay_detected"}},
        {"status": "stopped"},
    ]
    assert isinstance(responses[2].payload["uptime_ms"], int)
    assert ipc_error_category("ipc_authentication_failed") == "authentication"
    assert ipc_error_category("eitaa_process_fence_mismatch") == "worker"
    encoded_secret = base64.urlsafe_b64encode(material.secret).decode("ascii")
    assert encoded_secret not in stdout
    assert encoded_secret not in stderr
    assert not secret_path.exists()


def test_parent_terminates_child_on_signed_unsolicited_response(tmp_path):
    root = Path(__file__).resolve().parents[1]
    process, codec, _, secret_path = _fake_process(root, tmp_path)
    client = EitaaProcessWorkerClient(
        process,
        codec,
        messenger_account_id=codec.secret.messenger_account_id,
        request_timeout_seconds=5,
    )
    try:
        hello = client.request("worker.hello")
        client._worker_pid = int(hello["worker_pid"])
        client._responses.put(
            codec.error_response(code="ipc_request_failed"),
            timeout=1,
        )
        with pytest.raises(EitaaRuntimeError) as tampered:
            client.request("worker.health")
        assert tampered.value.code == "eitaa_process_response_correlation_invalid"
        assert process.poll() is not None
        assert not secret_path.exists()
    finally:
        client.terminate()


def test_repeated_authentication_tampering_forces_fake_worker_exit(tmp_path):
    root = Path(__file__).resolve().parents[1]
    process, codec, material, secret_path = _fake_process(root, tmp_path)
    tampered_requests: list[str] = []
    for _ in range(8):
        payload = json.loads(codec.request("worker.health"))
        payload["auth"]["signature"] = "0" * 64
        tampered_requests.append(
            json.dumps(payload, ensure_ascii=True, sort_keys=True)
        )
    assert process.stdin is not None
    stdout, stderr = process.communicate(
        "\n".join(tampered_requests) + "\n",
        timeout=15,
    )
    responses = [
        codec.decode(line, expected_kind="response")
        for line in stdout.splitlines()
        if line
    ]
    assert process.returncode == 3
    assert len(responses) == 8
    assert all(
        response.payload == {"error": {"code": "ipc_authentication_failed"}}
        for response in responses
    )
    assert json.loads(stderr) == {
        "error_code": "ipc_authentication_failure_limit",
        "ok": False,
    }
    encoded_secret = base64.urlsafe_b64encode(material.secret).decode("ascii")
    assert encoded_secret not in stdout
    assert encoded_secret not in stderr
    assert not secret_path.exists()


def test_eitaa_child_rejects_stale_fence_and_real_lock_contention(tmp_path):
    root = tmp_path / "fence-lock"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "d1")
    _make_runnable(database, account.messenger_account_id)
    config_path = _write_config(root, default_account_id=account.messenger_account_id)
    registry, logger = _registry(config_path)
    contender = None
    try:
        runtime = registry.resolve_v1()
        assert isinstance(runtime, EitaaProcessRuntime)
        runtime.stop_supervisor()
        raw = runtime.client.codec.request(
            "worker.heartbeat",
            {
                "worker_instance_id": runtime.worker.worker_instance_id,
                "worker_generation": runtime.worker.generation + 1,
            },
        )
        expected = runtime.client.codec.decode(raw, expected_kind="request")
        assert runtime.client.process.stdin is not None
        with runtime.client._request_lock:
            runtime.client.process.stdin.write(raw + "\n")
            runtime.client.process.stdin.flush()
            response_raw = runtime.client._responses.get(timeout=5)
        assert isinstance(response_raw, str)
        response = runtime.client.codec.decode(response_raw, expected_kind="response")
        assert response.correlation_id == expected.correlation_id
        assert response.payload == {
            "error": {"code": "eitaa_process_fence_mismatch"}
        }
        assert runtime.health()["status"] == "ready"

        contender = EitaaProcessWorkerClient.spawn(registry.config, runtime.ownership)
        with pytest.raises(EitaaRuntimeError) as contention:
            contender.request(
                "eitaa.runtime.start",
                {
                    "runtime_record": database.messenger_account_runtime(
                        account.messenger_account_id
                    ).safe_summary(),
                    "worker_instance_id": str(uuid4()),
                    "worker_generation": runtime.worker.generation + 100,
                },
            )
        assert contention.value.code == "eitaa_worker_lease_held"
        assert runtime.health()["status"] == "ready"
    finally:
        if contender is not None:
            contender.terminate()
        registry.close()
        logger.close()


def test_duplicate_spawn_race_creates_exactly_one_worker_generation(tmp_path):
    root = tmp_path / "spawn-race"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "d2")
    _make_runnable(database, account.messenger_account_id)
    config = _write_config(root, default_account_id=account.messenger_account_id)
    first_registry, first_logger = _registry(config)
    second_registry, second_logger = _registry(config)
    barrier = threading.Barrier(2)

    def start(registry):
        barrier.wait(timeout=5)
        try:
            return "ready", registry.resolve_v1()
        except Exception as exc:
            return "error", exc

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(start, (first_registry, second_registry))
            )
        ready = [value for status, value in results if status == "ready"]
        errors = [value for status, value in results if status == "error"]
        assert len(ready) == 1
        assert len(errors) == 1
        assert isinstance(ready[0], EitaaProcessRuntime)
        assert getattr(errors[0], "code", None) in {
            "eitaa_worker_process_alive",
            "worker_instance_already_active",
        }, getattr(errors[0], "safe_context", {})
        history = database.worker_instances(account.messenger_account_id)
        assert len(history) == 1
        assert history[0].runtime_state == "ready"
        ipc_files = list((root / "runtime" / "accounts").rglob("worker-ipc-*.json"))
        assert ipc_files == []
    finally:
        first_registry.close()
        second_registry.close()
        first_logger.close()
        second_logger.close()
    assert database.active_worker_instance(account.messenger_account_id) is None


def test_two_children_share_no_runtime_paths_and_generated_secrets_never_leak(tmp_path):
    root = tmp_path / "path-secret-isolation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    first = _bootstrap_account(database, "d3")
    second = _bootstrap_account(database, "d4")
    _make_runnable(database, first.messenger_account_id, second.messenger_account_id)
    config = _write_config(root, default_account_id=first.messenger_account_id)
    registry, logger = _registry(config)
    encoded_secrets: list[bytes] = []
    try:
        first_runtime = registry.resolve_v1()
        second_runtime = registry.runtime_for_account(second.messenger_account_id)
        assert isinstance(first_runtime, EitaaProcessRuntime)
        assert isinstance(second_runtime, EitaaProcessRuntime)
        assert first_runtime.process_id != second_runtime.process_id
        encoded_secrets = [
            base64.urlsafe_b64encode(runtime.client.codec.secret.secret)
            for runtime in (first_runtime, second_runtime)
        ]

        first_ownership = first_runtime.ownership
        second_ownership = second_runtime.ownership
        isolated_fields = (
            "account_data_directory",
            "account_runtime_directory",
            "provider_session_directory",
            "provider_state_directory",
            "content_index_file",
            "sender_directory_file",
            "dialog_catalog_file",
            "contact_peers_directory",
            "worker_diagnostics_root",
            "worker_log_file",
            "worker_lock_file",
            "worker_cache_directory",
        )
        for field in isolated_fields:
            assert getattr(first_ownership, field) != getattr(second_ownership, field)
        assert first_ownership.core != second_ownership.core
        assert not first_ownership.content_index_file.exists()
        assert not second_ownership.content_index_file.exists()
        assert first_ownership.sender_directory_file.is_file()
        assert second_ownership.sender_directory_file.is_file()
        assert not first_ownership.core.session_file.exists()
        assert not second_ownership.core.session_file.exists()
        assert not first_ownership.core.database_file.exists()
        assert not second_ownership.core.database_file.exists()
        first_scheduler = first_runtime.scheduler.snapshot()["worker_name"]
        second_scheduler = second_runtime.scheduler.snapshot()["worker_name"]
        assert first_scheduler != second_scheduler

        first_log = first_ownership.worker_log_file.read_text(encoding="utf-8")
        second_log = second_ownership.worker_log_file.read_text(encoding="utf-8")
        assert first.messenger_account_id in first_log
        assert second.messenger_account_id not in first_log
        assert second.messenger_account_id in second_log
        assert first.messenger_account_id not in second_log
        assert second.messenger_account_id not in json.dumps(
            first_runtime.safe_summary(), ensure_ascii=True
        )
        assert first.messenger_account_id not in json.dumps(
            second_runtime.safe_summary(), ensure_ascii=True
        )
    finally:
        registry.close()
        logger.close()

    assert list(root.rglob("worker-ipc-*.json")) == []
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            continue
        content = path.read_bytes()
        for encoded_secret in encoded_secrets:
            assert encoded_secret not in content, path
