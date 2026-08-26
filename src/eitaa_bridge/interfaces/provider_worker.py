"""Independent provider-worker process entrypoint for the Phase 7 IPC contract."""

from __future__ import annotations

import argparse
from collections import deque
import json
import re
import sys
import time
import uuid

from ..errors import BridgeError, ProviderExtensionError, WorkerIpcError
from ..infrastructure.worker_ipc import (
    IPC_MAX_MESSAGE_BYTES,
    WorkerIpcCodec,
    WorkerIpcSecretFile,
)
from ..providers import default_provider_registry

_METHOD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,3}$")
_MAX_AUTH_FAILURES = 8
_MAX_REPLAY_NONCES = 4096


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Eitaa Bridge provider worker")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--messenger-account-id", required=True)
    parser.add_argument("--secret-file", required=True)
    parser.add_argument("--config")
    return parser


def _write_line(value: str) -> None:
    sys.stdout.write(value + "\n")
    sys.stdout.flush()


def _safe_stderr(code: str) -> None:
    payload = {"ok": False, "error_code": code}
    sys.stderr.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
    sys.stderr.flush()


def _untrusted_context(raw: str) -> tuple[str | None, str, int]:
    """Recover only shape-validated routing fields for a signed error reply."""

    correlation_id: str | None = None
    method = "worker.error"
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            candidate = str(payload.get("correlation_id") or "")
            parsed = uuid.UUID(candidate)
            if parsed.version == 4 and str(parsed) == candidate:
                correlation_id = candidate
            selected_method = str(payload.get("method") or "")
            if _METHOD.fullmatch(selected_method):
                method = selected_method
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    return correlation_id, method, int(time.time() * 1000) + 30_000


def run_worker(
    *,
    provider: str,
    messenger_account_id: str,
    secret_file: str,
    config_file: str | None = None,
) -> int:
    registry = default_provider_registry()
    try:
        registration = registry.registration(provider)
        if not registration.manifest.runtime_enabled or registration.worker_factory is None:
            raise ProviderExtensionError(
                "The provider worker is not configured.",
                code="provider_worker_not_configured",
            )
        if registration.worker_config_required and not config_file:
            raise ProviderExtensionError(
                "The provider worker configuration is required.",
                code=f"{registration.manifest.provider}_worker_config_required",
            )
    except ProviderExtensionError as exc:
        _safe_stderr(exc.code)
        return 2
    try:
        secret = WorkerIpcSecretFile.consume(
            secret_file,
            expected_messenger_account_id=messenger_account_id,
            expected_provider=provider,
        )
    except WorkerIpcError as exc:
        _safe_stderr(exc.code)
        return 2

    codec = WorkerIpcCodec(secret)
    try:
        worker = registry.create_worker(
            provider,
            secret.messenger_account_id,
            str(config_file) if config_file is not None else None,
        )
    except (BridgeError, ProviderExtensionError) as exc:
        _safe_stderr(exc.code)
        return 2
    except Exception:
        _safe_stderr("ipc_worker_internal_error")
        return 3
    seen_nonces: set[str] = set()
    nonce_order: deque[str] = deque()
    authentication_failures = 0
    try:
        while True:
            line = sys.stdin.readline(IPC_MAX_MESSAGE_BYTES + 2)
            if not line:
                break
            raw = line.rstrip("\r\n")
            if not raw:
                continue
            if len(line) > IPC_MAX_MESSAGE_BYTES and not line.endswith(("\n", "\r")):
                while True:
                    remainder = sys.stdin.readline(IPC_MAX_MESSAGE_BYTES + 2)
                    if not remainder or remainder.endswith(("\n", "\r")):
                        break
                _write_line(codec.error_response(code="ipc_message_too_large"))
                continue
            request = None
            try:
                request = codec.decode(raw, expected_kind="request")
                if request.nonce in seen_nonces:
                    raise WorkerIpcError(
                        "The worker IPC request nonce was already used.",
                        code="ipc_replay_detected",
                    )
                seen_nonces.add(request.nonce)
                nonce_order.append(request.nonce)
                if len(nonce_order) > _MAX_REPLAY_NONCES:
                    seen_nonces.discard(nonce_order.popleft())
                result = worker.dispatch(request)
                _write_line(codec.response(request, result.payload))
                if result.stop_requested:
                    return 0
            except BridgeError as exc:
                if exc.code == "ipc_authentication_failed":
                    authentication_failures += 1
                if request is not None:
                    correlation_id = request.correlation_id
                    method = request.method
                else:
                    correlation_id, method, _ = _untrusted_context(raw)
                _write_line(
                    codec.error_response(
                        code=exc.code,
                        correlation_id=correlation_id,
                        method=method,
                    )
                )
                if authentication_failures >= _MAX_AUTH_FAILURES:
                    _safe_stderr("ipc_authentication_failure_limit")
                    return 3
            except Exception:
                if request is not None:
                    _write_line(
                        codec.error_response(
                            code="ipc_worker_internal_error",
                            correlation_id=request.correlation_id,
                            method=request.method,
                        )
                    )
                else:
                    _safe_stderr("ipc_worker_internal_error")
                    return 3
        return 0
    finally:
        worker.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    return run_worker(
        provider=args.provider,
        messenger_account_id=args.messenger_account_id,
        secret_file=args.secret_file,
        config_file=args.config,
    )


if __name__ == "__main__":
    raise SystemExit(main())
