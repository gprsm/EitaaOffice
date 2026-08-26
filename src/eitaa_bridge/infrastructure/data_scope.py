"""Canonical provider/account scope for Bridge-owned data repositories."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from uuid import UUID

from ..errors import BridgeError


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_LEGACY_ACCOUNT = "legacy"


class DataScopeError(BridgeError):
    component = "data_scope"
    default_code = "data_scope_invalid"


@dataclass(frozen=True, slots=True)
class ProviderAccountScope:
    """A non-secret logical owner for every provider-derived data key.

    ``legacy`` is deliberately explicit instead of being represented by an
    empty value.  Multi-session callers must use :meth:`for_account`.
    """

    provider: str
    messenger_account_id: str

    def __post_init__(self) -> None:
        provider = str(self.provider or "").strip().lower()
        account_id = str(self.messenger_account_id or "").strip().lower()
        if not _PROVIDER_ID.fullmatch(provider):
            raise DataScopeError(
                "The provider data scope is invalid.",
                code="data_scope_provider_invalid",
            )
        if account_id != _LEGACY_ACCOUNT:
            try:
                parsed = UUID(account_id)
            except (ValueError, AttributeError) as exc:
                raise DataScopeError(
                    "The MessengerAccount data scope is invalid.",
                    code="data_scope_account_invalid",
                ) from exc
            if str(parsed) != account_id:
                raise DataScopeError(
                    "The MessengerAccount data scope is not canonical.",
                    code="data_scope_account_invalid",
                )
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "messenger_account_id", account_id)

    @classmethod
    def legacy(cls, provider: str = "eitaa") -> "ProviderAccountScope":
        return cls(provider=provider, messenger_account_id=_LEGACY_ACCOUNT)

    @classmethod
    def for_account(
        cls,
        messenger_account_id: str,
        *,
        provider: str = "eitaa",
    ) -> "ProviderAccountScope":
        if str(messenger_account_id or "").strip().lower() == _LEGACY_ACCOUNT:
            raise DataScopeError(
                "A multi-session data scope requires a MessengerAccount UUID.",
                code="data_scope_account_required",
            )
        return cls(provider=provider, messenger_account_id=messenger_account_id)

    @property
    def is_legacy(self) -> bool:
        return self.messenger_account_id == _LEGACY_ACCOUNT

    @property
    def scope_key(self) -> str:
        return f"{self.provider}:{self.messenger_account_id}"

    def key(self, namespace: str, *parts: object) -> str:
        selected_namespace = str(namespace or "").strip().lower()
        if not selected_namespace or ":" in selected_namespace:
            raise DataScopeError(
                "The repository key namespace is invalid.",
                code="data_scope_namespace_invalid",
            )
        suffix = ":".join(str(part) for part in parts)
        return f"{self.scope_key}:{selected_namespace}:{suffix}"

    def prefix(self, namespace: str) -> str:
        return self.key(namespace, "")

    def strip(self, namespace: str, value: str) -> str:
        prefix = self.prefix(namespace)
        if not str(value).startswith(prefix):
            raise DataScopeError(
                "A repository key belongs to a different account scope.",
                code="data_scope_key_mismatch",
            )
        return str(value)[len(prefix):]

    def matches(self, payload: Any) -> bool:
        return bool(
            isinstance(payload, dict)
            and payload.get("provider") == self.provider
            and payload.get("messenger_account_id") == self.messenger_account_id
        )

    def safe_summary(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "messenger_account_id": self.messenger_account_id,
        }

