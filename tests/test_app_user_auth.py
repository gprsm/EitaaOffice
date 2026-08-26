from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import sqlite3

import pytest

from eitaa_bridge.errors import (
    CoordinatorAuthenticationError,
    CoordinatorAuthorizationError,
    CoordinatorAuthRateLimitError,
)
from eitaa_bridge.infrastructure.coordinator import (
    AppAuthPolicy,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    PasswordHasher,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.infrastructure.coordinator.app_auth import PasswordMaterial
from eitaa_bridge.infrastructure.coordinator.schema import (
    COORDINATOR_SCHEMA_VERSION,
    SCHEMA_V1_CHECKSUM,
    SCHEMA_V1_SQL,
)


class FastTestPasswordHasher(PasswordHasher):
    iterations = 600_000

    @staticmethod
    def _digest(password: str, salt: bytes) -> bytes:
        return hashlib.sha256(bytes(salt) + password.encode("utf-8")).digest()

    def hash_password(self, password: str) -> PasswordMaterial:
        if len(password) < 4:
            return super().hash_password(password)
        salt = os.urandom(16)
        return PasswordMaterial(salt, self._digest(password, salt), self.iterations)

    def verify_password(
        self,
        password: str,
        *,
        salt: bytes,
        expected_digest: bytes,
        iterations: int,
    ) -> bool:
        del iterations
        return hmac.compare_digest(
            self._digest(password, salt),
            bytes(expected_digest),
        )

    def dummy_material(self) -> PasswordMaterial:
        salt = b"d" * 16
        return PasswordMaterial(
            salt,
            self._digest("dummy-password-value", salt),
            self.iterations,
        )


@dataclass
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


class TestPhoneProtector:
    def protect(self, canonical_phone: str) -> ProtectedPhone:
        return ProtectedPhone(
            ciphertext=hashlib.sha256(canonical_phone.encode("utf-8")).digest(),
            key_version=1,
            fingerprint=hashlib.sha256(("fingerprint:" + canonical_phone).encode("utf-8")).hexdigest(),
            display_hint="+••••••••34",
        )


def protected_phone() -> ProtectedPhone:
    return ProtectedPhone(
        ciphertext=b"protected-phone",
        key_version=1,
        fingerprint="b" * 64,
        display_hint="+••••••••67",
    )


def coordinator_with_admin(path):
    database = CoordinatorDatabase(path)
    bootstrap = database.bootstrap_legacy_account(
        protected_phone=protected_phone(),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    clock = MutableClock(datetime(2026, 7, 31, tzinfo=timezone.utc))
    auth = CoordinatorAppAuth(
        path,
        fingerprinter=StaticSubjectFingerprinter(b"test-subject-secret-value"),
        password_hasher=FastTestPasswordHasher(),
        policy=AppAuthPolicy(
            idle_timeout_minutes=30,
            absolute_timeout_hours=12,
            max_failed_attempts=3,
            lockout_minutes=15,
        ),
        clock=clock,
    )
    return database, bootstrap, auth, clock


def setup_admin(auth: CoordinatorAppAuth):
    return auth.bootstrap_admin(
        username="local.admin",
        password="correct horse battery staple",
        display_name="مدیر محلی",
        client_kind="test",
        request_id="request-bootstrap",
    )


def test_schema_v1_is_upgraded_transactionally_without_losing_users(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    app_user_id = "11111111-1111-4111-8111-111111111111"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + SCHEMA_V1_SQL
            + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
            + f"1,'{SCHEMA_V1_CHECKSUM}','now');\n"
            + "PRAGMA user_version=1;\n"
            + "COMMIT;\n"
        )
        connection.execute(
            """
            INSERT INTO app_users(
                id,display_name,global_role,status,created_at,updated_at
            ) VALUES(?,'Existing admin','admin','active','now','now')
            """,
            (app_user_id,),
        )
        connection.commit()

    CoordinatorDatabase(path).initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            COORDINATOR_SCHEMA_VERSION
        )
        assert connection.execute(
            "SELECT display_name FROM app_users WHERE id=?", (app_user_id,)
        ).fetchone() == ("Existing admin",)
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone() == (COORDINATOR_SCHEMA_VERSION,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_admin_setup_stores_hashes_not_username_password_or_session_tokens(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, bootstrap, auth, _ = coordinator_with_admin(path)
    assert auth.setup_required() is True

    issued = setup_admin(auth)

    assert issued.principal.app_user_id == bootstrap.app_user_id
    assert auth.setup_required() is False
    authorized = auth.authorize(
        issued.token,
        csrf_token=issued.csrf_token,
        require_csrf=True,
    )
    assert authorized.principal.global_role == "admin"
    with sqlite3.connect(path) as connection:
        subject, scheme, iterations, digest = connection.execute(
            """
            SELECT
                u.auth_subject_fingerprint,c.password_scheme,
                c.password_iterations,c.password_digest
            FROM app_users u
            JOIN app_user_credentials c ON c.app_user_id=u.id
            """
        ).fetchone()
        token_hash, csrf_hash = connection.execute(
            "SELECT token_hash,csrf_token_hash FROM app_user_sessions"
        ).fetchone()
    assert len(subject) == 64
    assert scheme == "pbkdf2_sha256"
    assert iterations == 600_000
    assert len(digest) == 32
    assert token_hash == hashlib.sha256(issued.token.encode("ascii")).hexdigest()
    assert csrf_hash == hashlib.sha256(issued.csrf_token.encode("ascii")).hexdigest()
    raw = path.read_bytes()
    assert b"local.admin" not in raw
    assert b"correct horse battery staple" not in raw
    assert issued.token.encode("ascii") not in raw
    assert issued.csrf_token.encode("ascii") not in raw


def test_setup_is_one_time_and_login_errors_are_generic(tmp_path):
    _, _, auth, _ = coordinator_with_admin(tmp_path / "coordinator.sqlite3")
    setup_admin(auth)
    with pytest.raises(CoordinatorAuthenticationError) as setup_error:
        setup_admin(auth)
    assert setup_error.value.code == "app_auth_setup_unavailable"

    for username, password in (
        ("missing.user", "wrong password value"),
        ("local.admin", "wrong password value"),
    ):
        with pytest.raises(CoordinatorAuthenticationError) as login_error:
            auth.authenticate(
                username=username,
                password=password,
                client_kind="test",
            )
        assert login_error.value.code == "app_auth_invalid_credentials"
        assert login_error.value.message == "نام کاربری یا رمز ورود درست نیست."


def test_failed_logins_are_throttled_and_success_resets_subject_bucket(tmp_path):
    _, _, auth, clock = coordinator_with_admin(tmp_path / "coordinator.sqlite3")
    setup_admin(auth)
    for _ in range(3):
        with pytest.raises(CoordinatorAuthenticationError):
            auth.authenticate(
                username="local.admin",
                password="wrong password value",
                client_kind="test",
            )
    with pytest.raises(CoordinatorAuthRateLimitError):
        auth.authenticate(
            username="local.admin",
            password="correct horse battery staple",
            client_kind="test",
        )
    clock.advance(minutes=16)
    issued = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="test",
    )
    assert issued.principal.global_role == "admin"


def test_admin_can_create_user_but_user_cannot_manage_users(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, _ = coordinator_with_admin(path)
    admin = setup_admin(auth)
    admin_session = auth.authorize(
        admin.token,
        csrf_token=admin.csrf_token,
        require_csrf=True,
    )
    created = auth.create_user(
        admin_session.principal,
        username="ordinary.user",
        password="a long ordinary password",
        display_name="کاربر عادی",
        global_role="user",
    )
    assert created["global_role"] == "user"
    user = auth.authenticate(
        username="ordinary.user",
        password="a long ordinary password",
        client_kind="test",
    )
    assert auth.can_use_legacy_workspace(user.principal) is False
    with pytest.raises(CoordinatorAuthorizationError) as error:
        auth.list_users(user.principal)
    assert error.value.code == "app_auth_admin_required"
    assert len(auth.list_users(admin_session.principal)) == 2


def test_self_registration_accepts_four_character_password_and_stays_non_admin(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, _ = coordinator_with_admin(path)
    setup_admin(auth)

    issued = auth.register_user(
        username="mobile.user",
        password="1234",
        display_name="کاربر موبایل",
        client_kind="browser",
    )
    session = auth.authorize(issued.token)

    assert session.principal.global_role == "user"
    assert auth.can_use_legacy_workspace(session.principal) is False
    assert auth.list_messenger_accounts(session.principal) == []
    with pytest.raises(CoordinatorAuthorizationError):
        auth.list_users(session.principal)
    with pytest.raises(CoordinatorAuthenticationError) as duplicate:
        auth.register_user(
            username="mobile.user",
            password="5678",
            display_name="کاربر تکراری",
            client_kind="browser",
        )
    assert duplicate.value.code == "app_auth_username_unavailable"


def test_self_registered_user_can_onboard_and_own_first_eitaa_account(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, clock = coordinator_with_admin(path)
    setup_admin(auth)
    issued = auth.register_user(
        username="account.owner",
        password="4321",
        display_name="مالک حساب",
        client_kind="browser",
    )
    actor = auth.authorize(issued.token).principal
    onboarding_auth = CoordinatorAppAuth(
        path,
        fingerprinter=StaticSubjectFingerprinter(b"test-subject-secret-value"),
        password_hasher=FastTestPasswordHasher(),
        phone_protector=TestPhoneProtector(),
        policy=auth.policy,
        clock=clock,
    )

    created = onboarding_auth.onboard_messenger_account(
        actor,
        provider="eitaa",
        canonical_phone="+989120000034",
        label="حساب شخصی",
    )
    accounts = onboarding_auth.list_messenger_accounts(actor)

    assert created.created is True
    assert len(accounts) == 1
    assert accounts[0]["provider"] == "eitaa"
    assert accounts[0]["membership_role"] == "owner"
    assert onboarding_auth.can_use_legacy_workspace(actor) is True


def test_password_shorter_than_four_characters_is_rejected(tmp_path):
    _, _, auth, _ = coordinator_with_admin(tmp_path / "coordinator.sqlite3")
    with pytest.raises(CoordinatorAuthenticationError) as error:
        auth.bootstrap_admin(
            username="local.admin",
            password="123",
            display_name="مدیر محلی",
            client_kind="test",
        )
    assert error.value.code == "app_auth_password_policy_failed"


def test_last_active_admin_cannot_be_disabled_or_demoted(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, _ = coordinator_with_admin(path)
    admin = setup_admin(auth)
    session = auth.authorize(admin.token)
    with pytest.raises(CoordinatorAuthorizationError) as error:
        auth.update_user(
            session.principal,
            session.principal.app_user_id,
            global_role="user",
        )
    assert error.value.code == "last_active_admin_required"


def test_archived_user_cannot_be_reactivated_or_edited(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, _ = coordinator_with_admin(path)
    admin = setup_admin(auth)
    session = auth.authorize(admin.token)
    created = auth.create_user(
        session.principal,
        username="archive.user",
        password="a long archive password",
        display_name="کاربر بایگانی",
        global_role="user",
    )
    auth.update_user(
        session.principal,
        str(created["app_user_id"]),
        status="archived",
    )
    with pytest.raises(CoordinatorAuthorizationError) as error:
        auth.update_user(
            session.principal,
            str(created["app_user_id"]),
            status="active",
        )
    assert error.value.code == "app_user_archived_immutable"


def test_csrf_idle_expiry_and_password_change_revoke_other_sessions(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, clock = coordinator_with_admin(path)
    first = setup_admin(auth)
    with pytest.raises(CoordinatorAuthorizationError) as csrf_error:
        auth.authorize(first.token, csrf_token="wrong", require_csrf=True)
    assert csrf_error.value.code == "app_auth_csrf_invalid"

    second = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="test",
    )
    first_session = auth.authorize(
        first.token,
        csrf_token=first.csrf_token,
        require_csrf=True,
    )
    auth.change_password(
        first_session,
        current_password="correct horse battery staple",
        new_password="a completely different secure password",
    )
    with pytest.raises(CoordinatorAuthenticationError):
        auth.authorize(second.token)
    changed = auth.authenticate(
        username="local.admin",
        password="a completely different secure password",
        client_kind="test",
    )
    clock.advance(minutes=31)
    with pytest.raises(CoordinatorAuthenticationError) as expired:
        auth.authorize(changed.token)
    assert expired.value.code == "app_auth_session_invalid"


def test_auth_audit_contains_safe_actions_but_no_credentials(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, _ = coordinator_with_admin(path)
    setup_admin(auth)
    with pytest.raises(CoordinatorAuthenticationError):
        auth.authenticate(
            username="unknown.user",
            password="wrong password value",
            client_kind="test",
        )
    with sqlite3.connect(path) as connection:
        actions = {
            row[0]
            for row in connection.execute(
                "SELECT action FROM audit_events WHERE action LIKE 'app_auth.%'"
            )
        }
        metadata = "\n".join(
            row[0] for row in connection.execute("SELECT safe_metadata_json FROM audit_events")
        )
    assert "app_auth.bootstrap.completed" in actions
    assert "app_auth.login.failed" in actions
    assert "unknown.user" not in metadata
    assert "wrong password value" not in metadata
