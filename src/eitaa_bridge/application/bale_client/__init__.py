"""Bale Personal Client research framework and the Bale branch modular API."""

from .client import BaleClient
from .models import BaleSession, Peer, PeerType, Message, FileDetails

__all__ = [
    "BaleClient",
    "BaleSession",
    "Peer",
    "PeerType",
    "Message",
    "FileDetails",
    # Bale branch (Phase 1) modular API facade
    "BaleApi",
    "BaleApiError",
    "BaleAuthPending",
    "BaleNotConnected",
]

__version__ = "0.1.0"


def __getattr__(name: str):  # pragma: no cover - trivial lazy import
    if name in {"BaleApi", "BaleApiError", "BaleAuthPending", "BaleNotConnected"}:
        from . import api

        return getattr(api, name)
    raise AttributeError(name)
