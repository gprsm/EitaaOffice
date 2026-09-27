"""Local AppUser credentials, sessions, throttling, roles, and safe audit."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
from typing import Callable, Iterator
import unicodedata
from uuid import UUID, uuid4

from ...errors import (
    CoordinatorAuthenticationError,
    CoordinatorAuthorizationError,
    CoordinatorAuthRateLimitError,
    CoordinatorSchemaError,
)
from .identity import (
    FileKeyPhoneProtector,
    PhoneProtector,
    WindowsDpapiPhoneProtector,
    default_phone_protector,
)
from .store import CoordinatorDatabase, MessengerAccountOnboardingResult

_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000
_PASSWORD_SALT_BYTES = 16
_PASSWORD_DIGEST_BYTES = 32
_MIN_PASSWORD_CHARACTERS = 4
_MAX_PASSWORD_CHARACTERS = 128
_MAX_PASSWORD_BYTES = 512
_SESSION_TOKEN_BYTES = 32
_SESSION_TOKEN = re.compile(r"^[A-Za-z0-9_-]{40,64}$")
_GLOBAL_THROTTLE_FINGERPRINT = hashlib.sha256(
    b"eitaa-bridge-app-auth-global-throttle-v1"
).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _parse_utc(value: str) -> datetime:
    selected = datetime.fromisoformat(str(value))
    if selected.tzinfo is None:
        raise ValueError("coordinator timestamp has no timezone")
    return selected.astimezone(timezone.utc)


def _canonical_uuid(value: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise CoordinatorAuthorizationError(
            "The selected local user is invalid.",
            code="app_auth_user_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise CoordinatorAuthorizationError(
            "The selected local user is invalid.",
            code="app_auth_user_invalid",
        )
    return value


def normalize_username(value: str) -> str:
    selected = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    if not 3 <= len(selected) <= 64:
        raise CoordinatorAuthenticationError(
            "نام کاربری باید بین ۳ تا ۶۴ نویسه باشد.",
            code="app_auth_username_invalid",
        )
    if not selected[0].isalnum():
        raise CoordinatorAuthenticationError(
            "نام کاربری باید با حرف یا عدد شروع شود.",
            code="app_auth_username_invalid",
        )
    for character in selected:
        category = unicodedata.category(character)
        if character in "._-" or category.startswith(("L", "N")):
            continue
        raise CoordinatorAuthenticationError(
            "نام کاربری فقط می‌تواند شامل حروف، عدد، نقطه، خط تیره یا زیرخط باشد.",
            code="app_auth_username_invalid",
        )
    return selected


def validate_display_name(value: str) -> str:
    selected = str(value or "").strip()
    if not 1 <= len(selected) <= 120 or any(
        unicodedata.category(character) in {"Cc", "Cs"} for character in selected
    ):
        raise CoordinatorAuthenticationError(
            "نام نمایشی کاربر معتبر نیست.",
            code="app_auth_display_name_invalid",
        )
    return selected


def _password_bytes(value: str, *, strict: bool) -> bytes | None:
    selected = str(value or "")
    encoded = selected.encode("utf-8", errors="strict")
    valid = (
        _MIN_PASSWORD_CHARACTERS <= len(selected) <= _MAX_PASSWORD_CHARACTERS
        and len(encoded) <= _MAX_PASSWORD_BYTES
        and "\x00" not in selected
        and "\r" not in selected
        and "\n" not in selected
    )
    if valid:
        return encoded
    if strict:
        raise CoordinatorAuthenticationError(
            "رمز باید بین ۴ تا ۱۲۸ نویسه باشد و خط جدید نداشته باشد.",
            code="app_auth_password_policy_failed",
        )
    return None


@dataclass(frozen=True, slots=True)
class AppAuthPolicy:
    idle_timeout_minutes: int = 525_600
    absolute_timeout_hours: int = 8_760
    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    def validate(self) -> None:
        values = (
            (self.idle_timeout_minutes, 5, 525_600),
            (self.absolute_timeout_hours, 1, 8_760),
            (self.max_failed_attempts, 3, 20),
            (self.lockout_minutes, 1, 1440),
        )
        if any(
            isinstance(value, bool) or not minimum <= value <= maximum
            for value, minimum, maximum in values
        ):
            raise CoordinatorAuthenticationError(
                "The local authentication policy is invalid.",
                code="app_auth_policy_invalid",
            )


@dataclass(frozen=True, slots=True)
class PasswordMaterial:
    salt: bytes
    digest: bytes
    iterations: int = _PASSWORD_ITERATIONS


class PasswordHasher:
    """Versioned PBKDF2-HMAC-SHA256 password hashing with unique salts."""

    scheme = _PASSWORD_SCHEME
    iterations = _PASSWORD_ITERATIONS

    def hash_password(self, password: str) -> PasswordMaterial:
        encoded = _password_bytes(password, strict=True)
        assert encoded is not None
        salt = os.urandom(_PASSWORD_SALT_BYTES)
        return PasswordMaterial(
            salt=salt,
            digest=hashlib.pbkdf2_hmac(
                "sha256",
                encoded,
                salt,
                self.iterations,
                dklen=_PASSWORD_DIGEST_BYTES,
            ),
            iterations=self.iterations,
        )

    def verify_password(
        self,
        password: str,
        *,
        salt: bytes,
        expected_digest: bytes,
        iterations: int,
    ) -> bool:
        encoded = _password_bytes(password, strict=False)
        if encoded is None:
            encoded = b"invalid-password-candidate"
        if not 600_000 <= int(iterations) <= 10_000_000:
            iterations = self.iterations
            expected_digest = b"\x00" * _PASSWORD_DIGEST_BYTES
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            encoded,
            bytes(salt),
            int(iterations),
            dklen=_PASSWORD_DIGEST_BYTES,
        )
        return hmac.compare_digest(actual, bytes(expected_digest))

    def dummy_material(self) -> PasswordMaterial:
        salt = hashlib.sha256(b"eitaa-bridge-app-auth-dummy-salt-v1").digest()[
            :_PASSWORD_SALT_BYTES
        ]
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            b"dummy-password-that-is-never-valid",
            salt,
            self.iterations,
            dklen=_PASSWORD_DIGEST_BYTES,
        )
        return PasswordMaterial(salt=salt, digest=digest, iterations=self.iterations)


class WindowsDpapiSubjectFingerprinter:
    """HMAC normalized usernames with a DPAPI-wrapped per-install secret."""

    def __init__(self, wrapped_key_file: str | Path) -> None:
        self._key_store = WindowsDpapiPhoneProtector(wrapped_key_file)

    def fingerprint(self, normalized_username: str) -> str:
        secret = self._key_store._load_or_create_secret()
        return hmac.new(
            secret,
            b"app-user-subject-v1\x00" + normalized_username.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class FileKeySubjectFingerprinter:
    """HMAC normalized usernames with the restricted POSIX service key."""

    def __init__(self, key_file: str | Path) -> None:
        self._key_store = FileKeyPhoneProtector(key_file)

    def fingerprint(self, normalized_username: str) -> str:
        secret = self._key_store._load_or_create_secret()
        return hmac.new(
            secret,
            b"app-user-subject-v1\x00" + normalized_username.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class StaticSubjectFingerprinter:
    """Deterministic injected fingerprinter for isolated tests."""

    def __init__(self, secret: bytes) -> None:
        if len(secret) < 16:
            raise ValueError("test subject secret is too short")
        self._secret = bytes(secret)

    def fingerprint(self, normalized_username: str) -> str:
        return hmac.new(
            self._secret,
            b"app-user-subject-v1\x00" + normalized_username.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class AppPrincipal:
    app_user_id: str
    display_name: str
    global_role: str
    session_id: str
    client_kind: str

    def safe_summary(self) -> dict[str, object]:
        return {
            "app_user_id": self.app_user_id,
            "display_name": self.display_name,
            "global_role": self.global_role,
            "permissions": {
                "manage_users": self.global_role == "admin",
            },
        }


@dataclass(frozen=True, slots=True)
class IssuedAppSession:
    principal: AppPrincipal
    token: str
    csrf_token: str
    idle_expires_at: str
    absolute_expires_at: str

    def safe_payload(self) -> dict[str, object]:
        return {
            "ok": True,
            "authenticated": True,
            "principal": self.principal.safe_summary(),
            "csrf_token": self.csrf_token,
            "idle_expires_at": self.idle_expires_at,
            "absolute_expires_at": self.absolute_expires_at,
        }


@dataclass(frozen=True, slots=True)
class AuthorizedAppSession:
    principal: AppPrincipal
    csrf_token: str | None
    idle_expires_at: str
    absolute_expires_at: str


class CoordinatorAppAuth:
    """Fail-closed AppUser credential and session service."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        policy: AppAuthPolicy | None = None,
        fingerprinter: WindowsDpapiSubjectFingerprinter
        | FileKeySubjectFingerprinter
        | StaticSubjectFingerprinter
        | None = None,
        phone_protector: PhoneProtector | None = None,
        password_hasher: PasswordHasher | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.path = Path(database_path).expanduser().resolve()
        self.database = CoordinatorDatabase(self.path)
        self.policy = policy or AppAuthPolicy()
        self.policy.validate()
        if fingerprinter is not None:
            self.fingerprinter = fingerprinter
        elif sys.platform == "win32":
            self.fingerprinter = WindowsDpapiSubjectFingerprinter(
                self.path.parent / "app-auth-subject.key.dpapi"
            )
        else:
            self.fingerprinter = FileKeySubjectFingerprinter(
                self.path.parent / "app-auth-subject.key"
            )
        self.phone_protector = phone_protector or default_phone_protector(
            self.path.parent
        )
        self.password_hasher = password_hasher or PasswordHasher()
        self.clock = clock
        self._dummy_material: PasswordMaterial | None = None

    def initialize(self) -> None:
        self.database.initialize()

    def setup_required(self) -> bool:
        self.initialize()
        with self._connect() as connection:
            return (
                int(
                    connection.execute(
                        "SELECT COUNT(*) FROM app_user_credentials"
                    ).fetchone()[0]
                )
                == 0
            )

    def bootstrap_admin(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        client_kind: str,
        request_id: str | None = None,
    ) -> IssuedAppSession:
        normalized = normalize_username(username)
        selected_name = validate_display_name(display_name)
        material = self.password_hasher.hash_password(password)
        fingerprint = self.fingerprinter.fingerprint(normalized)
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                credential_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM app_user_credentials"
                    ).fetchone()[0]
                )
                admins = connection.execute(
                    """
                    SELECT id FROM app_users
                    WHERE global_role='admin' AND status='active'
                    ORDER BY created_at,id
                    """
                ).fetchall()
                app_user_count = int(
                    connection.execute("SELECT COUNT(*) FROM app_users").fetchone()[0]
                )
                if credential_count != 0 or (
                    len(admins) != 1 and app_user_count != 0
                ):
                    raise CoordinatorAuthenticationError(
                        "راه‌اندازی مدیر اولیه دیگر در دسترس نیست.",
                        code="app_auth_setup_unavailable",
                    )
                if app_user_count == 0:
                    app_user_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO app_users(
                            id,display_name,global_role,status,
                            auth_subject_fingerprint,created_at,updated_at
                        ) VALUES(?,?,'admin','active',?,?,?)
                        """,
                        (
                            app_user_id,
                            selected_name,
                            fingerprint,
                            _as_utc_text(now),
                            _as_utc_text(now),
                        ),
                    )
                    bootstrap_source = "empty_coordinator"
                else:
                    app_user_id = str(admins[0]["id"])
                    cursor = connection.execute(
                        """
                        UPDATE app_users
                        SET display_name=?,auth_subject_fingerprint=?,updated_at=?
                        WHERE id=? AND auth_subject_fingerprint IS NULL
                        """,
                        (selected_name, fingerprint, _as_utc_text(now), app_user_id),
                    )
                    if cursor.rowcount != 1:
                        raise CoordinatorAuthenticationError(
                            "راه‌اندازی مدیر اولیه دیگر در دسترس نیست.",
                            code="app_auth_setup_unavailable",
                        )
                    bootstrap_source = "legacy_migration"
                self._insert_credential(connection, app_user_id, material, now)
                issued = self._issue_session(
                    connection,
                    app_user_id=app_user_id,
                    display_name=selected_name,
                    global_role="admin",
                    client_kind=client_kind,
                    now=now,
                )
                self._append_audit(
                    connection,
                    actor_type="system",
                    actor_app_user_id=None,
                    actor_global_role=None,
                    action="app_auth.bootstrap.completed",
                    target_id=app_user_id,
                    result="succeeded",
                    reason_code="initial_admin_credential_created",
                    request_id=request_id,
                    safe_metadata={
                        "client_kind": client_kind,
                        "bootstrap_source": bootstrap_source,
                    },
                )
                connection.commit()
                return issued
        except CoordinatorAuthenticationError:
            raise
        except sqlite3.IntegrityError as exc:
            raise CoordinatorAuthenticationError(
                "راه‌اندازی مدیر اولیه کامل نشد.",
                code="app_auth_setup_conflict",
            ) from exc
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "راه‌اندازی مدیر اولیه کامل نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_setup_failed",
            ) from exc

    def authenticate(
        self,
        *,
        username: str,
        password: str,
        client_kind: str,
        client_address: str | None = None,
        request_id: str | None = None,
    ) -> IssuedAppSession:
        self.initialize()
        normalized = self._normalize_login_username(username)
        fingerprint = self.fingerprinter.fingerprint(normalized)
        client_fingerprint = self._client_fingerprint(client_address)
        now = self._now()
        with self._connect() as connection:
            blocked = self._is_blocked(
                connection,
                fingerprint,
                client_fingerprint,
                now,
            )
            row = connection.execute(
                """
                SELECT
                    u.id,u.display_name,u.global_role,u.status,
                    c.password_salt,c.password_digest,c.password_iterations,
                    c.credential_version
                FROM app_users u
                JOIN app_user_credentials c ON c.app_user_id=u.id
                WHERE u.auth_subject_fingerprint=?
                """,
                (fingerprint,),
            ).fetchone()
        if blocked:
            self._audit_throttled_attempt(
                fingerprint=fingerprint,
                app_user_id=str(row["id"]) if row is not None else None,
                client_kind=client_kind,
                request_id=request_id,
            )
            raise CoordinatorAuthRateLimitError(
                "ورود موقتاً محدود شده است؛ کمی بعد دوباره تلاش کنید.",
                code="app_auth_rate_limited",
            )
        material = (
            PasswordMaterial(
                salt=bytes(row["password_salt"]),
                digest=bytes(row["password_digest"]),
                iterations=int(row["password_iterations"]),
            )
            if row is not None
            else self._dummy_password_material()
        )
        verified = self.password_hasher.verify_password(
            password,
            salt=material.salt,
            expected_digest=material.digest,
            iterations=material.iterations,
        )
        if row is None or str(row["status"]) != "active" or not verified:
            self._record_failed_login(
                fingerprint=fingerprint,
                client_fingerprint=client_fingerprint,
                app_user_id=str(row["id"]) if row is not None else None,
                client_kind=client_kind,
                request_id=request_id,
            )
            raise CoordinatorAuthenticationError(
                "نام کاربری یا رمز ورود درست نیست.",
                code="app_auth_invalid_credentials",
            )
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute(
                    """
                    SELECT u.display_name,u.global_role,u.status,c.credential_version
                    FROM app_users u
                    JOIN app_user_credentials c ON c.app_user_id=u.id
                    WHERE u.id=? AND u.auth_subject_fingerprint=?
                    """,
                    (str(row["id"]), fingerprint),
                ).fetchone()
                if (
                    current is None
                    or str(current["status"]) != "active"
                    or int(current["credential_version"])
                    != int(row["credential_version"])
                ):
                    raise CoordinatorAuthenticationError(
                        "نام کاربری یا رمز ورود درست نیست.",
                        code="app_auth_invalid_credentials",
                    )
                now = self._now()
                connection.execute(
                    """
                    UPDATE app_user_credentials
                    SET last_authenticated_at=?,updated_at=?
                    WHERE app_user_id=?
                    """,
                    (_as_utc_text(now), _as_utc_text(now), str(row["id"])),
                )
                connection.execute(
                    "DELETE FROM app_auth_throttles WHERE subject_fingerprint=?",
                    (fingerprint,),
                )
                issued = self._issue_session(
                    connection,
                    app_user_id=str(row["id"]),
                    display_name=str(current["display_name"]),
                    global_role=str(current["global_role"]),
                    client_kind=client_kind,
                    now=now,
                )
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=issued.principal.app_user_id,
                    actor_global_role=issued.principal.global_role,
                    action="app_auth.login.succeeded",
                    target_id=issued.principal.app_user_id,
                    result="succeeded",
                    reason_code="local_password_verified",
                    request_id=request_id,
                    safe_metadata={"client_kind": client_kind},
                )
                connection.commit()
                return issued
        except CoordinatorAuthenticationError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "ورود محلی کامل نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_login_failed",
            ) from exc

    def authorize(
        self,
        token: str | None,
        *,
        csrf_token: str | None = None,
        require_csrf: bool = False,
        rotate_csrf: bool = False,
        request_id: str | None = None,
    ) -> AuthorizedAppSession:
        self.initialize()
        selected_token = str(token or "")
        if not _SESSION_TOKEN.fullmatch(selected_token):
            raise CoordinatorAuthenticationError(
                "برای ادامه وارد نرم‌افزار شوید.",
                code="app_auth_required",
            )
        token_hash = hashlib.sha256(selected_token.encode("ascii")).hexdigest()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT
                        s.id,s.app_user_id,s.csrf_token_hash,s.status,s.client_kind,
                        s.created_at,s.last_seen_at,s.idle_expires_at,s.absolute_expires_at,
                        u.display_name,u.global_role,u.status AS user_status
                    FROM app_user_sessions s
                    JOIN app_users u ON u.id=s.app_user_id
                    WHERE s.token_hash=?
                    """,
                    (token_hash,),
                ).fetchone()
                if row is None or str(row["status"]) != "active":
                    raise CoordinatorAuthenticationError(
                        "نشست ورود نرم‌افزار معتبر نیست.",
                        code="app_auth_session_invalid",
                    )
                now = self._now()
                stored_absolute = _parse_utc(str(row["absolute_expires_at"]))
                configured_absolute = _parse_utc(str(row["created_at"])) + timedelta(
                    hours=self.policy.absolute_timeout_hours
                )
                absolute = max(stored_absolute, configured_absolute)
                expired = (
                    _parse_utc(str(row["idle_expires_at"])) <= now
                    or absolute <= now
                )
                if expired or str(row["user_status"]) != "active":
                    connection.execute(
                        """
                        UPDATE app_user_sessions
                        SET status=?,revoked_at=?,safe_reason_code=?
                        WHERE id=? AND status='active'
                        """,
                        (
                            "expired" if expired else "revoked",
                            _as_utc_text(now),
                            "session_timeout" if expired else "app_user_not_active",
                            str(row["id"]),
                        ),
                    )
                    self._append_audit(
                        connection,
                        actor_type="system",
                        actor_app_user_id=None,
                        actor_global_role=None,
                        action=(
                            "app_auth.session.expired"
                            if expired
                            else "app_auth.session.revoked"
                        ),
                        target_id=str(row["app_user_id"]),
                        result="succeeded",
                        reason_code=(
                            "session_timeout" if expired else "app_user_not_active"
                        ),
                        request_id=request_id,
                        safe_metadata={"client_kind": str(row["client_kind"])},
                    )
                    connection.commit()
                    raise CoordinatorAuthenticationError(
                        "نشست ورود نرم‌افزار معتبر نیست.",
                        code="app_auth_session_invalid",
                    )
                if require_csrf:
                    supplied_hash = hashlib.sha256(
                        str(csrf_token or "").encode("utf-8")
                    ).hexdigest()
                    if not csrf_token or not hmac.compare_digest(
                        supplied_hash, str(row["csrf_token_hash"])
                    ):
                        self._append_audit(
                            connection,
                            actor_type="app_user",
                            actor_app_user_id=str(row["app_user_id"]),
                            actor_global_role=str(row["global_role"]),
                            action="app_auth.csrf.rejected",
                            target_id=str(row["app_user_id"]),
                            result="rejected",
                            reason_code="csrf_token_invalid",
                            request_id=request_id,
                            safe_metadata={"client_kind": str(row["client_kind"])},
                        )
                        connection.commit()
                        raise CoordinatorAuthorizationError(
                            "درخواست امنیتی معتبر نیست؛ صفحه را تازه‌سازی کنید.",
                            code="app_auth_csrf_invalid",
                        )
                next_idle = min(
                    now + timedelta(minutes=self.policy.idle_timeout_minutes),
                    absolute,
                )
                raw_csrf = (
                    self._csrf_for_session_token(selected_token)
                    if rotate_csrf
                    else None
                )
                csrf_hash = (
                    hashlib.sha256(raw_csrf.encode("ascii")).hexdigest()
                    if raw_csrf
                    else str(row["csrf_token_hash"])
                )
                connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET last_seen_at=?,idle_expires_at=?,absolute_expires_at=?,csrf_token_hash=?
                    WHERE id=? AND status='active'
                    """,
                    (
                        _as_utc_text(now),
                        _as_utc_text(next_idle),
                        _as_utc_text(absolute),
                        csrf_hash,
                        str(row["id"]),
                    ),
                )
                connection.commit()
                return AuthorizedAppSession(
                    principal=AppPrincipal(
                        app_user_id=str(row["app_user_id"]),
                        display_name=str(row["display_name"]),
                        global_role=str(row["global_role"]),
                        session_id=str(row["id"]),
                        client_kind=str(row["client_kind"]),
                    ),
                    csrf_token=raw_csrf,
                    idle_expires_at=_as_utc_text(next_idle),
                    absolute_expires_at=_as_utc_text(absolute),
                )
        except (CoordinatorAuthenticationError, CoordinatorAuthorizationError):
            raise
        except (sqlite3.Error, ValueError) as exc:
            raise CoordinatorAuthenticationError(
                "نشست ورود نرم‌افزار بررسی نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_session_check_failed",
            ) from exc

    def logout(
        self,
        session: AuthorizedAppSession,
        *,
        request_id: str | None = None,
    ) -> None:
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET status='revoked',revoked_at=?,safe_reason_code='operator_logout'
                    WHERE id=? AND status='active'
                    """,
                    (_as_utc_text(now), session.principal.session_id),
                )
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=session.principal.app_user_id,
                    actor_global_role=session.principal.global_role,
                    action="app_auth.logout",
                    target_id=session.principal.app_user_id,
                    result="succeeded",
                    reason_code="operator_logout",
                    request_id=request_id,
                    safe_metadata={"client_kind": session.principal.client_kind},
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "خروج از نرم‌افزار کامل نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_logout_failed",
            ) from exc

    def logout_all(
        self,
        session: AuthorizedAppSession,
        *,
        request_id: str | None = None,
    ) -> int:
        """Revoke every active session owned by the authenticated AppUser."""

        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET status='revoked',revoked_at=?,safe_reason_code='operator_logout_all'
                    WHERE app_user_id=? AND status='active'
                    """,
                    (_as_utc_text(now), session.principal.app_user_id),
                )
                revoked = max(0, int(cursor.rowcount))
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=session.principal.app_user_id,
                    actor_global_role=session.principal.global_role,
                    action="app_auth.logout_all",
                    target_id=session.principal.app_user_id,
                    result="succeeded",
                    reason_code="operator_logout_all",
                    request_id=request_id,
                    safe_metadata={"sessions_revoked": revoked},
                )
                connection.commit()
                return revoked
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "خروج از همهٔ نشست‌های نرم‌افزار کامل نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_logout_all_failed",
            ) from exc

    def list_own_sessions(
        self,
        session: AuthorizedAppSession,
    ) -> list[dict[str, object]]:
        """Return safe device/session metadata without token hashes or IP data."""

        now = self._now()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id,status,client_kind,created_at,last_seen_at,
                       idle_expires_at,absolute_expires_at,revoked_at,safe_reason_code
                FROM app_user_sessions
                WHERE app_user_id=?
                ORDER BY CASE WHEN status='active' THEN 0 ELSE 1 END,
                         last_seen_at DESC,id
                LIMIT 50
                """,
                (session.principal.app_user_id,),
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            status = str(row["status"])
            idle = _parse_utc(str(row["idle_expires_at"]))
            absolute = _parse_utc(str(row["absolute_expires_at"]))
            if status == "active" and (idle <= now or absolute <= now):
                status = "expired"
            client_kind = str(row["client_kind"])
            result.append(
                {
                    "session_id": str(row["id"]),
                    "current": str(row["id"]) == session.principal.session_id,
                    "status": status,
                    "client_kind": client_kind,
                    "device_label": {
                        "electron": "Windows desktop app",
                        "browser": "Web browser",
                        "api": "Local API client",
                        "test": "Test client",
                    }.get(client_kind, "Local client"),
                    "created_at": str(row["created_at"]),
                    "last_seen_at": str(row["last_seen_at"]),
                    "idle_expires_at": str(row["idle_expires_at"]),
                    "absolute_expires_at": str(row["absolute_expires_at"]),
                    "revoked_at": str(row["revoked_at"]) if row["revoked_at"] else None,
                    "safe_reason_code": (
                        str(row["safe_reason_code"]) if row["safe_reason_code"] else None
                    ),
                    "expires_soon": (
                        status == "active"
                        and min(idle, absolute) <= now + timedelta(minutes=10)
                    ),
                    "recent_login": (
                        str(row["id"]) != session.principal.session_id
                        and status == "active"
                        and _parse_utc(str(row["created_at"]))
                        >= now - timedelta(minutes=15)
                    ),
                }
            )
        return result

    def revoke_own_session(
        self,
        session: AuthorizedAppSession,
        target_session_id: str,
        *,
        request_id: str | None = None,
    ) -> bool:
        """Revoke one session only when it belongs to the authenticated AppUser."""

        target_id = _canonical_uuid(target_session_id)
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT status,client_kind FROM app_user_sessions
                    WHERE id=? AND app_user_id=?
                    """,
                    (target_id, session.principal.app_user_id),
                ).fetchone()
                if row is None:
                    raise CoordinatorAuthorizationError(
                        "The selected session is unavailable.",
                        code="app_auth_session_not_found",
                    )
                cursor = connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET status='revoked',revoked_at=?,safe_reason_code='operator_revoked_device'
                    WHERE id=? AND app_user_id=? AND status='active'
                    """,
                    (_as_utc_text(now), target_id, session.principal.app_user_id),
                )
                revoked = cursor.rowcount == 1
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=session.principal.app_user_id,
                    actor_global_role=session.principal.global_role,
                    action="app_auth.session.device_revoked",
                    target_id=session.principal.app_user_id,
                    result="succeeded",
                    reason_code="operator_revoked_device",
                    request_id=request_id,
                    safe_metadata={
                        "target_session_id": target_id,
                        "target_client_kind": str(row["client_kind"]),
                        "current_session": target_id == session.principal.session_id,
                        "session_was_active": revoked,
                    },
                )
                connection.commit()
                return revoked
        except CoordinatorAuthorizationError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "The selected session could not be revoked.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_session_revoke_failed",
            ) from exc

    def revoke_user_sessions(
        self,
        actor: AppPrincipal,
        target_app_user_id: str,
        *,
        request_id: str | None = None,
    ) -> int:
        """Admin-only whole-user revocation without exposing device metadata."""

        self._require_admin(actor)
        target_id = _canonical_uuid(target_app_user_id)
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._assert_active_admin(connection, actor)
                target = connection.execute(
                    "SELECT id FROM app_users WHERE id=?",
                    (target_id,),
                ).fetchone()
                if target is None:
                    raise CoordinatorAuthenticationError(
                        "کاربر نرم‌افزار پیدا نشد.",
                        code="app_user_not_found",
                    )
                cursor = connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET status='revoked',revoked_at=?,safe_reason_code='admin_revoked_sessions'
                    WHERE app_user_id=? AND status='active'
                    """,
                    (_as_utc_text(now), target_id),
                )
                revoked = max(0, int(cursor.rowcount))
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=actor.app_user_id,
                    actor_global_role=actor.global_role,
                    action="app_auth.sessions.revoked",
                    target_id=target_id,
                    result="succeeded",
                    reason_code="admin_revoked_sessions",
                    request_id=request_id,
                    safe_metadata={"sessions_revoked": revoked},
                )
                connection.commit()
                return revoked
        except (CoordinatorAuthenticationError, CoordinatorAuthorizationError):
            raise
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "نشست‌های کاربر باطل نشدند.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_revoke_sessions_failed",
            ) from exc

    def list_users(self, actor: AppPrincipal) -> list[dict[str, object]]:
        self._require_admin(actor)
        now = _as_utc_text(self._now())
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.id,u.display_name,u.global_role,u.status,u.created_at,u.updated_at,
                    CASE WHEN c.app_user_id IS NULL THEN 0 ELSE 1 END AS credential_configured,
                    (SELECT COUNT(*) FROM app_user_sessions s
                     WHERE s.app_user_id=u.id AND s.status='active'
                       AND s.idle_expires_at>? AND s.absolute_expires_at>?) AS active_session_count
                FROM app_users u
                LEFT JOIN app_user_credentials c ON c.app_user_id=u.id
                ORDER BY u.created_at,u.id
                """,
                (now, now),
            ).fetchall()
        return [
            {
                "app_user_id": str(row["id"]),
                "display_name": str(row["display_name"]),
                "global_role": str(row["global_role"]),
                "status": str(row["status"]),
                "credential_configured": bool(row["credential_configured"]),
                "active_session_count": int(row["active_session_count"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]

    def list_phone_accounts(self, actor: AppPrincipal) -> list[dict[str, object]]:
        """Admin-only access map; protected phone material never leaves SQLite."""

        self._require_admin(actor)
        with self._connect() as connection:
            phone_rows = connection.execute(
                """
                SELECT id,display_hint,status,created_at,updated_at
                FROM phone_accounts ORDER BY created_at,id
                """
            ).fetchall()
            messenger_rows = connection.execute(
                """
                SELECT id,phone_account_id,provider,label,lifecycle_state
                FROM messenger_accounts ORDER BY provider,id
                """
            ).fetchall()
            membership_rows = connection.execute(
                """
                SELECT m.id,m.phone_account_id,m.app_user_id,m.role,m.status,
                       u.display_name,u.global_role,u.status AS app_user_status
                FROM phone_account_memberships m
                JOIN app_users u ON u.id=m.app_user_id
                ORDER BY u.display_name,m.id
                """
            ).fetchall()
        messengers: dict[str, list[dict[str, object]]] = {}
        for row in messenger_rows:
            messengers.setdefault(str(row["phone_account_id"]), []).append(
                {
                    "messenger_account_id": str(row["id"]),
                    "provider": str(row["provider"]),
                    "label": str(row["label"]) if row["label"] is not None else None,
                    "lifecycle_state": str(row["lifecycle_state"]),
                }
            )
        memberships: dict[str, list[dict[str, object]]] = {}
        for row in membership_rows:
            memberships.setdefault(str(row["phone_account_id"]), []).append(
                {
                    "membership_id": str(row["id"]),
                    "app_user_id": str(row["app_user_id"]),
                    "display_name": str(row["display_name"]),
                    "global_role": str(row["global_role"]),
                    "app_user_status": str(row["app_user_status"]),
                    "role": str(row["role"]),
                    "status": str(row["status"]),
                }
            )
        return [
            {
                "phone_account_id": str(row["id"]),
                "phone_hint": str(row["display_hint"] or ""),
                "status": str(row["status"]),
                "messenger_accounts": messengers.get(str(row["id"]), []),
                "memberships": memberships.get(str(row["id"]), []),
            }
            for row in phone_rows
        ]

    def update_phone_account_membership(
        self,
        actor: AppPrincipal,
        *,
        phone_account_id: str,
        app_user_id: str,
        role: str,
        status: str,
        request_id: str | None = None,
    ) -> dict[str, object]:
        """Create or update one exact PhoneAccount grant and revoke stale sessions."""

        self._require_admin(actor)
        phone_id = _canonical_uuid(phone_account_id)
        target_id = _canonical_uuid(app_user_id)
        selected_role = str(role or "").strip()
        selected_status = str(status or "").strip()
        if selected_role not in {"owner", "operator", "viewer"}:
            raise CoordinatorAuthorizationError(
                "The PhoneAccount membership role is invalid.",
                code="phone_account_membership_role_invalid",
            )
        if selected_status not in {"active", "revoked"}:
            raise CoordinatorAuthorizationError(
                "The PhoneAccount membership status is invalid.",
                code="phone_account_membership_status_invalid",
            )
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._assert_active_admin(connection, actor)
                phone = connection.execute(
                    "SELECT status FROM phone_accounts WHERE id=?", (phone_id,)
                ).fetchone()
                user = connection.execute(
                    "SELECT display_name,status FROM app_users WHERE id=?", (target_id,)
                ).fetchone()
                if phone is None:
                    raise CoordinatorAuthorizationError(
                        "The PhoneAccount was not found.", code="phone_account_not_found"
                    )
                if user is None:
                    raise CoordinatorAuthorizationError(
                        "The AppUser was not found.", code="app_user_not_found"
                    )
                if selected_status == "active" and (
                    str(phone["status"]) != "active" or str(user["status"]) != "active"
                ):
                    raise CoordinatorAuthorizationError(
                        "Only active users may receive an active PhoneAccount membership.",
                        code="phone_account_membership_target_inactive",
                    )
                existing = connection.execute(
                    """
                    SELECT id,role,status FROM phone_account_memberships
                    WHERE app_user_id=? AND phone_account_id=?
                    """,
                    (target_id, phone_id),
                ).fetchone()
                if existing is None:
                    if selected_status != "active":
                        raise CoordinatorAuthorizationError(
                            "A new PhoneAccount membership must start active.",
                            code="phone_account_membership_new_revoked",
                        )
                    membership_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO phone_account_memberships(
                            id,app_user_id,phone_account_id,role,status,
                            created_by_app_user_id,created_at,updated_at
                        ) VALUES(?,?,?,?, 'active',?,?,?)
                        """,
                        (
                            membership_id,
                            target_id,
                            phone_id,
                            selected_role,
                            actor.app_user_id,
                            _as_utc_text(now),
                            _as_utc_text(now),
                        ),
                    )
                    action = "phone_account.membership.created"
                    previous_role = None
                    previous_status = None
                else:
                    membership_id = str(existing["id"])
                    previous_role = str(existing["role"])
                    previous_status = str(existing["status"])
                    connection.execute(
                        """
                        UPDATE phone_account_memberships
                        SET role=?,status=?,revoked_by_app_user_id=?,updated_at=?
                        WHERE id=?
                        """,
                        (
                            selected_role,
                            selected_status,
                            actor.app_user_id if selected_status == "revoked" else None,
                            _as_utc_text(now),
                            membership_id,
                        ),
                    )
                    action = (
                        "phone_account.membership.revoked"
                        if selected_status == "revoked"
                        else "phone_account.membership.updated"
                    )
                revoked = connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET status='revoked',revoked_at=?,safe_reason_code='membership_access_changed'
                    WHERE app_user_id=? AND status='active'
                    """,
                    (_as_utc_text(now), target_id),
                ).rowcount
                CoordinatorDatabase._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=actor.app_user_id,
                    actor_global_role=actor.global_role,
                    action=action,
                    target_type="phone_account_membership",
                    target_id=membership_id,
                    phone_account_id=phone_id,
                    messenger_account_id=None,
                    provider=None,
                    result="succeeded",
                    reason_code="admin_updated_phone_account_access",
                    request_id=request_id,
                    safe_metadata={
                        "app_user_id": target_id,
                        "previous_role": previous_role,
                        "role": selected_role,
                        "previous_status": previous_status,
                        "status": selected_status,
                        "sessions_revoked": max(0, int(revoked)),
                    },
                )
                connection.commit()
                return {
                    "membership_id": membership_id,
                    "phone_account_id": phone_id,
                    "app_user_id": target_id,
                    "display_name": str(user["display_name"]),
                    "role": selected_role,
                    "status": selected_status,
                    "sessions_revoked": max(0, int(revoked)),
                }
        except (CoordinatorAuthenticationError, CoordinatorAuthorizationError):
            raise
        except sqlite3.IntegrityError as exc:
            code = (
                "phone_account_last_owner_required"
                if "last_active_owner_required" in str(exc)
                else "phone_account_membership_conflict"
            )
            raise CoordinatorAuthorizationError(
                "At least one active owner must remain on the PhoneAccount.", code=code
            ) from exc
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "The PhoneAccount membership could not be updated.",
                safe_context={"error_type": type(exc).__name__},
                code="phone_account_membership_update_failed",
            ) from exc

    def can_use_legacy_workspace(self, actor: AppPrincipal) -> bool:
        if actor.global_role == "admin":
            return True
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM app_users u
                JOIN phone_account_memberships m ON m.app_user_id=u.id
                WHERE u.id=? AND u.status='active' AND m.status='active'
                LIMIT 1
                """,
                (actor.app_user_id,),
            ).fetchone()
        return row is not None

    def list_messenger_accounts(self, actor: AppPrincipal) -> list[dict[str, object]]:
        """List only accounts allowed by the actor's exact PhoneAccount grants."""

        return self.database.list_accessible_messenger_accounts(
            app_user_id=actor.app_user_id,
            global_role=actor.global_role,
        )

    def onboard_messenger_account(
        self,
        actor: AppPrincipal,
        *,
        provider: str,
        canonical_phone: str,
        label: str | None,
        request_id: str | None = None,
    ) -> MessengerAccountOnboardingResult:
        """Protect private identity, then hand only ciphertext to persistence."""

        protected_phone = self.phone_protector.protect(canonical_phone)
        return self.database.onboard_messenger_account(
            actor_app_user_id=actor.app_user_id,
            actor_global_role=actor.global_role,
            protected_phone=protected_phone,
            provider=provider,
            label=label,
            request_id=request_id,
        )

    def require_messenger_account_access(
        self,
        actor: AppPrincipal,
        messenger_account_id: str,
        *,
        operation: str,
    ) -> dict[str, object]:
        try:
            return self.database.require_messenger_account_access(
                messenger_account_id,
                app_user_id=actor.app_user_id,
                global_role=actor.global_role,
                operation=operation,
            )
        except CoordinatorSchemaError as exc:
            if exc.code in {
                "messenger_account_access_denied",
                "messenger_account_actor_inactive",
            }:
                raise CoordinatorAuthorizationError(
                    "You cannot access the selected messaging account.",
                    safe_context={"messenger_account_id": str(messenger_account_id)},
                    code="messenger_account_access_denied",
                ) from exc
            raise

    def create_user(
        self,
        actor: AppPrincipal,
        *,
        username: str,
        password: str,
        display_name: str,
        global_role: str,
        request_id: str | None = None,
    ) -> dict[str, object]:
        self._require_admin(actor)
        normalized = normalize_username(username)
        selected_name = validate_display_name(display_name)
        selected_role = self._validate_role(global_role)
        fingerprint = self.fingerprinter.fingerprint(normalized)
        material = self.password_hasher.hash_password(password)
        app_user_id = str(uuid4())
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._assert_active_admin(connection, actor)
                connection.execute(
                    """
                    INSERT INTO app_users(
                        id,display_name,global_role,status,auth_subject_fingerprint,
                        created_at,updated_at
                    ) VALUES(?,?,?,'active',?,?,?)
                    """,
                    (
                        app_user_id,
                        selected_name,
                        selected_role,
                        fingerprint,
                        _as_utc_text(now),
                        _as_utc_text(now),
                    ),
                )
                self._insert_credential(connection, app_user_id, material, now)
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=actor.app_user_id,
                    actor_global_role=actor.global_role,
                    action="app_user.created",
                    target_id=app_user_id,
                    result="succeeded",
                    reason_code="admin_created_local_user",
                    request_id=request_id,
                    safe_metadata={
                        "global_role": selected_role,
                        "status": "active",
                    },
                )
                connection.commit()
        except CoordinatorAuthorizationError:
            raise
        except sqlite3.IntegrityError as exc:
            raise CoordinatorAuthenticationError(
                "این نام کاربری قابل استفاده نیست.",
                code="app_auth_username_unavailable",
            ) from exc
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "کاربر نرم‌افزار ایجاد نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_user_create_failed",
            ) from exc
        return {
            "app_user_id": app_user_id,
            "display_name": selected_name,
            "global_role": selected_role,
            "status": "active",
            "credential_configured": True,
        }

    def register_user(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        client_kind: str,
        request_id: str | None = None,
    ) -> IssuedAppSession:
        """Create a non-admin local user and issue its first isolated session."""

        normalized = normalize_username(username)
        selected_name = validate_display_name(display_name)
        fingerprint = self.fingerprinter.fingerprint(normalized)
        material = self.password_hasher.hash_password(password)
        app_user_id = str(uuid4())
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                active_admin = connection.execute(
                    """
                    SELECT id FROM app_users
                    WHERE global_role='admin' AND status='active'
                      AND auth_subject_fingerprint IS NOT NULL
                    LIMIT 1
                    """
                ).fetchone()
                if active_admin is None:
                    raise CoordinatorAuthenticationError(
                        "ثبت‌نام پس از راه‌اندازی مدیر اولیه در دسترس است.",
                        code="app_auth_registration_unavailable",
                    )
                connection.execute(
                    """
                    INSERT INTO app_users(
                        id,display_name,global_role,status,auth_subject_fingerprint,
                        created_at,updated_at
                    ) VALUES(?,?,'user','active',?,?,?)
                    """,
                    (
                        app_user_id,
                        selected_name,
                        fingerprint,
                        _as_utc_text(now),
                        _as_utc_text(now),
                    ),
                )
                self._insert_credential(connection, app_user_id, material, now)
                issued = self._issue_session(
                    connection,
                    app_user_id=app_user_id,
                    display_name=selected_name,
                    global_role="user",
                    client_kind=client_kind,
                    now=now,
                )
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=app_user_id,
                    actor_global_role="user",
                    action="app_user.self_registered",
                    target_id=app_user_id,
                    result="succeeded",
                    reason_code="self_registered_local_user",
                    request_id=request_id,
                    safe_metadata={"global_role": "user", "client_kind": client_kind},
                )
                connection.commit()
                return issued
        except CoordinatorAuthenticationError:
            raise
        except sqlite3.IntegrityError as exc:
            raise CoordinatorAuthenticationError(
                "این نام کاربری قابل استفاده نیست.",
                code="app_auth_username_unavailable",
            ) from exc
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "ثبت‌نام کاربر کامل نشد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_user_registration_failed",
            ) from exc

    def update_user(
        self,
        actor: AppPrincipal,
        target_app_user_id: str,
        *,
        global_role: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, object]:
        self._require_admin(actor)
        target_id = _canonical_uuid(target_app_user_id)
        selected_role = self._validate_role(global_role) if global_role is not None else None
        selected_status = self._validate_status(status) if status is not None else None
        if selected_role is None and selected_status is None:
            raise CoordinatorAuthenticationError(
                "هیچ تغییری برای کاربر انتخاب نشده است.",
                code="app_user_update_empty",
            )
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._assert_active_admin(connection, actor)
                row = connection.execute(
                    "SELECT display_name,global_role,status FROM app_users WHERE id=?",
                    (target_id,),
                ).fetchone()
                if row is None:
                    raise CoordinatorAuthenticationError(
                        "کاربر نرم‌افزار پیدا نشد.",
                        code="app_user_not_found",
                    )
                if str(row["status"]) == "archived":
                    raise CoordinatorAuthorizationError(
                        "کاربر بایگانی‌شده دوباره فعال یا ویرایش نمی‌شود.",
                        code="app_user_archived_immutable",
                    )
                next_role = selected_role or str(row["global_role"])
                next_status = selected_status or str(row["status"])
                connection.execute(
                    """
                    UPDATE app_users SET global_role=?,status=?,updated_at=? WHERE id=?
                    """,
                    (next_role, next_status, _as_utc_text(now), target_id),
                )
                access_changed = (
                    next_role != str(row["global_role"])
                    or next_status != str(row["status"])
                )
                revoked = 0
                if access_changed:
                    cursor = connection.execute(
                        """
                        UPDATE app_user_sessions
                        SET status='revoked',revoked_at=?,safe_reason_code='app_user_access_changed'
                        WHERE app_user_id=? AND status='active'
                        """,
                        (_as_utc_text(now), target_id),
                    )
                    revoked = max(0, int(cursor.rowcount))
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=actor.app_user_id,
                    actor_global_role=actor.global_role,
                    action="app_user.access.updated",
                    target_id=target_id,
                    result="succeeded",
                    reason_code="admin_updated_role_or_status",
                    request_id=request_id,
                    safe_metadata={
                        "previous_global_role": str(row["global_role"]),
                        "global_role": next_role,
                        "previous_status": str(row["status"]),
                        "status": next_status,
                        "sessions_revoked": revoked,
                    },
                )
                connection.commit()
                return {
                    "app_user_id": target_id,
                    "display_name": str(row["display_name"]),
                    "global_role": next_role,
                    "status": next_status,
                    "credential_configured": True,
                }
        except (CoordinatorAuthenticationError, CoordinatorAuthorizationError):
            raise
        except sqlite3.IntegrityError as exc:
            code = (
                "last_active_admin_required"
                if "last_active_admin_required" in str(exc)
                else "app_user_update_conflict"
            )
            raise CoordinatorAuthorizationError(
                "آخرین مدیر فعال را نمی‌توان غیرفعال یا به کاربر عادی تبدیل کرد.",
                code=code,
            ) from exc
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "دسترسی کاربر تغییر نکرد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_user_update_failed",
            ) from exc

    def change_password(
        self,
        session: AuthorizedAppSession,
        *,
        current_password: str,
        new_password: str,
        request_id: str | None = None,
    ) -> None:
        material = self.password_hasher.hash_password(new_password)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT password_salt,password_digest,password_iterations
                FROM app_user_credentials WHERE app_user_id=?
                """,
                (session.principal.app_user_id,),
            ).fetchone()
        if row is None or not self.password_hasher.verify_password(
            current_password,
            salt=bytes(row["password_salt"]),
            expected_digest=bytes(row["password_digest"]),
            iterations=int(row["password_iterations"]),
        ):
            raise CoordinatorAuthenticationError(
                "رمز فعلی درست نیست.",
                code="app_auth_current_password_invalid",
            )
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    UPDATE app_user_credentials
                    SET password_scheme=?,password_iterations=?,password_salt=?,
                        password_digest=?,credential_version=credential_version+1,
                        password_changed_at=?,updated_at=?
                    WHERE app_user_id=?
                    """,
                    (
                        self.password_hasher.scheme,
                        material.iterations,
                        material.salt,
                        material.digest,
                        _as_utc_text(now),
                        _as_utc_text(now),
                        session.principal.app_user_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE app_user_sessions
                    SET status='revoked',revoked_at=?,safe_reason_code='password_changed'
                    WHERE app_user_id=? AND id!=? AND status='active'
                    """,
                    (
                        _as_utc_text(now),
                        session.principal.app_user_id,
                        session.principal.session_id,
                    ),
                )
                self._append_audit(
                    connection,
                    actor_type="app_user",
                    actor_app_user_id=session.principal.app_user_id,
                    actor_global_role=session.principal.global_role,
                    action="app_auth.password.changed",
                    target_id=session.principal.app_user_id,
                    result="succeeded",
                    reason_code="self_service_password_change",
                    request_id=request_id,
                    safe_metadata={"other_sessions_revoked": True},
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise CoordinatorAuthenticationError(
                "رمز ورود تغییر نکرد.",
                safe_context={"error_type": type(exc).__name__},
                code="app_auth_password_change_failed",
            ) from exc

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        finally:
            connection.close()

    def _now(self) -> datetime:
        raw = self.clock()
        if raw.tzinfo is None:
            raise CoordinatorAuthenticationError(
                "The authentication clock is invalid.",
                code="app_auth_clock_invalid",
            )
        return raw.astimezone(timezone.utc)

    def _normalize_login_username(self, value: str) -> str:
        try:
            return normalize_username(value)
        except CoordinatorAuthenticationError:
            return "invalid-login-subject"

    def _dummy_password_material(self) -> PasswordMaterial:
        if self._dummy_material is None:
            self._dummy_material = self.password_hasher.dummy_material()
        return self._dummy_material

    def _insert_credential(
        self,
        connection: sqlite3.Connection,
        app_user_id: str,
        material: PasswordMaterial,
        now: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO app_user_credentials(
                app_user_id,credential_kind,password_scheme,password_iterations,
                password_salt,password_digest,credential_version,password_changed_at,
                created_at,updated_at
            ) VALUES(?,'local_password',?,?,?,?,1,?,?,?)
            """,
            (
                app_user_id,
                self.password_hasher.scheme,
                material.iterations,
                material.salt,
                material.digest,
                _as_utc_text(now),
                _as_utc_text(now),
                _as_utc_text(now),
            ),
        )

    def _issue_session(
        self,
        connection: sqlite3.Connection,
        *,
        app_user_id: str,
        display_name: str,
        global_role: str,
        client_kind: str,
        now: datetime,
    ) -> IssuedAppSession:
        selected_client = self._validate_client_kind(client_kind)
        active = connection.execute(
            """
            SELECT id FROM app_user_sessions
            WHERE app_user_id=? AND status='active'
            ORDER BY created_at DESC,id DESC
            """,
            (app_user_id,),
        ).fetchall()
        for row in active[4:]:
            connection.execute(
                """
                UPDATE app_user_sessions
                SET status='revoked',revoked_at=?,safe_reason_code='session_limit'
                WHERE id=?
                """,
                (_as_utc_text(now), str(row["id"])),
            )
        token = secrets.token_urlsafe(_SESSION_TOKEN_BYTES)
        csrf_token = self._csrf_for_session_token(token)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        csrf_hash = hashlib.sha256(csrf_token.encode("ascii")).hexdigest()
        session_id = str(uuid4())
        idle = now + timedelta(minutes=self.policy.idle_timeout_minutes)
        absolute = now + timedelta(hours=self.policy.absolute_timeout_hours)
        connection.execute(
            """
            INSERT INTO app_user_sessions(
                id,app_user_id,token_hash,csrf_token_hash,status,client_kind,
                created_at,last_seen_at,idle_expires_at,absolute_expires_at
            ) VALUES(?,?,?,?,'active',?,?,?,?,?)
            """,
            (
                session_id,
                app_user_id,
                token_hash,
                csrf_hash,
                selected_client,
                _as_utc_text(now),
                _as_utc_text(now),
                _as_utc_text(idle),
                _as_utc_text(absolute),
            ),
        )
        return IssuedAppSession(
            principal=AppPrincipal(
                app_user_id=app_user_id,
                display_name=display_name,
                global_role=global_role,
                session_id=session_id,
                client_kind=selected_client,
            ),
            token=token,
            csrf_token=csrf_token,
            idle_expires_at=_as_utc_text(idle),
            absolute_expires_at=_as_utc_text(absolute),
        )

    def _csrf_for_session_token(self, token: str) -> str:
        """Derive a session-bound CSRF value without storing its raw form."""
        return self.fingerprinter.fingerprint(f"csrf-token-v1\x00{token}")

    def _is_blocked(
        self,
        connection: sqlite3.Connection,
        fingerprint: str,
        client_fingerprint: str | None,
        now: datetime,
    ) -> bool:
        fingerprints = [fingerprint, _GLOBAL_THROTTLE_FINGERPRINT]
        if client_fingerprint:
            fingerprints.append(client_fingerprint)
        placeholders = ",".join("?" for _ in fingerprints)
        rows = connection.execute(
            f"""
            SELECT blocked_until FROM app_auth_throttles
            WHERE subject_fingerprint IN ({placeholders})
            """,
            tuple(fingerprints),
        ).fetchall()
        return any(
            row["blocked_until"]
            and _parse_utc(str(row["blocked_until"])) > now
            for row in rows
        )

    def _record_failed_login(
        self,
        *,
        fingerprint: str,
        client_fingerprint: str | None,
        app_user_id: str | None,
        client_kind: str,
        request_id: str | None,
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._increment_throttle(
                connection,
                fingerprint,
                threshold=self.policy.max_failed_attempts,
                now=now,
            )
            if client_fingerprint:
                self._increment_throttle(
                    connection,
                    client_fingerprint,
                    threshold=self.policy.max_failed_attempts,
                    now=now,
                )
            self._increment_throttle(
                connection,
                _GLOBAL_THROTTLE_FINGERPRINT,
                threshold=self.policy.max_failed_attempts * 6,
                now=now,
            )
            self._append_audit(
                connection,
                actor_type="system",
                actor_app_user_id=None,
                actor_global_role=None,
                action="app_auth.login.failed",
                target_id=app_user_id,
                result="rejected",
                reason_code="invalid_credentials",
                request_id=request_id,
                safe_metadata={"client_kind": self._validate_client_kind(client_kind)},
            )
            connection.commit()

    def _client_fingerprint(self, client_address: str | None) -> str | None:
        if not client_address:
            return None
        try:
            normalized = ipaddress.ip_address(str(client_address).strip()).compressed
        except ValueError:
            return None
        return self.fingerprinter.fingerprint(f"app-auth-client-v1\x00{normalized}")

    def _audit_throttled_attempt(
        self,
        *,
        fingerprint: str,
        app_user_id: str | None,
        client_kind: str,
        request_id: str | None,
    ) -> None:
        del fingerprint
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._append_audit(
                connection,
                actor_type="system",
                actor_app_user_id=None,
                actor_global_role=None,
                action="app_auth.login.throttled",
                target_id=app_user_id,
                result="rejected",
                reason_code="login_throttle_active",
                request_id=request_id,
                safe_metadata={"client_kind": self._validate_client_kind(client_kind)},
            )
            connection.commit()

    def _increment_throttle(
        self,
        connection: sqlite3.Connection,
        fingerprint: str,
        *,
        threshold: int,
        now: datetime,
    ) -> None:
        row = connection.execute(
            """
            SELECT failure_count,window_started_at FROM app_auth_throttles
            WHERE subject_fingerprint=?
            """,
            (fingerprint,),
        ).fetchone()
        window = timedelta(minutes=self.policy.lockout_minutes)
        if row is None or _parse_utc(str(row["window_started_at"])) + window <= now:
            count = 1
            started = now
        else:
            count = int(row["failure_count"]) + 1
            started = _parse_utc(str(row["window_started_at"]))
        blocked_until = (
            _as_utc_text(now + window) if count >= threshold else None
        )
        connection.execute(
            """
            INSERT INTO app_auth_throttles(
                subject_fingerprint,failure_count,window_started_at,blocked_until,
                last_failed_at,updated_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(subject_fingerprint) DO UPDATE SET
                failure_count=excluded.failure_count,
                window_started_at=excluded.window_started_at,
                blocked_until=excluded.blocked_until,
                last_failed_at=excluded.last_failed_at,
                updated_at=excluded.updated_at
            """,
            (
                fingerprint,
                count,
                _as_utc_text(started),
                blocked_until,
                _as_utc_text(now),
                _as_utc_text(now),
            ),
        )

    def _require_admin(self, actor: AppPrincipal) -> None:
        if actor.global_role != "admin":
            raise CoordinatorAuthorizationError(
                "این عملیات فقط برای مدیر نرم‌افزار مجاز است.",
                code="app_auth_admin_required",
            )
        with self._connect() as connection:
            self._assert_active_admin(connection, actor)

    @staticmethod
    def _assert_active_admin(
        connection: sqlite3.Connection, actor: AppPrincipal
    ) -> None:
        row = connection.execute(
            "SELECT global_role,status FROM app_users WHERE id=?",
            (actor.app_user_id,),
        ).fetchone()
        if (
            row is None
            or str(row["global_role"]) != "admin"
            or str(row["status"]) != "active"
        ):
            raise CoordinatorAuthorizationError(
                "این عملیات فقط برای مدیر نرم‌افزار مجاز است.",
                code="app_auth_admin_required",
            )

    @staticmethod
    def _validate_role(value: str | None) -> str:
        selected = str(value or "")
        if selected not in {"admin", "user"}:
            raise CoordinatorAuthenticationError(
                "نقش کاربر معتبر نیست.",
                code="app_user_role_invalid",
            )
        return selected

    @staticmethod
    def _validate_status(value: str | None) -> str:
        selected = str(value or "")
        if selected not in {"active", "disabled", "archived"}:
            raise CoordinatorAuthenticationError(
                "وضعیت کاربر معتبر نیست.",
                code="app_user_status_invalid",
            )
        return selected

    @staticmethod
    def _validate_client_kind(value: str) -> str:
        selected = str(value or "api").strip().lower()
        if selected not in {"electron", "browser", "api", "test"}:
            return "api"
        return selected

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        *,
        actor_type: str,
        actor_app_user_id: str | None,
        actor_global_role: str | None,
        action: str,
        target_id: str | None,
        result: str,
        reason_code: str,
        request_id: str | None,
        safe_metadata: dict[str, object],
    ) -> None:
        metadata = dict(safe_metadata)
        if request_id:
            metadata["request_id"] = str(request_id)
        CoordinatorDatabase._append_audit(
            connection,
            actor_type=actor_type,
            actor_app_user_id=actor_app_user_id,
            actor_global_role=actor_global_role,
            action=action,
            target_type="app_user",
            target_id=target_id,
            phone_account_id=None,
            messenger_account_id=None,
            provider=None,
            result=result,
            reason_code=reason_code,
            safe_metadata=metadata,
        )


__all__ = [
    "AppAuthPolicy",
    "AppPrincipal",
    "AuthorizedAppSession",
    "CoordinatorAppAuth",
    "IssuedAppSession",
    "PasswordHasher",
    "StaticSubjectFingerprinter",
    "WindowsDpapiSubjectFingerprinter",
    "normalize_username",
    "validate_display_name",
]
