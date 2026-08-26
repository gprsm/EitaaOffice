"""Stable safe error categories for the worker IPC protocol."""

from __future__ import annotations

from types import MappingProxyType


IPC_ERROR_TAXONOMY = MappingProxyType(
    {
        "bootstrap": frozenset(
            {
                "ipc_identity_invalid",
                "ipc_provider_invalid",
                "ipc_secret_acl_failed",
                "ipc_secret_acl_invalid",
                "ipc_secret_create_failed",
                "ipc_secret_invalid",
                "ipc_secret_ttl_invalid",
                "ipc_secret_unavailable",
                "eitaa_worker_config_required",
                "eitaa_worker_process_feature_disabled",
                "provider_worker_not_configured",
                "provider_not_allowlisted",
                "provider_activation_not_authorized",
                "provider_activation_not_verified",
                "provider_adapter_contract_invalid",
                "provider_adapter_factory_failed",
                "provider_worker_contract_invalid",
                "provider_worker_factory_failed",
            }
        ),
        "authentication": frozenset(
            {
                "ipc_authentication_failed",
                "ipc_authentication_failure_limit",
                "ipc_replay_detected",
            }
        ),
        "contract": frozenset(
            {
                "ipc_deadline_expired",
                "ipc_deadline_invalid",
                "ipc_envelope_invalid",
                "ipc_kind_invalid",
                "ipc_message_too_large",
                "ipc_payload_forbidden",
                "ipc_payload_invalid",
                "ipc_protocol_unsupported",
            }
        ),
        "worker": frozenset(
            {
                "ipc_fake_reference_invalid",
                "ipc_method_not_supported",
                "ipc_request_failed",
                "ipc_worker_internal_error",
                "ipc_worker_scope_mismatch",
                "eitaa_process_generation_refresh_invalid",
                "eitaa_process_fence_mismatch",
                "eitaa_process_identity_invalid",
                "eitaa_process_runtime_already_started",
                "eitaa_process_runtime_not_started",
                "eitaa_process_runtime_record_invalid",
            }
        ),
    }
)


def ipc_error_category(code: str) -> str | None:
    for category, codes in IPC_ERROR_TAXONOMY.items():
        if code in codes:
            return category
    return None
