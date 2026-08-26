from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from eitaa_bridge.errors import WorkerIpcError
from eitaa_bridge.infrastructure.worker_ipc import (
    IPC_PROTOCOL_NAME,
    IPC_PROTOCOL_VERSION,
    WorkerIpcCodec,
    WorkerIpcSecretFile,
    ipc_error_category,
)


def _secret(tmp_path: Path, *, account_id: str | None = None):
    selected_id = account_id or str(uuid4())
    material, path = WorkerIpcSecretFile.create(
        tmp_path / "worker-auth",
        messenger_account_id=selected_id,
        provider="fake",
    )
    return selected_id, material, path


def test_secret_file_is_short_lived_current_user_only_and_consumed_once(tmp_path):
    account_id, parent_material, path = _secret(tmp_path)
    assert path.is_file()
    assert parent_material.safe_summary() == {
        "key_id": parent_material.key_id,
        "messenger_account_id": account_id,
        "provider": "fake",
        "expires_at": parent_material.expires_at.isoformat(timespec="seconds"),
    }
    assert "secret" not in parent_material.safe_summary()
    assert "secret=" not in repr(parent_material)
    assert base64.urlsafe_b64encode(parent_material.secret).decode("ascii") not in repr(
        parent_material
    )

    worker_material = WorkerIpcSecretFile.consume(
        path,
        expected_messenger_account_id=account_id,
        expected_provider="fake",
    )

    assert worker_material == parent_material
    assert not path.exists()
    with pytest.raises(WorkerIpcError) as reused:
        WorkerIpcSecretFile.consume(
            path,
            expected_messenger_account_id=account_id,
            expected_provider="fake",
        )
    assert reused.value.code == "ipc_secret_unavailable"


def test_secret_file_fails_closed_on_scope_mismatch_or_expiry(tmp_path):
    account_id, _, path = _secret(tmp_path / "scope")
    with pytest.raises(WorkerIpcError) as mismatch:
        WorkerIpcSecretFile.consume(
            path,
            expected_messenger_account_id=str(uuid4()),
            expected_provider="fake",
        )
    assert mismatch.value.code == "ipc_secret_invalid"
    assert not path.exists()

    now = datetime.now(timezone.utc)
    _, expired_path = WorkerIpcSecretFile.create(
        tmp_path / "expired",
        messenger_account_id=account_id,
        provider="fake",
        ttl_seconds=5,
        now=now,
    )
    with pytest.raises(WorkerIpcError) as expired:
        WorkerIpcSecretFile.consume(
            expired_path,
            expected_messenger_account_id=account_id,
            expected_provider="fake",
            now=now + timedelta(seconds=6),
        )
    assert expired.value.code == "ipc_secret_invalid"
    assert not expired_path.exists()


def test_versioned_envelope_authenticates_scope_correlation_and_deadline(tmp_path):
    account_id, material, _ = _secret(tmp_path)
    codec = WorkerIpcCodec(material)
    correlation_id = str(uuid4())
    now_ms = int(time.time() * 1000)
    raw = codec.request(
        "fake.echo_opaque",
        {"opaque_reference": "conversation:opaque-17"},
        correlation_id=correlation_id,
        deadline_unix_ms=now_ms + 10_000,
    )

    decoded = codec.decode(raw, expected_kind="request", now_unix_ms=now_ms)

    assert decoded.correlation_id == correlation_id
    assert decoded.messenger_account_id == account_id
    assert decoded.provider == "fake"
    assert decoded.method == "fake.echo_opaque"
    serialized = json.loads(raw)
    assert serialized["protocol"] == IPC_PROTOCOL_NAME
    assert serialized["version"] == IPC_PROTOCOL_VERSION
    assert serialized["auth"]["algorithm"] == "hmac-sha256"
    assert material.secret not in raw.encode("utf-8")

    serialized["payload"]["opaque_reference"] = "tampered"
    with pytest.raises(WorkerIpcError) as tampered:
        codec.decode(json.dumps(serialized), expected_kind="request", now_unix_ms=now_ms)
    assert tampered.value.code == "ipc_authentication_failed"

    expired = codec.request(
        "worker.health",
        deadline_unix_ms=now_ms - 1,
    )
    with pytest.raises(WorkerIpcError) as deadline:
        codec.decode(expired, expected_kind="request", now_unix_ms=now_ms)
    assert deadline.value.code == "ipc_deadline_expired"
    assert ipc_error_category(deadline.value.code) == "contract"
    assert ipc_error_category("ipc_authentication_failed") == "authentication"
    assert ipc_error_category("not_an_ipc_error") is None


