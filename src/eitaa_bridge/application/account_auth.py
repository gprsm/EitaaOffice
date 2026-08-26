"""In-memory, account-bound Eitaa authentication challenge metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid


_DEFAULT_CHALLENGE_SECONDS = 300
_MIN_CHALLENGE_SECONDS = 1
_MAX_CHALLENGE_SECONDS = 900


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _challenge_seconds(provider_challenge: Any) -> int:
    selected = getattr(provider_challenge, "timeout_seconds", None)
    if not isinstance(selected, int) or isinstance(selected, bool) or selected <= 0:
        selected = _DEFAULT_CHALLENGE_SECONDS
    return max(_MIN_CHALLENGE_SECONDS, min(_MAX_CHALLENGE_SECONDS, selected))


def _safe_provider_summary(provider_challenge: Any) -> dict[str, object]:
    provider_summary: dict[str, object] = {}
    if provider_challenge is None:
        return provider_summary
    summary_method = getattr(provider_challenge, "safe_summary", None)
    if not callable(summary_method):
        return provider_summary
    raw = summary_method()
    if not isinstance(raw, dict):
        return provider_summary
    for key in (
        "phone",
        "delivery_type",
        "code_length",
        "next_type",
        "timeout_seconds",
    ):
        if key in raw:
            provider_summary[key] = raw[key]
    return provider_summary


@dataclass(slots=True)
class LegacyAuthChallenge:
    """Bind the single-session provider challenge to one opaque local flow."""

    challenge_id: str
    stage: str
    issued_at: datetime
    expires_at: datetime
    provider_challenge: Any = field(default=None, repr=False)

    @classmethod
    def for_code(
        cls,
        *,
        provider_challenge: Any,
        now: datetime | None = None,
    ) -> "LegacyAuthChallenge":
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        return cls(
            challenge_id=str(uuid.uuid4()),
            stage="code",
            issued_at=selected_now,
            expires_at=(
                selected_now
                + timedelta(seconds=_challenge_seconds(provider_challenge))
            ),
            provider_challenge=provider_challenge,
        )

    def for_password(self, *, now: datetime | None = None) -> "LegacyAuthChallenge":
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        return LegacyAuthChallenge(
            challenge_id=self.challenge_id,
            stage="password",
            issued_at=selected_now,
            expires_at=selected_now + timedelta(seconds=_DEFAULT_CHALLENGE_SECONDS),
            provider_challenge=None,
        )

    def is_expired(self, *, now: datetime | None = None) -> bool:
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        return selected_now >= self.expires_at

    def matches(self, *, challenge_id: str, stage: str) -> bool:
        return challenge_id == self.challenge_id and stage == self.stage

    def safe_summary(self) -> dict[str, object]:
        return {
            "challenge_id": self.challenge_id,
            "stage": self.stage,
            "issued_at": self.issued_at.isoformat(timespec="milliseconds"),
            "expires_at": self.expires_at.isoformat(timespec="milliseconds"),
            **_safe_provider_summary(self.provider_challenge),
        }


@dataclass(slots=True)
class AccountAuthChallenge:
    """Bind provider challenge state to one account and session generation."""

    challenge_id: str
    messenger_account_id: str
    session_generation: int
    stage: str
    issued_at: datetime
    expires_at: datetime
    provider_challenge: Any = field(default=None, repr=False)

    @classmethod
    def for_code(
        cls,
        *,
        messenger_account_id: str,
        session_generation: int,
        provider_challenge: Any,
        now: datetime | None = None,
    ) -> "AccountAuthChallenge":
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        seconds = _challenge_seconds(provider_challenge)
        return cls(
            challenge_id=str(uuid.uuid4()),
            messenger_account_id=messenger_account_id,
            session_generation=session_generation,
            stage="code",
            issued_at=selected_now,
            expires_at=selected_now + timedelta(seconds=seconds),
            provider_challenge=provider_challenge,
        )

    def for_password(self, *, now: datetime | None = None) -> "AccountAuthChallenge":
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        return AccountAuthChallenge(
            challenge_id=self.challenge_id,
            messenger_account_id=self.messenger_account_id,
            session_generation=self.session_generation,
            stage="password",
            issued_at=selected_now,
            expires_at=selected_now + timedelta(seconds=_DEFAULT_CHALLENGE_SECONDS),
            provider_challenge=None,
        )

    def is_expired(self, *, now: datetime | None = None) -> bool:
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        return selected_now >= self.expires_at

    def matches(
        self,
        *,
        challenge_id: str,
        messenger_account_id: str,
        session_generation: int,
        stage: str,
    ) -> bool:
        return (
            challenge_id == self.challenge_id
            and messenger_account_id == self.messenger_account_id
            and session_generation == self.session_generation
            and stage == self.stage
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "challenge_id": self.challenge_id,
            "messenger_account_id": self.messenger_account_id,
            "session_generation": self.session_generation,
            "stage": self.stage,
            "issued_at": self.issued_at.isoformat(timespec="milliseconds"),
            "expires_at": self.expires_at.isoformat(timespec="milliseconds"),
            **_safe_provider_summary(self.provider_challenge),
        }
