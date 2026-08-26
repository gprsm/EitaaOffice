from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from eitaa_core import load_peer_file

from ..domain import CompositionSource, WordPressCompositionRequest
from ..errors import CompositionValidationError


class CompositionManifestLoader:
    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        default_site_key: str,
        site_key_override: str | None = None,
    ) -> WordPressCompositionRequest:
        source = Path(path).expanduser().resolve()
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as exc:
            raise CompositionValidationError(
                "Composition file was not found.",
                safe_context={"file_name": source.name},
                code="composition_file_not_found",
            ) from exc
        except json.JSONDecodeError as exc:
            raise CompositionValidationError(
                "Composition file is not valid JSON.",
                safe_context={"line": exc.lineno, "column": exc.colno},
                code="composition_json_error",
            ) from exc
        except OSError as exc:
            raise CompositionValidationError(
                "Composition file could not be read.",
                safe_context={"file_name": source.name, "error_type": type(exc).__name__},
                code="composition_file_error",
            ) from exc
        if not isinstance(payload, dict):
            raise CompositionValidationError("Composition JSON root must be an object.")
        return cls.from_mapping(
            payload,
            base_directory=source.parent,
            default_site_key=default_site_key,
            site_key_override=site_key_override,
        )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        base_directory: str | Path,
        default_site_key: str,
        site_key_override: str | None = None,
    ) -> WordPressCompositionRequest:
        """Build the same validated request used by CLI manifests and the local API."""
        base = Path(base_directory).expanduser().resolve()
        try:
            raw_sources = payload["sources"]
            if not isinstance(raw_sources, list):
                raise TypeError("sources")
            sources: list[CompositionSource] = []
            for index, raw in enumerate(raw_sources):
                if not isinstance(raw, Mapping):
                    raise TypeError(f"sources[{index}]")
                peer_value = raw.get("peer_file")
                if not isinstance(peer_value, str) or not peer_value.strip():
                    raise TypeError(f"sources[{index}].peer_file")
                peer_path = Path(peer_value).expanduser()
                if not peer_path.is_absolute():
                    peer_path = (base / peer_path).resolve()
                peer = load_peer_file(peer_path)
                message_id = int(raw["message_id"])
                sources.append(CompositionSource(peer=peer, message_id=message_id, peer_file=peer_path))
            categories = cls._ids(payload.get("category_ids", []), "category_ids")
            tags = cls._ids(payload.get("tag_ids", []), "tag_ids")
            featured = payload.get("featured_source_index")
            post_status = str(payload.get("post_status") or "draft").strip().lower()
            request = WordPressCompositionRequest(
                composition_key=str(payload["composition_key"]).strip(),
                site_key=(site_key_override or str(payload.get("site_key") or default_site_key)).strip(),
                title=str(payload["title"]),
                excerpt=str(payload.get("excerpt") or ""),
                sources=tuple(sources),
                category_ids=categories,
                tag_ids=tags,
                featured_source_index=int(featured) if featured is not None else None,
                include_featured_in_body=bool(payload.get("include_featured_in_body", True)),
                post_status=post_status,
                confirm_publish=bool(payload.get("confirm_publish", False)),
            )
            request.validate()
            return request
        except CompositionValidationError:
            raise
        except ValueError as exc:
            message = str(exc) or "Composition contains an invalid value."
            code = (
                "composition_publish_confirmation_required"
                if "confirm_publish" in message
                else "composition_invalid_fields"
            )
            raise CompositionValidationError(message, code=code) from exc
        except Exception as exc:
            raise CompositionValidationError(
                "Composition contains invalid fields.",
                safe_context={"error_type": type(exc).__name__},
                code="composition_invalid_fields",
            ) from exc

    @staticmethod
    def _ids(value: Any, field_name: str) -> tuple[int, ...]:
        if not isinstance(value, list):
            raise CompositionValidationError(f"{field_name} must be an array.")
        try:
            return tuple(int(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise CompositionValidationError(f"{field_name} must contain integer ids.") from exc
