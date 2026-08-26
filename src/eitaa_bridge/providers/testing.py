"""Offline-only contract harness for provider-extension authors.

This module never performs network I/O. ``InMemoryProviderSessionStore`` is a
test double and must not be used as a production session store.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ProviderExtensionError
from .contracts import (
    ProviderAccountContext,
    ProviderAdapter,
    ProviderManifest,
    ProviderSessionStore,
    SensitiveProviderValue,
)


_FORBIDDEN_PUBLIC_MEMBERS = frozenset(
    {
        "raw_rpc",
        "raw_request",
        "raw_response",
        "request_hex",
        "response_hex",
        "access_token",
        "cookie",
        "session_object",
    }
)


@dataclass(frozen=True, slots=True)
class ProviderContractReport:
    provider: str
    extension_api_version: int
    adapter_shape_valid: bool
    forbidden_public_members: tuple[str, ...]

    def safe_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "extension_api_version": self.extension_api_version,
            "adapter_shape_valid": self.adapter_shape_valid,
            "forbidden_public_members": list(self.forbidden_public_members),
        }


def verify_provider_adapter_contract(
    adapter: object,
    *,
    expected_manifest: ProviderManifest,
) -> ProviderContractReport:
    shape_valid = isinstance(adapter, ProviderAdapter)
    forbidden = tuple(sorted(name for name in _FORBIDDEN_PUBLIC_MEMBERS if hasattr(adapter, name)))
    adapter_manifest = getattr(adapter, "manifest", None)
    if not shape_valid or adapter_manifest != expected_manifest or forbidden:
        raise ProviderExtensionError(
            "The provider adapter failed the offline contract probe.",
            safe_context={
                "provider": expected_manifest.provider,
                "shape_valid": shape_valid,
                "forbidden_member_count": len(forbidden),
            },
            code="provider_adapter_contract_invalid",
        )
    return ProviderContractReport(
        provider=expected_manifest.provider,
        extension_api_version=expected_manifest.extension_api_version,
        adapter_shape_valid=True,
        forbidden_public_members=(),
    )


class InMemoryProviderSessionStore(ProviderSessionStore):
    """Deterministic Fake; deliberately refuses cross-account reads."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str, int], SensitiveProviderValue] = {}

    @staticmethod
    def _key(context: ProviderAccountContext) -> tuple[str, str, int]:
        return (context.provider, context.messenger_account_id, context.session_generation)

    def load(self, context: ProviderAccountContext) -> SensitiveProviderValue | None:
        return self._values.get(self._key(context))

    def save(self, context: ProviderAccountContext, value: SensitiveProviderValue) -> None:
        if not isinstance(value, SensitiveProviderValue):
            raise ProviderExtensionError(
                "The Fake provider session value is invalid.",
                code="provider_sensitive_value_invalid",
            )
        self._values[self._key(context)] = value

    def archive(self, context: ProviderAccountContext, *, reason_code: str) -> None:
        if not reason_code or len(reason_code) > 64:
            raise ProviderExtensionError(
                "The Fake provider archive reason is invalid.",
                code="provider_session_archive_reason_invalid",
            )
        self._values.pop(self._key(context), None)
