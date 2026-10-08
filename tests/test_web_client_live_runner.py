"""Tests for Web Client Live Warm Acceptance Runner (Phase 8).

Validates:
- Default-off safe execution (dry-plan exits 0 without network activity).
- Strict loopback origin validation (SSRF/remote endpoints blocked).
- Confirmation gating (aborts safely when rejected or unconfirmed in non-interactive environment).
- Live execution without explicit credentials fails closed (missing_token).
- No token, phone, or private message text is accepted from argv (P8 rules).
- Dispatch is impossible without an explicit target and a same-operation confirmation.
- ``warm_verified`` only with a session witness and a real connect count.
- ai-probe requires a real admin app session (cookie + CSRF); an M2M Bearer is never admin.
- Raw AI responses and sensitive exception text never reach the runner output.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import web_client_live_runner
from tests.test_web_client_e2e import loopback_env

ADMIN_USERNAME = "admin_loopback"
ADMIN_PASSWORD = "ValidPassword123!"


@pytest.fixture(autouse=True)
def _clean_runner_env(monkeypatch):
    for name in (
        web_client_live_runner.M2M_TOKEN_ENV,
        web_client_live_runner.ADMIN_SESSION_TOKEN_ENV,
        web_client_live_runner.ADMIN_CSRF_TOKEN_ENV,
        web_client_live_runner.TARGET_PHONE_ENV,
        web_client_live_runner.CONTACT_NAME_ENV,
        web_client_live_runner.OTP_MESSAGE_ENV,
        web_client_live_runner.AI_MESSAGE_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def test_runner_default_dry_plan(capsys):
    exit_code = web_client_live_runner.main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    plan = json.loads(captured.out)
    assert plan["runner"] == "web_client_live_runner"
    assert plan["mode"] == "OFFLINE_PLAN"
    assert len(plan["supported_actions"]) >= 5


def test_runner_explicit_dry_plan_flag(capsys):
    exit_code = web_client_live_runner.main(["--dry-plan"])
    assert exit_code == 0
    captured = capsys.readouterr()
    plan = json.loads(captured.out)
    assert plan["mode"] == "OFFLINE_PLAN"


def test_runner_dry_plan_declares_secure_input_policy(capsys):
    web_client_live_runner.main(["--dry-plan"])
    captured = capsys.readouterr()
    plan = json.loads(captured.out)
    policy = json.dumps(plan["input_policy"])
    assert "never argv" in policy
    guarantees = json.dumps(plan["guarantees"])
    assert "warm_verified" in guarantees


def test_runner_origin_validation():
    # Valid loopback
    assert web_client_live_runner.validate_origin("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert web_client_live_runner.validate_origin("http://127.0.0.1:9090/") == "http://127.0.0.1:9090"

    # Invalid origins (remote host, HTTPS without cert, missing port, credentials in URL)
    with pytest.raises(ValueError):
        web_client_live_runner.validate_origin("http://example.com:8000")

    with pytest.raises(ValueError):
        web_client_live_runner.validate_origin("http://127.0.0.1")  # missing port

    with pytest.raises(ValueError):
        web_client_live_runner.validate_origin("http://user:pass@127.0.0.1:8000")  # credentials in URL

    with pytest.raises(ValueError):
        web_client_live_runner.validate_origin("https://127.0.0.1:8000")  # not HTTP loopback


def test_runner_rejects_sensitive_argv_options():
    # P8: tokens, phone numbers, and private texts must never arrive via argv.
    for sensitive in (
        ["--token", "secret-token"],
        ["--admin-token", "secret-admin-token"],
        ["--phone", "+989120000001"],
        ["--message", "private message"],
        ["--contact-name", "Private User"],
    ):
        with pytest.raises(SystemExit):
            web_client_live_runner.main(sensitive)


def test_runner_live_with_invalid_origin_returns_error(capsys):
    exit_code = web_client_live_runner.main([
        "--allow-live",
        "--origin", "http://remote-server.com:8080",
        "--action", "preflight",
    ])
    assert exit_code == 2
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["error"] == "invalid_origin"


def test_runner_live_aborted_when_confirmation_missing_in_non_interactive(capsys):
    with patch_isatty(False):
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--origin", "http://127.0.0.1:8080",
            "--action", "preflight",
        ])
    assert exit_code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["status"] == "aborted"
    assert res["reason"] == "operator_confirmation_required"


def test_runner_live_aborted_when_operator_rejects(capsys):
    with patch_isatty(True), pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", lambda _prompt: "no")
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--origin", "http://127.0.0.1:8080",
            "--action", "preflight",
        ])
    assert exit_code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["status"] == "aborted"
    assert res["reason"] == "operator_confirmation_rejected"


def test_runner_live_fails_closed_when_token_missing(capsys):
    with patch_isatty(False):
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", "http://127.0.0.1:8080",
            "--action", "preflight",
        ])
    assert exit_code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["error"] == "missing_token"


def test_runner_dispatch_requires_explicit_target(capsys):
    # Non-interactive, no BRIDGE_OTP_TARGET_PHONE: dispatch must be impossible
    # even with a same-operation confirmation.
    with patch_isatty(False):
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm", "otp-dispatch",
            "--origin", "http://127.0.0.1:8080",
            "--action", "otp-dispatch",
        ])
    assert exit_code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["error"] == "dispatch_target_required"


def test_runner_dispatch_requires_message_text(capsys):
    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.TARGET_PHONE_ENV, "+989129998877")
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm", "otp-dispatch",
            "--origin", "http://127.0.0.1:8080",
            "--action", "otp-dispatch",
        ])
    assert exit_code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["error"] == "dispatch_message_required"


def test_runner_impactful_action_requires_same_operation_confirmation(capsys):
    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.TARGET_PHONE_ENV, "+989129998877")
        mp.setenv(web_client_live_runner.OTP_MESSAGE_ENV, "Code 246810")
        # 1. Bare --confirm is not enough for an impactful action.
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", "http://127.0.0.1:8080",
            "--action", "otp-dispatch",
        ])
        assert exit_code == 1
        res = json.loads(capsys.readouterr().out)
        assert res["reason"] == "same_operation_confirmation_required"

        # 2. Confirming a DIFFERENT action is not enough either.
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm", "preflight",
            "--origin", "http://127.0.0.1:8080",
            "--action", "otp-dispatch",
        ])
        assert exit_code == 1
        res = json.loads(capsys.readouterr().out)
        assert res["reason"] == "same_operation_confirmation_required"


def test_runner_impactful_bare_confirm_still_prompts_interactively(capsys):
    # A bare --confirm in interactive mode must NOT silently authorize an
    # impactful action: the operator must still be asked with a prompt that
    # names the exact action.
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return "no"

    with patch_isatty(True), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.TARGET_PHONE_ENV, "+989129998877")
        mp.setenv(web_client_live_runner.OTP_MESSAGE_ENV, "Code 246810")
        mp.setenv(web_client_live_runner.CONTACT_NAME_ENV, "Live Runner User")
        mp.setattr("builtins.input", fake_input)
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", "http://127.0.0.1:8080",
            "--action", "otp-dispatch",
        ])
    assert exit_code == 1
    res = json.loads(capsys.readouterr().out)
    assert res["status"] == "aborted"
    assert res["reason"] == "operator_confirmation_rejected"
    assert len(prompts) == 1 and "'otp-dispatch'" in prompts[0]


class _Isatty:
    """Context manager patching sys.stdin.isatty for both checks."""

    def __init__(self, value: bool) -> None:
        self._value = value

    def __enter__(self):
        import sys

        self._original = sys.stdin.isatty
        sys.stdin.isatty = lambda: self._value
        return self

    def __exit__(self, *exc):
        import sys

        sys.stdin.isatty = self._original
        return False


def patch_isatty(value: bool) -> _Isatty:
    return _Isatty(value)


def test_runner_live_preflight_real_execution(loopback_env, capsys):
    base_url = loopback_env["base_url"]
    service_token = loopback_env["service_token"]
    sender_profile_id = loopback_env["sender_profile_id"]

    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.M2M_TOKEN_ENV, service_token)
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", base_url,
            "--action", "preflight",
            "--sender-profile-id", sender_profile_id,
            "--recipient-kind", "new",
        ])
    assert exit_code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["action"] == "preflight"
    assert res["status"] == "ready"
    # Warmth is proven by the session witness + real connect count, never by
    # the preflight response itself.
    assert res["warm_verified"] is True
    witness = res["warm_witness"]
    assert witness["session_ok"] is True
    assert witness["session_kind"] == "m2m_credential"
    assert witness["connects_observed"] is True
    assert witness["connects"] >= 1
    assert witness["round_trips"] >= 1


def test_runner_live_reserve_and_dispatch_real_execution(loopback_env, capsys):
    base_url = loopback_env["base_url"]
    service_token = loopback_env["service_token"]
    sender_profile_id = loopback_env["sender_profile_id"]
    target_phone = "+989129998877"
    target_message = "Code 987654"

    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.M2M_TOKEN_ENV, service_token)
        mp.setenv(web_client_live_runner.TARGET_PHONE_ENV, target_phone)
        mp.setenv(web_client_live_runner.OTP_MESSAGE_ENV, target_message)
        mp.setenv(web_client_live_runner.CONTACT_NAME_ENV, "Live Runner User")

        # 1. Real reserve action (impactful: same-operation confirmation).
        res_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm", "reserve",
            "--origin", base_url,
            "--action", "reserve",
            "--sender-profile-id", sender_profile_id,
            "--ttl-seconds", "300",
        ])
        assert res_code == 0
        res_data = json.loads(capsys.readouterr().out)
        assert res_data["ok"] is True
        assert res_data["warm_verified"] is True
        res_id = res_data["reservation_id"]
        assert res_id is not None

        # 2. Real OTP dispatch action using that reservation.
        disp_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm", "otp-dispatch",
            "--origin", base_url,
            "--action", "otp-dispatch",
            "--sender-profile-id", sender_profile_id,
            "--reservation-id", res_id,
        ])
        assert disp_code == 0
        disp_data = json.loads(capsys.readouterr().out)
        assert disp_data["ok"] is True
        assert disp_data["warm_verified"] is True
        assert disp_data["delivery_id"] is not None

    # Privacy: neither the target phone nor the private message may appear in
    # any runner output.
    full_output = res_data | disp_data
    assert target_phone not in json.dumps(full_output)
    assert target_message not in json.dumps(full_output)


def test_runner_live_ai_chat_real_execution(loopback_env, capsys):
    base_url = loopback_env["base_url"]
    service_token = loopback_env["service_token"]
    private_message = "پیام زنده برای آزمون"

    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.M2M_TOKEN_ENV, service_token)
        mp.setenv(web_client_live_runner.AI_MESSAGE_ENV, private_message)
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm", "ai-chat",
            "--origin", base_url,
            "--action", "ai-chat",
        ])
    assert exit_code == 0
    captured = capsys.readouterr()
    chat_data = json.loads(captured.out)
    assert chat_data["ok"] is True
    assert chat_data["warm_verified"] is True
    # The raw AI response must never be printed; only its size/metadata.
    assert "response" not in chat_data
    assert chat_data["response_length"] > 0
    assert private_message not in captured.out


def _login_admin_over_http(base_url: str) -> tuple[str, str]:
    """Real HTTP login against the loopback server; returns (session_token, csrf)."""
    response = httpx.post(
        f"{base_url}/api/v2/app-auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        headers={"X-Request-Id": "runner-test-login"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True and payload["authenticated"] is True
    csrf = payload.get("csrf_token")
    assert csrf
    cookie = response.cookies.get("eitaa_bridge_app_session")
    assert cookie
    return cookie, csrf


def test_runner_live_ai_probe_requires_real_admin_session(loopback_env, capsys):
    base_url = loopback_env["base_url"]
    service_token = loopback_env["service_token"]

    # Presenting the M2M service token as the admin session must fail closed:
    # an M2M Bearer is never admin authorization. (A dummy CSRF value lets the
    # flow reach the session witness; the fake session itself must be rejected.)
    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.ADMIN_SESSION_TOKEN_ENV, service_token)
        mp.setenv(web_client_live_runner.ADMIN_CSRF_TOKEN_ENV, "dummy-csrf-for-negative-test")
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", base_url,
            "--action", "ai-probe",
        ])
    assert exit_code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["warm_verified"] is False
    assert res["error"] in {"session_rejected", "session_unexpected_response", "admin_role_required"}


def test_runner_live_ai_probe_fails_closed_without_csrf_token(loopback_env, capsys):
    base_url = loopback_env["base_url"]
    session_token, _csrf = _login_admin_over_http(base_url)

    # A valid admin session without a CSRF token must not reach the probe: the
    # runner fails closed instead of sending a doomed POST.
    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.ADMIN_SESSION_TOKEN_ENV, session_token)
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", base_url,
            "--action", "ai-probe",
        ])
    assert exit_code == 1
    res = json.loads(capsys.readouterr().out)
    assert res["ok"] is False
    assert res["error"] == "missing_csrf_token"


def test_runner_live_m2m_witness_rejects_invalid_token(loopback_env, capsys):
    base_url = loopback_env["base_url"]

    # A garbage credential must fail the session witness BEFORE any action:
    # warm can never be reported for a dead session.
    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.M2M_TOKEN_ENV, "eb_svc_invalid_token_0000000000")
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", base_url,
            "--action", "preflight",
        ])
    assert exit_code == 1
    res = json.loads(capsys.readouterr().out)
    assert res["ok"] is False
    assert res["warm_verified"] is False
    assert res["warm_witness"]["session_ok"] is False
    assert res["error"] in {"session_rejected", "session_unexpected_response"}


def test_runner_live_ai_probe_with_admin_session_and_csrf(loopback_env, capsys):
    base_url = loopback_env["base_url"]
    session_token, csrf = _login_admin_over_http(base_url)

    with patch_isatty(False), pytest.MonkeyPatch.context() as mp:
        mp.setenv(web_client_live_runner.ADMIN_SESSION_TOKEN_ENV, session_token)
        mp.setenv(web_client_live_runner.ADMIN_CSRF_TOKEN_ENV, csrf)
        exit_code = web_client_live_runner.main([
            "--allow-live",
            "--confirm",
            "--origin", base_url,
            "--action", "ai-probe",
        ])
    assert exit_code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["status_code"] == 200
    assert res["warm_verified"] is True
    witness = res["warm_witness"]
    assert witness["session_kind"] == "admin_session"
    assert witness["session_ok"] is True
    assert witness["connects"] >= 1
    # Only bounded, safe probe fields leave the runner.
    assert set(res["probe_result"].keys()) <= {"ok", "reachable", "status_code", "error", "latency_ms"}
