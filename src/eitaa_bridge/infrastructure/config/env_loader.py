from __future__ import annotations

import os
from pathlib import Path

from ...errors import BridgeConfigurationError


class EnvLoader:
    """Small `.env` reader that never logs or returns a full environment dump."""

    @staticmethod
    def load(path: Path, *, override: bool = False) -> set[str]:
        path = Path(path)
        if not path.exists():
            return set()
        loaded: set[str] = set()
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            raise BridgeConfigurationError(
                "Could not read the configured .env file.",
                safe_context={"error_type": type(exc).__name__},
            ) from exc
        for line_number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                raise BridgeConfigurationError(
                    "Invalid .env line; expected KEY=VALUE.",
                    safe_context={"line_number": line_number},
                )
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or not (key[0].isalpha() or key[0] == "_") or not all(
                character.isalnum() or character == "_" for character in key
            ):
                raise BridgeConfigurationError(
                    "Invalid .env variable name.",
                    safe_context={"line_number": line_number},
                )
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if override or key not in os.environ:
                os.environ[key] = value
            loaded.add(key)
        return loaded
