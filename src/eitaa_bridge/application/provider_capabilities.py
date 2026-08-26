"""Account-scoped capability decisions for every registered provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ProviderExtensionError
from ..infrastructure.coordinator import CoordinatorDatabase
from ..providers.contracts import ProviderCapability, ProviderRegistry


@dataclass(frozen=True, slots=True)
class ProviderCapabilityDecision:
    capability: str
    status: str
    reason_code: str
    constraints_present: bool = False
    revision: int = 0

    def safe_summary(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "status": self.status,
            "reason_code": self.reason_code,
            "constraints_present": self.constraints_present,
            "revision": self.revision,
        }


@dataclass(frozen=True, slots=True)
class ProviderCapabilitySnapshot:
    messenger_account_id: str
    provider: str
    implementation_state: str
    runtime_enabled: bool
    capabilities: tuple[ProviderCapabilityDecision, ...]

    def safe_summary(self) -> dict[str, object]:
        return {
            "messenger_account_id": self.messenger_account_id,
            "provider": self.provider,
            "implementation_state": self.implementation_state,
            "runtime_enabled": self.runtime_enabled,
            "capabilities": [item.safe_summary() for item in self.capabilities],
        }

    def decision(self, capability: ProviderCapability) -> ProviderCapabilityDecision:
        selected = ProviderCapability(capability).value
        for item in self.capabilities:
            if item.capability == selected:
                return item
        raise ProviderExtensionError(
            "The provider capability is unknown.",
            safe_context={"capability": selected},
            code="provider_capability_unknown",
        )


class ProviderCapabilityService:
    """Merge immutable manifest declarations with safe account observations."""

    def __init__(self, coordinator: CoordinatorDatabase, registry: ProviderRegistry) -> None:
        self._coordinator = coordinator
        self._registry = registry

    def snapshot(self, messenger_account_id: str) -> ProviderCapabilitySnapshot:
        runtime = self._coordinator.messenger_account_runtime(messenger_account_id)
        registration = self._coordinator.provider_registration(runtime.provider)
        manifest = self._registry.registration(runtime.provider).manifest
        if registration.status != "active" or registration.provider != manifest.provider:
            raise ProviderExtensionError(
                "The provider registration is unavailable.",
                safe_context={"provider": runtime.provider},
                code="provider_registration_unavailable",
            )
        persisted = frozenset(registration.capabilities)
        declared = frozenset(item.value for item in manifest.capabilities)
        if persisted != declared:
            raise ProviderExtensionError(
                "The provider capability contract is not reconciled.",
                safe_context={"provider": runtime.provider},
                code="provider_capability_contract_stale",
            )
        observations = self._coordinator.messenger_capability_observations(
            messenger_account_id
        )
        decisions: list[ProviderCapabilityDecision] = []
        for capability in sorted(ProviderCapability, key=lambda item: item.value):
            name = capability.value
            observed: dict[str, Any] | None = observations.get(name)
            if name not in declared:
                decisions.append(
                    ProviderCapabilityDecision(
                        capability=name,
                        status="unsupported",
                        reason_code="provider_manifest_not_declared",
                    )
                )
            elif observed is None:
                decisions.append(
                    ProviderCapabilityDecision(
                        capability=name,
                        status="supported",
                        reason_code="provider_manifest_declared",
                    )
                )
            else:
                decisions.append(
                    ProviderCapabilityDecision(
                        capability=name,
                        status=str(observed["status"]),
                        reason_code=str(
                            observed.get("reason_code")
                            or f"provider_observed_{observed['status']}"
                        ),
                        constraints_present=bool(observed["constraints_present"]),
                        revision=int(observed["revision"]),
                    )
                )
        return ProviderCapabilitySnapshot(
            messenger_account_id=runtime.messenger_account_id,
            provider=runtime.provider,
            implementation_state=registration.implementation_state,
            runtime_enabled=registration.runtime_enabled,
            capabilities=tuple(decisions),
        )

    def require(
        self,
        messenger_account_id: str,
        capability: ProviderCapability,
    ) -> ProviderCapabilityDecision:
        snapshot = self.snapshot(messenger_account_id)
        selected = snapshot.decision(capability)
        if not snapshot.runtime_enabled:
            raise ProviderExtensionError(
                "The provider runtime is disabled.",
                safe_context={
                    "provider": snapshot.provider,
                    "capability": selected.capability,
                },
                code="provider_runtime_disabled",
            )
        if selected.status != "supported":
            raise ProviderExtensionError(
                "The selected provider account cannot perform this operation.",
                safe_context={
                    "provider": snapshot.provider,
                    "capability": selected.capability,
                    "capability_status": selected.status,
                    "reason_code": selected.reason_code,
                },
                code="provider_capability_unavailable",
            )
        return selected


def provider_capability_for_route(method: str, path: str) -> ProviderCapability | None:
    """Map provider-backed v1 compatibility routes onto the generic contract."""

    selected_method = str(method).upper().strip()
    selected_path = str(path)
    if selected_path.startswith("/api/v1/dialogs"):
        if "/avatar" in selected_path:
            return ProviderCapability.MEDIA_READ
        return ProviderCapability.DIALOGS_READ
    if selected_path.startswith("/api/v1/messages"):
        if selected_method == "POST" and selected_path.endswith("/send"):
            return ProviderCapability.MESSAGES_SEND
        if "media-preview" in selected_path:
            return ProviderCapability.MEDIA_READ
        return ProviderCapability.HISTORY_READ
    if selected_path.startswith("/api/v1/eitaa-contacts"):
        return (
            ProviderCapability.CONTACTS_READ
            if selected_path.endswith("/list")
            else ProviderCapability.CONTACTS_WRITE
        )
    if selected_path == "/api/v1/contacts/add-to-messenger/start":
        return ProviderCapability.CONTACTS_WRITE
    return None


__all__ = [
    "ProviderCapabilityDecision",
    "ProviderCapabilityService",
    "ProviderCapabilitySnapshot",
    "provider_capability_for_route",
]
