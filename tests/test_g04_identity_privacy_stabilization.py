from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from eitaa_bridge.errors import CoordinatorIdentityError
from eitaa_bridge.infrastructure.coordinator.identity import (
    masked_phone,
    validate_canonical_e164,
)
from eitaa_bridge.infrastructure.diagnostics.redaction import redact


SYNTHETIC_E164 = "+999123456789"
LEGACY_PLACEHOLDER_TESTS = {
    "test_bootstrap_rejects_display_hint_with_too_many_digits",
    "test_phone_mask_never_contains_the_full_number",
}
REPLACEMENT_CONTRACT_TESTS = {
    "test_bootstrap_accepts_full_canonical_display_hint",
    "test_product_phone_display_preserves_full_canonical_e164",
}


def test_g04_legacy_phone_contract_tests_are_not_placeholders():
    test_path = Path(__file__).with_name("test_coordinator_schema.py")
    module = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    missing_or_empty_replacements = {
        name
        for name in REPLACEMENT_CONTRACT_TESTS
        if name not in functions
        or (
            len(functions[name].body) == 1
            and isinstance(functions[name].body[0], ast.Pass)
        )
    }
    legacy_contracts_present = LEGACY_PLACEHOLDER_TESTS.intersection(functions)
    if missing_or_empty_replacements or legacy_contracts_present:
        pytest.fail(
            "The legacy placeholders were not fully replaced by current phone-contract tests.",
            pytrace=False,
        )


def test_g04_full_canonical_phone_is_allowed_at_product_display_boundary():
    if masked_phone(SYNTHETIC_E164) != SYNTHETIC_E164:
        pytest.fail(
            "The allowed product display boundary did not preserve canonical E.164.",
            pytrace=False,
        )


def test_g04_runtime_redaction_blocks_full_phone_for_identity_hint_keys():
    redacted = redact(
        {
            "phone_hint": SYNTHETIC_E164,
            "display_hint": SYNTHETIC_E164,
        }
    )
    encoded = json.dumps(redacted, ensure_ascii=False, sort_keys=True)
    if SYNTHETIC_E164 in encoded:
        pytest.fail(
            "Runtime redaction retained a full synthetic phone under an identity-hint key.",
            pytrace=False,
        )


def test_g04_phone_validator_rejects_token_shaped_identity():
    synthetic_token_shape = "7" * 6 + ":" + "x" * 24
    with pytest.raises(CoordinatorIdentityError):
        validate_canonical_e164(synthetic_token_shape)
