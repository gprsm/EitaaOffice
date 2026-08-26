"""Offline provider used only for shared contract and isolation tests."""

from .adapter import FakeProviderAdapter
from .slot import fake_extension_registration, fake_provider_manifest

__all__ = [
    "FakeProviderAdapter",
    "fake_extension_registration",
    "fake_provider_manifest",
]
