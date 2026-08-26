"""Compatibility facade for the versioned provider extension SDK."""

from __future__ import annotations

from ..providers.contracts import (
    ProviderAccountContext,
    ProviderAdapterDescriptor,
    ProviderWorkerAdapter,
    ProviderWorkerDispatchResult,
)
from ..providers.registry import default_provider_registry


def provider_adapter_catalog() -> dict[str, ProviderAdapterDescriptor]:
    return default_provider_registry().descriptor_catalog()


__all__ = [
    "ProviderAccountContext",
    "ProviderAdapterDescriptor",
    "ProviderWorkerAdapter",
    "ProviderWorkerDispatchResult",
    "provider_adapter_catalog",
]
