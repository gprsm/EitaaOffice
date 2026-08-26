"""Authenticated, versioned local IPC primitives for provider workers."""

from .protocol import (
    IPC_MAX_MESSAGE_BYTES,
    IPC_PROTOCOL_NAME,
    IPC_PROTOCOL_VERSION,
    IpcEnvelope,
    WorkerIpcCodec,
)
from .error_taxonomy import IPC_ERROR_TAXONOMY, ipc_error_category
from .secret_file import WorkerIpcSecret, WorkerIpcSecretFile

__all__ = [
    "IPC_PROTOCOL_NAME",
    "IPC_PROTOCOL_VERSION",
    "IPC_MAX_MESSAGE_BYTES",
    "IPC_ERROR_TAXONOMY",
    "IpcEnvelope",
    "WorkerIpcCodec",
    "WorkerIpcSecret",
    "WorkerIpcSecretFile",
    "ipc_error_category",
]
