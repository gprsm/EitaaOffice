"""Authentication results must remain valid across the Child IPC boundary."""

from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

import pytest
from eitaa_core.domain.auth import LoginStepResult

from eitaa_bridge.application.eitaa_auth_child_operations import EitaaAuthChildOperations
from eitaa_bridge.infrastructure.worker_ipc.protocol import _validate_payload


@pytest.mark.parametrize("step", ["code_complete", "code_password", "password_complete"])
def test_auth_child_result_can_cross_ipc_and_preserves_session_snapshot(
    monkeypatch, tmp_path, step: str
) -> None:
    session_summary = {"present": True}
    session = SimpleNamespace(safe_summary=lambda: session_summary)
    password_challenge = SimpleNamespace(safe_summary=lambda: {"required": True})
    result = (
        LoginStepResult(password_challenge=password_challenge)
        if step == "code_password"
        else LoginStepResult(session=session)
    )
    auth = SimpleNamespace(
        submit_code=lambda *_args: result,
        submit_password=lambda *_args: result,
    )
    auth_runtime = SimpleNamespace(auth=auth, close=lambda: None)
    record = SimpleNamespace(
        messenger_account_id="account-test",
        provider="eitaa",
        auth_state="challenge_pending",
        session_generation=1,
    )
    challenge = SimpleNamespace(
        provider_challenge=object(),
        for_password=lambda: challenge,
        safe_summary=lambda: {"stage": "password"},
    )
    runtime = SimpleNamespace(
        eitaa_lock=RLock(),
        auth_lock=RLock(),
        auth_runtime=auth_runtime,
        auth_challenge=challenge,
        audit_auth_event=lambda **_kwargs: None,
        transition_auth=lambda **_kwargs: record,
        close_shared_core=lambda: None,
        logger=SimpleNamespace(emit=lambda *_args, **_kwargs: None),
    )
    operation = EitaaAuthChildOperations.__new__(EitaaAuthChildOperations)
    operation.runtime = runtime
    operation._logger = runtime.logger
    monkeypatch.setattr(operation, "_require_challenge", lambda **_kwargs: (challenge, record))
    session_file = tmp_path / "session.json"
    session_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        operation,
        "_core_config",
        lambda: SimpleNamespace(session_file=session_file),
    )

    payload = (
        operation.submit_password(challenge_id="test", credential="test-credential")
        if step == "password_complete"
        else operation.submit_code(challenge_id="test", code="12345")
    )

    _validate_payload(payload)
    assert "session" not in payload
    assert payload["session_snapshot"] == (
        None if step == "code_password" else session_summary
    )
    assert payload["step"] == (
        "password" if step == "code_password" else "completed"
    )
