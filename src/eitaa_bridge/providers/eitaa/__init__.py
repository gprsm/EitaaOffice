"""Eitaa provider integration behind the public provider contract."""

from .application_adapter import (
    EitaaCompatibilityOperations,
    EitaaProviderApplicationAdapter,
)

__all__ = [
    "EitaaCompatibilityOperations",
    "EitaaProviderApplicationAdapter",
]