@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"session": {}},
        {"nested": {"access_hash": "123"}},
        {"items": [{"raw_peer": {"id": 9}}]},
        {"provider_state": {"cookie": "private"}},
    ],
)
def test_ipc_contract_rejects_sensitive_provider_state_recursively(
    tmp_path,
    forbidden_payload,
):
    _, material, _ = _secret(tmp_path)
    codec = WorkerIpcCodec(material)
    with pytest.raises(WorkerIpcError) as raised:
        codec.request("fake.echo_opaque", forbidden_payload)
    assert raised.value.code == "ipc_payload_forbidden"
    assert "private" not in str(raised.value.safe_context)


def test_fake_worker_runs_in_an_independent_process_and_preserves_correlation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    account_id, material, secret_path = _secret(tmp_path)
    codec = WorkerIpcCodec(material)
    requests = [
        codec.request("worker.hello"),
        codec.request(
            "fake.echo_opaque",
            {"opaque_reference": "message:opaque-42"},
        ),
        codec.request("worker.health"),
        codec.request("worker.stop"),
    ]
    source_path = str(root / "src")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (source_path, environment.get("PYTHONPATH", ""))
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
    )
    stdout, stderr = process.communicate("\n".join(requests) + "\n", timeout=10)

    assert process.returncode == 0
    assert stderr == ""
    assert not secret_path.exists()
    responses = [
        codec.decode(line, expected_kind="response")
        for line in stdout.splitlines()
        if line
    ]
    assert len(responses) == len(requests)
    decoded_requests = [
        codec.decode(line, expected_kind="request") for line in requests
    ]
    assert [item.correlation_id for item in responses] == [
        item.correlation_id for item in decoded_requests
    ]
    assert responses[0].payload["status"] == "ready"
    assert responses[0].payload["worker_pid"] != os.getpid()
    assert responses[1].payload == {"opaque_reference": "message:opaque-42"}
    assert responses[2].payload["status"] == "ready"
    assert responses[3].payload == {"status": "stopped"}
    encoded_secret = base64.urlsafe_b64encode(material.secret).decode("ascii")
    assert encoded_secret not in stdout
    assert encoded_secret not in stderr


def test_fake_worker_rejects_replay_and_eitaa_requires_process_config(tmp_path):
    root = Path(__file__).resolve().parents[1]
    account_id, material, secret_path = _secret(tmp_path / "replay")
    codec = WorkerIpcCodec(material)
    repeated = codec.request("worker.health", nonce=uuid4().hex)
    stop = codec.request("worker.stop")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root / "src"), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    completed = subprocess.run(
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
        input="\n".join([repeated, repeated, stop]) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0
    responses = [
        codec.decode(line, expected_kind="response")
        for line in completed.stdout.splitlines()
        if line
    ]
    assert responses[0].payload["status"] == "ready"
    assert responses[1].payload == {"error": {"code": "ipc_replay_detected"}}
    assert responses[2].payload == {"status": "stopped"}

    _, _, unused_secret = _secret(tmp_path / "unsupported")
    refused = subprocess.run(
        [
            sys.executable,
            "-m",
            "eitaa_bridge.interfaces.provider_worker",
            "--provider",
            "eitaa",
            "--messenger-account-id",
            str(uuid4()),
            "--secret-file",
            str(unused_secret),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    try:
        assert refused.returncode == 2
        assert json.loads(refused.stderr)["error_code"] == "eitaa_worker_config_required"
        assert refused.stdout == ""
        assert unused_secret.exists()
    finally:
        unused_secret.unlink(missing_ok=True)

    entrypoint = (
        root / "src" / "eitaa_bridge" / "interfaces" / "provider_worker.py"
    ).read_text(encoding="utf-8")
    assert "eitaa_core" not in entrypoint
    assert "EitaaAuth" not in entrypoint
    assert "account_runtime" not in entrypoint
