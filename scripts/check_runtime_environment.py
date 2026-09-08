from __future__ import annotations

import importlib
import importlib.metadata
import json
import sys
from zoneinfo import ZoneInfo

EXPECTED_DISTRIBUTIONS = {
    "requests": "2.34.2",
    "tzdata": "2026.3",
    "eitaa-core": "0.6.0.dev19",
    "eitaa-bridge": "0.7.0.dev31",
    "cryptography": "46.0.7",
}
EXPECTED_BRIDGE_PRODUCT = "0.7.0-ui-mvp6.1.1-gmi4.2"


def main() -> int:
    failures: list[str] = []
    versions: dict[str, str] = {}
    for distribution, expected in EXPECTED_DISTRIBUTIONS.items():
        try:
            actual = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            actual = "missing"
        versions[distribution] = actual
        if actual != expected:
            failures.append(f"{distribution}: expected {expected}, found {actual}")

    for module_name in ("requests", "tzdata", "cryptography", "eitaa_core", "eitaa_bridge"):
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # safe type-only diagnostic
            failures.append(f"{module_name}: import failed ({type(exc).__name__})")

    try:
        bridge = importlib.import_module("eitaa_bridge")
        product_version = str(getattr(bridge, "__version__", "unknown"))
    except Exception:
        product_version = "unavailable"
    if product_version != EXPECTED_BRIDGE_PRODUCT:
        failures.append(
            f"eitaa_bridge product: expected {EXPECTED_BRIDGE_PRODUCT}, found {product_version}"
        )

    try:
        ZoneInfo("Asia/Tehran")
    except Exception as exc:
        failures.append(f"timezone: Asia/Tehran unavailable ({type(exc).__name__})")

    payload = {
        "ok": not failures,
        "expected_bridge_product": EXPECTED_BRIDGE_PRODUCT,
        "bridge_product": product_version,
        "distributions": versions,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
