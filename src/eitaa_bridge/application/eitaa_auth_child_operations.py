"""Eitaa account authentication lifecycle executed inside one Child process.

The whole login challenge state machine (provider auth runtime, AccountAuthChallenge
binding, session-file archival, and account auth-state transitions) lives behind
this DTO-only boundary so the parent process never touches the provider Core or
the protected phone identity. The parent stays responsible for Coordinator
database access already provided through the runtime's coordinator handle.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eitaa_core import EitaaAuth, EitaaCore, EitaaCoreConfig
from eitaa_core.errors import NetworkError, RpcError

from ..errors import (
    AuthenticationRuntimeError,
    BridgeError,
    CompositionValidationError,
)
from ..infrastructure.coordinator import MessengerAccountRuntimeRecord
from .account_auth import AccountAuthChallenge
from .account_runtime import EitaaAccountRuntime
from .api import (
    BridgeApplicationApi,
    _normalize_login_code,
    _provider_login_code_failure,
)

_CODE_FORMAT = re.compile(r"[0-9A-Za-z-]{2,32}")


class EitaaAuthChildOperations:
    """Own the per-account login lifecycle inside exactly one Child."""

    def __init__(
        self,
        runtime: EitaaAccountRuntime,
        config: Any = None,
    ) -> None:
        if not runtime.is_account_scoped:
            raise CompositionValidationError(
                "Child authentication operations require an account scope.",
                code="eitaa_auth_child_account_scope_required",
            )
        self.runtime = runtime
        self._config = config
        self._logger = runtime.logger

    # ------------------------------------------------------------------ helpers

    def _core_config(self) -> EitaaCoreConfig:
        config = self.runtime.ownership.core
        return EitaaCoreConfig(
            session_file=config.session_file,
            database_file=config.database_file,
            media_directory=config.media_directory,
            diagnostics_root=config.diagnostics_root,
            diagnostics_enabled=config.diagnostics_enabled,
            timeout_seconds=config.timeout_seconds,
        )

    def _close_auth_attempt(self) -> None:
        auth_runtime = self.runtime.auth_runtime
        if auth_runtime is not None:
            try:
                auth_runtime.close()
            finally:
                self.runtime.auth_runtime = None
        self.runtime.auth_challenge = None

    @staticmethod
    def _account_auth_fields(record: Any) -> dict[str, object]:
        return {
            "messenger_account_id": record.messenger_account_id,
            "provider": record.provider,
            "auth_state": record.auth_state,
            "session_generation": record.session_generation,
        }

    @staticmethod
    def _login_result_ipc_summary(result: Any) -> dict[str, object]:
        summary = result.safe_summary()
        return {
            "completed": summary["completed"],
            "password_required": summary["password_required"],
            "session_snapshot": summary["session"],
            "password_challenge": summary["password_challenge"],
        }

    def _archive_uncoordinated_session(self) -> str | None:
        session_file = self._core_config().session_file
        if not session_file.is_file():
            return None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        archive = session_file.with_name(
            f"{session_file.name}.uncoordinated.{timestamp}.bak"
        )
        try:
            import os

            os.replace(session_file, archive)
        except OSError as exc:
            self._logger.emit(
                "auth_uncoordinated_session_archive_failed",
                level="error",
                fields={"error_type": type(exc).__name__},
            )
            return None
        self._logger.emit(
            "auth_uncoordinated_session_archived",
            level="warning",
            fields={"archive_name": archive.name},
        )
        return archive.name

    # ------------------------------------------------------------------- status

    def status(self) -> dict[str, object]:
        core_config = self._core_config()
        core = None
        with self.runtime.eitaa_lock, self.runtime.auth_lock:
            record = self.runtime.refresh_auth_record()
            challenge = (
                self.runtime.auth_challenge
                if isinstance(self.runtime.auth_challenge, AccountAuthChallenge)
                else None
            )
            if challenge is not None:
                challenge_valid = (
                    challenge.messenger_account_id == record.messenger_account_id
                    and challenge.session_generation == record.session_generation
                    and record.auth_state == "challenge_pending"
                )
                if not challenge_valid or challenge.is_expired():
                    reason = (
                        "challenge_expired"
                        if challenge.is_expired()
                        else "challenge_context_mismatch"
                    )
                    self._close_auth_attempt()
                    if record.auth_state == "challenge_pending":
                        record = self.runtime.transition_auth(
                            expected_states={record.auth_state},
                            expected_generation=record.session_generation,
                            new_state="expired",
                            increment_generation=False,
                            reason_code=reason,
                            action="eitaa.auth.challenge.expired",
                            safe_metadata={"challenge_stage": challenge.stage},
                        )
                    challenge = None
            elif record.auth_state == "challenge_pending":
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_runtime_missing",
                    action="eitaa.auth.challenge.expired",
                    safe_metadata={"challenge_stage": "unknown"},
                )

            if challenge is not None:
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": core_config.session_file.is_file(),
                    "password_pending": challenge.stage == "password",
                    "fresh_login_available": False,
                    "challenge": challenge.safe_summary(),
                    **self._account_auth_fields(record),
                }

            if not core_config.session_file.is_file():
                if record.auth_state == "authenticated":
                    record = self.runtime.transition_auth(
                        expected_states={record.auth_state},
                        expected_generation=record.session_generation,
                        new_state="invalid",
                        increment_generation=True,
                        reason_code="local_session_missing",
                        action="eitaa.auth.session.invalidated",
                        safe_metadata={"session_file_present": False},
                    )
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": False,
                    "password_pending": False,
                    "fresh_login_available": True,
                    **self._account_auth_fields(record),
                }

            if record.auth_state in {"revoked", "invalid"}:
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": True,
                    "session_error": True,
                    "session_invalid": True,
                    "session_error_code": "auth_metadata_rejects_active_session",
                    "password_pending": False,
                    "fresh_login_available": True,
                    **self._account_auth_fields(record),
                }

            try:
                core = EitaaCore.open(core_config)
            except Exception as exc:
                return {
                    "ok": True,
                    "authenticated": False,
                    "session_present": True,
                    "session_error": True,
                    "session_error_code": "auth_session_open_failed",
                    "session_error_type": type(exc).__name__,
                    "password_pending": False,
                    "fresh_login_available": True,
                    **self._account_auth_fields(record),
                }
            try:
                session_summary = core.session.safe_summary()
                try:
                    core.discovery.list_dialogs(limit=1)
                except Exception as exc:
                    if BridgeApplicationApi._is_invalid_session_error(exc):
                        if record.auth_state != "invalid":
                            record = self.runtime.transition_auth(
                                expected_states={record.auth_state},
                                expected_generation=record.session_generation,
                                new_state="invalid",
                                increment_generation=True,
                                reason_code="remote_session_invalid",
                                action="eitaa.auth.session.invalidated",
                                safe_metadata={
                                    "error_type": type(exc).__name__,
                                    "remote_status": 401,
                                    "session_file_present": True,
                                },
                            )
                        return {
                            "ok": True,
                            "authenticated": False,
                            "session_present": True,
                            "session_snapshot": session_summary,
                            "session_error": True,
                            "session_invalid": True,
                            "session_error_code": "auth_session_invalid",
                            "session_error_type": type(exc).__name__,
                            "password_pending": False,
                            "fresh_login_available": True,
                            "remote_probe": False,
                            "remote_warning": False,
                            "remote_error_code": 401,
                            **self._account_auth_fields(record),
                        }
                    return {
                        "ok": True,
                        "authenticated": record.auth_state == "authenticated",
                        "session_present": True,
                        "session_snapshot": session_summary,
                        "password_pending": False,
                        "fresh_login_available": record.auth_state
                        != "authenticated",
                        "remote_probe": False,
                        "remote_warning": True,
                        "remote_error_type": type(exc).__name__,
                        "remote_error_code": getattr(exc, "code", None),
                        **self._account_auth_fields(record),
                    }
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="authenticated",
                    increment_generation=False,
                    reason_code="remote_session_validated",
                    action="eitaa.auth.session.validated",
                    mark_validated=True,
                    audit_when_unchanged=False,
                    safe_metadata={"session_file_present": True},
                )
                return {
                    "ok": True,
                    "authenticated": True,
                    "session_present": True,
                    "session_snapshot": session_summary,
                    "password_pending": False,
                    "fresh_login_available": False,
                    "remote_probe": True,
                    "remote_warning": False,
                    **self._account_auth_fields(record),
                }
            finally:
                core.close()

    # ------------------------------------------------------------- request-code

    def request_code(
        self,
        *,
        supplied_phone: str | None,
    ) -> dict[str, object]:
        session_file = self._core_config().session_file
        with self.runtime.eitaa_lock, self.runtime.auth_lock:
            record = self.runtime.refresh_auth_record()
            if session_file.is_file():
                self.runtime.audit_auth_event(
                    action="eitaa.auth.request_code.denied",
                    result="denied",
                    reason_code="active_session_reset_required",
                    safe_metadata={"session_file_present": True},
                )
                raise CompositionValidationError(
                    "Archive or log out the active account session before starting a fresh login.",
                    code="api_auth_session_reset_required",
                )
            if record.auth_state == "challenge_pending":
                self._close_auth_attempt()
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_replaced",
                    action="eitaa.auth.challenge.expired",
                    safe_metadata={"challenge_stage": "unknown"},
                )
            else:
                self._close_auth_attempt()
            try:
                phone = self.runtime.resolve_login_phone(supplied_phone)
            except BridgeError as exc:
                self.runtime.audit_auth_event(
                    action="eitaa.auth.request_code.denied",
                    result=(
                        "denied"
                        if exc.code == "eitaa_account_phone_mismatch"
                        else "failed"
                    ),
                    reason_code=(
                        "account_phone_mismatch"
                        if exc.code == "eitaa_account_phone_mismatch"
                        else "account_phone_resolution_failed"
                    ),
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise
            try:
                self.runtime.auth_runtime = EitaaAuth.open(self._core_config())
                provider_challenge = self.runtime.auth_runtime.auth.request_code(
                    phone
                )
                provider_summary = provider_challenge.safe_summary()
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="challenge_pending",
                    increment_generation=True,
                    reason_code="login_challenge_issued",
                    action="eitaa.auth.request_code.succeeded",
                    safe_metadata={
                        "delivery_type": str(
                            provider_summary.get("delivery_type") or "unknown"
                        ),
                        "timeout_seconds": provider_summary.get("timeout_seconds"),
                    },
                )
                self.runtime.auth_challenge = AccountAuthChallenge.for_code(
                    messenger_account_id=record.messenger_account_id,
                    session_generation=record.session_generation,
                    provider_challenge=provider_challenge,
                )
                self._logger.emit(
                    "auth_challenge_created",
                    fields={
                        "session_generation": record.session_generation,
                        "challenge_stage": "code",
                        "expires_at": (
                            self.runtime.auth_challenge.expires_at.isoformat(
                                timespec="milliseconds"
                            )
                        ),
                    },
                )
                return {
                    "ok": True,
                    "step": "code",
                    "challenge": self.runtime.auth_challenge.safe_summary(),
                    **self._account_auth_fields(record),
                }
            except BridgeError:
                self._close_auth_attempt()
                raise
            except NetworkError as exc:
                self._close_auth_attempt()
                self.runtime.audit_auth_event(
                    action="eitaa.auth.request_code.failed",
                    result="failed",
                    reason_code="provider_network_unreachable",
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise AuthenticationRuntimeError(
                    "ارتباط سرویس محلی با سرور ایتا برقرار نشد. اتصال اینترنت یا دسترسی شبکهٔ سرویس را بررسی و دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_provider_network_unreachable",
                ) from exc
            except Exception as exc:
                self._close_auth_attempt()
                self.runtime.audit_auth_event(
                    action="eitaa.auth.request_code.failed",
                    result="failed",
                    reason_code="provider_request_failed",
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise AuthenticationRuntimeError(
                    "راه‌اندازی ورود ایتا ناموفق بود. سرویس محلی را دوباره راه‌اندازی و مجدداً تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_request_code_failed",
                ) from exc

    # ---------------------------------------------------------------- challenge

    def _require_challenge(
        self,
        *,
        challenge_id: str,
        expected_stage: str,
    ) -> tuple[AccountAuthChallenge, MessengerAccountRuntimeRecord]:
        if not challenge_id:
            raise CompositionValidationError(
                "challenge_id is required.",
                code="api_auth_challenge_id_required",
            )
        record = self.runtime.refresh_auth_record()
        challenge = self.runtime.auth_challenge
        if (
            not isinstance(challenge, AccountAuthChallenge)
            or self.runtime.auth_runtime is None
        ):
            missing_stage = (
                challenge.stage
                if isinstance(challenge, AccountAuthChallenge)
                else "unknown"
            )
            self._close_auth_attempt()
            if record.auth_state == "challenge_pending":
                self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_runtime_missing",
                    action="eitaa.auth.challenge.expired",
                    safe_metadata={"challenge_stage": missing_stage},
                )
            raise CompositionValidationError(
                "No account login challenge is pending.",
                code="api_auth_challenge_missing",
            )
        if challenge.is_expired():
            self._close_auth_attempt()
            if (
                record.auth_state == "challenge_pending"
                and record.session_generation == challenge.session_generation
            ):
                self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="expired",
                    increment_generation=False,
                    reason_code="challenge_expired",
                    action="eitaa.auth.challenge.expired",
                    safe_metadata={"challenge_stage": challenge.stage},
                )
            raise CompositionValidationError(
                "The account login challenge expired. Request a new code.",
                code="api_auth_challenge_expired",
            )
        if not challenge.matches(
            challenge_id=challenge_id,
            messenger_account_id=record.messenger_account_id,
            session_generation=record.session_generation,
            stage=expected_stage,
        ) or record.auth_state != "challenge_pending":
            self.runtime.audit_auth_event(
                action="eitaa.auth.challenge.denied",
                result="denied",
                reason_code="challenge_context_mismatch",
                safe_metadata={"challenge_stage": expected_stage},
            )
            raise CompositionValidationError(
                "The account login challenge does not match this session.",
                code="api_auth_challenge_mismatch",
            )
        return challenge, record

    # -------------------------------------------------------------- submit-code

    def submit_code(
        self,
        *,
        challenge_id: str,
        code: str,
    ) -> dict[str, object]:
        code = _normalize_login_code(code)
        with self.runtime.eitaa_lock, self.runtime.auth_lock:
            challenge, record = self._require_challenge(
                challenge_id=challenge_id,
                expected_stage="code",
            )
            if not _CODE_FORMAT.fullmatch(code):
                raise CompositionValidationError(
                    "کد ورود باید فقط شامل رقم یا حروف انگلیسی باشد.",
                    code="auth_code_format_invalid",
                )
            try:
                result = self.runtime.auth_runtime.auth.submit_code(
                    challenge.provider_challenge,
                    code,
                )
            except BridgeError:
                raise
            except RpcError as exc:
                error_kind, reason_code, error_code, message = (
                    _provider_login_code_failure(exc)
                )
                self.runtime.audit_auth_event(
                    action="eitaa.auth.submit_code.failed",
                    result="failed",
                    reason_code=reason_code,
                    safe_metadata={
                        "error_type": type(exc).__name__,
                        "challenge_stage": "code",
                        "provider_error_kind": error_kind,
                    },
                )
                raise AuthenticationRuntimeError(
                    message,
                    safe_context={
                        "error_type": type(exc).__name__,
                        "provider_error_kind": error_kind,
                    },
                    code=error_code,
                ) from exc
            except Exception as exc:
                self.runtime.audit_auth_event(
                    action="eitaa.auth.submit_code.failed",
                    result="failed",
                    reason_code="provider_code_submission_failed",
                    safe_metadata={
                        "error_type": type(exc).__name__,
                        "challenge_stage": "code",
                    },
                )
                raise AuthenticationRuntimeError(
                    "بررسی کد ورود ایتا ناموفق بود. دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_submit_code_failed",
                ) from exc
            if result.completed:
                if not self._core_config().session_file.is_file():
                    self.runtime.audit_auth_event(
                        action="eitaa.auth.login.failed",
                        result="failed",
                        reason_code="provider_session_file_missing",
                        safe_metadata={"session_file_present": False},
                    )
                    self._close_auth_attempt()
                    raise AuthenticationRuntimeError(
                        "ورود ایتا کامل شد اما فایل نشست تأیید نشد.",
                        code="auth_session_file_missing_after_login",
                    )
                try:
                    record = self.runtime.transition_auth(
                        expected_states={record.auth_state},
                        expected_generation=record.session_generation,
                        new_state="authenticated",
                        increment_generation=False,
                        reason_code="native_login_completed",
                        action="eitaa.auth.login.completed",
                        mark_validated=True,
                        safe_metadata={"challenge_stage": "code"},
                    )
                except BridgeError:
                    self._archive_uncoordinated_session()
                    self._close_auth_attempt()
                    raise
                self._close_auth_attempt()
                self.runtime.close_shared_core()
                return {
                    "ok": True,
                    "step": "completed",
                    **self._login_result_ipc_summary(result),
                    **self._account_auth_fields(record),
                }
            if result.password_required:
                self.runtime.auth_challenge = challenge.for_password()
                self.runtime.audit_auth_event(
                    action="eitaa.auth.submit_code.password_required",
                    result="succeeded",
                    reason_code="second_factor_required",
                    safe_metadata={"challenge_stage": "password"},
                )
                self._logger.emit(
                    "auth_challenge_advanced",
                    fields={
                        "session_generation": record.session_generation,
                        "challenge_stage": "password",
                    },
                )
                return {
                    "ok": True,
                    "step": "password",
                    **self._login_result_ipc_summary(result),
                    "challenge": self.runtime.auth_challenge.safe_summary(),
                    **self._account_auth_fields(record),
                }
            self.runtime.audit_auth_event(
                action="eitaa.auth.submit_code.failed",
                result="failed",
                reason_code="provider_result_incomplete",
                safe_metadata={"challenge_stage": "code"},
            )
            raise AuthenticationRuntimeError(
                "پاسخ ورود ایتا وضعیت قابل استفاده‌ای نداشت.",
                code="auth_submit_code_result_invalid",
            )

    # ---------------------------------------------------------- submit-password

    def submit_password(
        self,
        *,
        challenge_id: str,
        credential: str,
    ) -> dict[str, object]:
        if not isinstance(credential, str) or not credential:
            raise CompositionValidationError(
                "password is required.",
                code="api_password_required",
            )
        with self.runtime.eitaa_lock, self.runtime.auth_lock:
            _, record = self._require_challenge(
                challenge_id=challenge_id,
                expected_stage="password",
            )
            try:
                result = self.runtime.auth_runtime.auth.submit_password(
                    credential
                )
            except BridgeError:
                raise
            except Exception as exc:
                self.runtime.audit_auth_event(
                    action="eitaa.auth.submit_password.failed",
                    result="failed",
                    reason_code="provider_password_submission_failed",
                    safe_metadata={
                        "error_type": type(exc).__name__,
                        "challenge_stage": "password",
                    },
                )
                raise AuthenticationRuntimeError(
                    "بررسی رمز دوم ایتا ناموفق بود. دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_submit_password_failed",
                ) from exc
            if (
                not result.completed
                or not self._core_config().session_file.is_file()
            ):
                self.runtime.audit_auth_event(
                    action="eitaa.auth.login.failed",
                    result="failed",
                    reason_code="provider_session_file_missing",
                    safe_metadata={
                        "challenge_stage": "password",
                        "session_file_present": (
                            self._core_config().session_file.is_file()
                        ),
                    },
                )
                self._close_auth_attempt()
                raise AuthenticationRuntimeError(
                    "ورود دومرحله‌ای کامل شد اما فایل نشست تأیید نشد.",
                    code="auth_session_file_missing_after_login",
                )
            try:
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="authenticated",
                    increment_generation=False,
                    reason_code="native_second_factor_completed",
                    action="eitaa.auth.login.completed",
                    mark_validated=True,
                    safe_metadata={"challenge_stage": "password"},
                )
            except BridgeError:
                self._archive_uncoordinated_session()
                self._close_auth_attempt()
                raise
            self._close_auth_attempt()
            self.runtime.close_shared_core()
            return {
                "ok": True,
                "step": "completed",
                **self._login_result_ipc_summary(result),
                **self._account_auth_fields(record),
            }

    # -------------------------------------------------------- reset-local-session

    def reset_local_session(
        self,
        *,
        automatic_recovery: bool,
    ) -> dict[str, object]:
        import os

        session_file = self._core_config().session_file
        self.runtime.close_shared_core()
        with self.runtime.eitaa_lock, self.runtime.auth_lock:
            record = self.runtime.refresh_auth_record()
            if (
                automatic_recovery
                and record.auth_state == "absent"
                and not session_file.exists()
            ):
                return {
                    "ok": True,
                    "session_present": False,
                    "archived": False,
                    "login_ready": True,
                    "recovery_mode": "automatic",
                    **self._account_auth_fields(record),
                }
            if automatic_recovery and record.auth_state != "invalid":
                self.runtime.audit_auth_event(
                    action="eitaa.auth.session.reset.denied",
                    result="denied",
                    reason_code="automatic_recovery_state_mismatch",
                    safe_metadata={"auth_state": record.auth_state},
                )
                raise CompositionValidationError(
                    "Automatic recovery is only available for an invalid provider session.",
                    safe_context={"auth_state": record.auth_state},
                    code="api_session_automatic_recovery_not_allowed",
                )
            had_challenge = self.runtime.auth_challenge is not None
            self._close_auth_attempt()
            reset_reason = (
                "automatic_invalid_session_recovery"
                if automatic_recovery
                else "operator_local_session_reset"
            )
            if not session_file.exists():
                if record.auth_state != "absent" or had_challenge:
                    record = self.runtime.transition_auth(
                        expected_states={record.auth_state},
                        expected_generation=record.session_generation,
                        new_state="absent",
                        increment_generation=True,
                        reason_code=reset_reason,
                        action="eitaa.auth.session.reset",
                        safe_metadata={
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                else:
                    self.runtime.audit_auth_event(
                        action="eitaa.auth.session.reset",
                        result="succeeded",
                        reason_code="local_session_already_absent",
                        safe_metadata={
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                return {
                    "ok": True,
                    "session_present": False,
                    "archived": False,
                    "login_ready": True,
                    "recovery_mode": (
                        "automatic" if automatic_recovery else "confirmed"
                    ),
                    **self._account_auth_fields(record),
                }
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            archive = session_file.with_name(
                f"{session_file.name}.invalid.{timestamp}.bak"
            )
            try:
                os.replace(session_file, archive)
            except OSError as exc:
                self.runtime.audit_auth_event(
                    action="eitaa.auth.session.reset.failed",
                    result="failed",
                    reason_code="local_session_archive_failed",
                    safe_metadata={"error_type": type(exc).__name__},
                )
                raise AuthenticationRuntimeError(
                    "بایگانی نشست محلی ناموفق بود. برنامه را ببندید و دوباره تلاش کنید.",
                    safe_context={"error_type": type(exc).__name__},
                    code="auth_session_archive_failed",
                ) from exc
            if session_file.exists():
                raise AuthenticationRuntimeError(
                    "فایل نشست پس از بایگانی همچنان در مسیر فعال باقی مانده است.",
                    safe_context={"session_file_present": True},
                    code="auth_session_archive_verification_failed",
                )
            record = self.runtime.transition_auth(
                expected_states={record.auth_state},
                expected_generation=record.session_generation,
                new_state="absent",
                increment_generation=True,
                reason_code=reset_reason,
                action="eitaa.auth.session.reset",
                safe_metadata={
                    "archive_created": True,
                    "session_file_present": False,
                },
            )
        return {
            "ok": True,
            "session_present": False,
            "archived": True,
            "login_ready": True,
            "recovery_mode": "automatic" if automatic_recovery else "confirmed",
            **({} if automatic_recovery else {"archive_name": archive.name}),
            **self._account_auth_fields(record),
        }

    # ------------------------------------------------------------------- logout

    def logout(self) -> dict[str, object]:
        """Mirror the parent's account logout inside the Child process."""

        import os

        session_file = self._core_config().session_file
        with self.runtime.eitaa_lock, self.runtime.auth_lock:
            record = self.runtime.refresh_auth_record()
            if not session_file.is_file():
                had_challenge = self.runtime.auth_challenge is not None
                self._close_auth_attempt()
                if record.auth_state not in {"absent", "revoked"} or had_challenge:
                    record = self.runtime.transition_auth(
                        expected_states={record.auth_state},
                        expected_generation=record.session_generation,
                        new_state="revoked",
                        increment_generation=True,
                        reason_code="logout_without_active_session",
                        action="eitaa.auth.logout.completed",
                        safe_metadata={
                            "remote_ok": False,
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                else:
                    self.runtime.audit_auth_event(
                        action="eitaa.auth.logout.completed",
                        result="succeeded",
                        reason_code=(
                            "local_session_already_revoked"
                            if record.auth_state == "revoked"
                            else "local_session_already_absent"
                        ),
                        safe_metadata={
                            "remote_ok": False,
                            "archive_created": False,
                            "session_file_present": False,
                        },
                    )
                return {
                    "ok": True,
                    "logout": {
                        "remote_ok": False,
                        "local_session_archived": False,
                    },
                    "session_present": False,
                    "login_ready": True,
                    **self._account_auth_fields(record),
                }

            if record.auth_state in {"invalid", "revoked"}:
                self.runtime.close_shared_core()
                archive_name = self._archive_account_session_file("invalid")
                self._close_auth_attempt()
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="revoked",
                    increment_generation=True,
                    reason_code="invalid_session_revoked_locally",
                    action="eitaa.auth.logout.completed",
                    safe_metadata={
                        "remote_ok": False,
                        "archive_created": archive_name is not None,
                        "session_file_present": False,
                    },
                )
                return {
                    "ok": True,
                    "logout": {
                        "remote_ok": False,
                        "remote_session_already_invalid": True,
                        "local_session_archived": archive_name is not None,
                        "archive_name": archive_name,
                    },
                    "session_present": False,
                    "login_ready": True,
                    **self._account_auth_fields(record),
                }

            summary: dict[str, Any] = {}
            try:
                from ..facade import EitaaBridge

                with EitaaBridge.open(
                    self._config.source_file,
                    site_key=self._config.default_site_key,
                    open_core=True,
                    diagnostics=self.runtime.diagnostics,
                    reuse_core=self.runtime.scheduler.is_worker_thread(),
                    core_config_override=self.runtime.ownership.core,
                    data_scope=self.runtime.data_scope,
                ) as bridge:
                    result = bridge.core.account.logout(
                        archive_local_session=True
                    )
                    summary = result.safe_summary()
            except Exception as exc:
                if not BridgeApplicationApi._is_invalid_session_error(exc):
                    self.runtime.audit_auth_event(
                        action="eitaa.auth.logout.failed",
                        result="failed",
                        reason_code="provider_logout_failed",
                        safe_metadata={"error_type": type(exc).__name__},
                    )
                    raise
                self.runtime.close_shared_core()
                archive_name = self._archive_account_session_file("invalid")
                self._close_auth_attempt()
                record = self.runtime.transition_auth(
                    expected_states={record.auth_state},
                    expected_generation=record.session_generation,
                    new_state="revoked",
                    increment_generation=True,
                    reason_code="remote_session_already_invalid",
                    action="eitaa.auth.logout.completed",
                    safe_metadata={
                        "remote_ok": False,
                        "archive_created": archive_name is not None,
                        "session_file_present": False,
                    },
                )
                return {
                    "ok": True,
                    "logout": {
                        "remote_ok": False,
                        "remote_session_already_invalid": True,
                        "local_session_archived": archive_name is not None,
                        "archive_name": archive_name,
                    },
                    "session_present": False,
                    "login_ready": True,
                    **self._account_auth_fields(record),
                }

            self.runtime.close_shared_core()
            archive_name = None
            archived_path = summary.get("archived_path")
            if archived_path:
                archive_name = Path(str(archived_path)).name
            if session_file.is_file():
                archive_name = self._archive_account_session_file("logout")
            self._close_auth_attempt()
            record = self.runtime.transition_auth(
                expected_states={record.auth_state},
                expected_generation=record.session_generation,
                new_state="revoked",
                increment_generation=True,
                reason_code="remote_logout_completed",
                action="eitaa.auth.logout.completed",
                safe_metadata={
                    "remote_ok": bool(summary.get("remote_ok", True)),
                    "archive_created": archive_name is not None,
                    "session_file_present": False,
                },
            )
            return {
                "ok": True,
                "logout": {
                    "remote_ok": bool(summary.get("remote_ok", True)),
                    "local_session_archived": archive_name is not None,
                    "archive_name": archive_name,
                },
                "session_present": False,
                "login_ready": True,
                **self._account_auth_fields(record),
            }

    # --------------------------------------------------------- session archival

    def _archive_account_session_file(self, marker: str) -> str | None:
        import os

        session_file = self._core_config().session_file
        if not session_file.is_file():
            return None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        archive = session_file.with_name(
            f"{session_file.name}.{marker}.{timestamp}.bak"
        )
        try:
            os.replace(session_file, archive)
        except OSError as exc:
            raise AuthenticationRuntimeError(
                "بایگانی امن نشست حساب ناموفق بود.",
                safe_context={"error_type": type(exc).__name__},
                code="auth_session_archive_failed",
            ) from exc
        if session_file.exists():
            raise AuthenticationRuntimeError(
                "فایل نشست حساب پس از بایگانی همچنان فعال است.",
                safe_context={"session_file_present": True},
                code="auth_session_archive_verification_failed",
            )
        return archive.name
