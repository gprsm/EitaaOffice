from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from eitaa_core import load_peer_file

from ..errors import BridgeError, PublicationWorkflowError
from ..facade import EitaaBridge
from ..infrastructure.composition_manifest import CompositionManifestLoader
from ..infrastructure.config import BridgeConfigLoader, EnvLoader
from ..version import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eitaa-bridge",
        description=f"Eitaa Bridge {__version__}",
    )
    parser.add_argument("--config", default="bridge.json", help="Path to non-secret Bridge JSON configuration")
    parser.add_argument("--env-file", default=None, help="Optional .env path")
    parser.add_argument("--site-key", default=None, help="WordPress site_key selected for this operation")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Run safe local checks")
    doctor.add_argument("--online", action="store_true", help="Also test the selected WordPress REST API")
    doctor.add_argument("--skip-core-open", action="store_true", help="Check Core package contract without opening session/database")

    sites = sub.add_parser("sites", help="Inspect configured WordPress destinations")
    sites_sub = sites.add_subparsers(dest="sites_command", required=True)
    sites_sub.add_parser("list", help="List configured sites without exposing credentials")

    wp = sub.add_parser("wp", help="WordPress operations on one selected site")
    wp_sub = wp.add_subparsers(dest="wp_command", required=True)
    wp_sub.add_parser("test", help="Test the selected WordPress site and authenticated user")
    wp_sub.add_parser("info", help="Read public information for the selected WordPress site")
    categories = wp_sub.add_parser("categories", help="List selectable WordPress categories")
    categories.add_argument("--search")
    categories.add_argument("--per-page", type=int, default=100)
    tags = wp_sub.add_parser("tags", help="List selectable WordPress tags/keywords")
    tags.add_argument("--search")
    tags.add_argument("--per-page", type=int, default=100)

    draft = wp_sub.add_parser("draft", help="Create a text draft, optionally with an existing featured media ID")
    draft.add_argument("--title", required=True)
    content = draft.add_mutually_exclusive_group(required=True)
    content.add_argument("--content")
    content.add_argument("--content-file")
    draft.add_argument("--excerpt")
    draft.add_argument("--slug")
    draft.add_argument("--category-id", type=int)
    draft.add_argument("--featured-media-id", type=int)

    media = wp_sub.add_parser("media", help="Upload or inspect WordPress Media Library items")
    media_sub = media.add_subparsers(dest="media_command", required=True)
    upload = media_sub.add_parser("upload", help="Upload one local file without automatic write retry")
    upload.add_argument("--file", required=True)
    upload.add_argument("--mime-type")
    upload.add_argument("--title")
    upload.add_argument("--caption")
    upload.add_argument("--description")
    upload.add_argument("--alt-text")
    upload.add_argument("--parent-post-id", type=int)
    media_info = media_sub.add_parser("info", help="Read one Media Library item")
    media_info.add_argument("--media-id", required=True, type=int)

    publication = sub.add_parser(
        "publication",
        help="Controlled publication of one locally stored Eitaa message",
    )
    publication_sub = publication.add_subparsers(
        dest="publication_command", required=True
    )

    def add_publication_identity(command: argparse.ArgumentParser) -> None:
        command.add_argument("--peer-file", required=True)
        command.add_argument("--message-id", required=True, type=int)
        command.add_argument("--title")
        command.add_argument("--category-id", type=int)
        command.add_argument(
            "--no-media", action="store_true",
            help="Publish only the stored message text",
        )

    publication_preview = publication_sub.add_parser(
        "preview", help="Build a deterministic plan without WordPress writes or Core state changes"
    )
    add_publication_identity(publication_preview)

    publication_status = publication_sub.add_parser(
        "status", help="Read the current Core publication state"
    )
    add_publication_identity(publication_status)

    publication_run = publication_sub.add_parser(
        "run", help="Create or safely reconcile one WordPress Draft"
    )
    add_publication_identity(publication_run)
    publication_run.add_argument("--max-media-mb", type=int, default=100)
    publication_run.add_argument("--retry-skipped", action="store_true")

    publication_update_preview = publication_sub.add_parser(
        "update-preview",
        help="Inspect an existing WordPress publication without any external write",
    )
    add_publication_identity(publication_update_preview)
    publication_update_preview.add_argument(
        "--allow-live-update", action="store_true",
        help="Preview an update to a non-Draft live post as explicitly allowed",
    )
    publication_update_preview.add_argument(
        "--restore-trashed", action="store_true",
        help="Preview restoring the same trashed WordPress post as a Draft",
    )

    publication_update = publication_sub.add_parser(
        "update",
        help="Update exactly one recorded WordPress post without creating a replacement",
    )
    add_publication_identity(publication_update)
    publication_update.add_argument("--max-media-mb", type=int, default=100)
    publication_update.add_argument(
        "--allow-live-update", action="store_true",
        help="Explicitly allow modifying a WordPress post whose status is not draft",
    )
    publication_update.add_argument(
        "--overwrite-remote-drift", action="store_true",
        help="Replace reviewed remote edits even when the Core message hash is unchanged",
    )
    publication_update.add_argument(
        "--restore-trashed", action="store_true",
        help="Restore the same trashed WordPress post as a Draft and update it",
    )

    composer = sub.add_parser(
        "composer", help="Create one WordPress Draft from multiple selected Eitaa messages"
    )
    composer_sub = composer.add_subparsers(dest="composer_command", required=True)
    for name, help_text in (
        ("preview", "Validate a composition without downloads or WordPress writes"),
        ("status", "Read local and WordPress state for one composition"),
        ("publish", "Create or safely reconcile one multi-message Draft"),
    ):
        command = composer_sub.add_parser(name, help=help_text)
        command.add_argument("--file", required=True, help="Composition JSON file")
        if name == "publish":
            command.add_argument("--max-media-mb", type=int, default=100)

    usage = sub.add_parser("usage", help="Inspect whether one Eitaa message was already used")
    usage_sub = usage.add_subparsers(dest="usage_command", required=True)
    usage_message = usage_sub.add_parser("message", help="Read WordPress usage for one stored message")
    usage_message.add_argument("--peer-file", required=True)
    usage_message.add_argument("--message-id", required=True, type=int)
    return parser


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _load_peer(path: str):
    try:
        return load_peer_file(path)
    except Exception as exc:
        raise PublicationWorkflowError(
            "The peer file could not be loaded through the public Core helper.",
            safe_context={
                "file_suffix": Path(path).suffix.lower(),
                "error_type": type(exc).__name__,
            },
            code="peer_file_error",
        ) from exc


def _sites_list(config_path: str, env_file: str | None) -> dict[str, object]:
    config = BridgeConfigLoader.load(config_path, env_file=env_file)
    EnvLoader.load(config.env_file)
    sites: list[dict[str, object]] = []
    for site in config.wordpress_sites:
        credentials_configured = bool(
            os.getenv(site.username_env, "").strip()
            and os.getenv(site.application_password_env, "").strip()
        )
        sites.append(
            site.safe_summary(
                is_default=site.site_key == config.default_site_key,
                credentials_configured=credentials_configured,
            )
        )
    return {
        "default_site_key": config.default_site_key,
        "site_count": len(sites),
        "sites": sites,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "sites" and args.sites_command == "list":
            _print(_sites_list(args.config, args.env_file))
            return 0

        if args.command == "doctor":
            report = EitaaBridge.doctor_from_file(
                args.config,
                env_file=args.env_file,
                site_key=args.site_key,
                online=args.online,
                open_core=not args.skip_core_open,
            )
            _print(report.safe_summary())
            return 0 if report.ok else 1

        composition_request = None
        selected_site_key = args.site_key
        if args.command == "composer":
            loaded_config = BridgeConfigLoader.load(args.config, env_file=args.env_file)
            composition_request = CompositionManifestLoader.load(
                args.file,
                default_site_key=loaded_config.default_site_key,
                site_key_override=args.site_key,
            )
            selected_site_key = composition_request.site_key

        with EitaaBridge.open(
            args.config,
            env_file=args.env_file,
            site_key=selected_site_key,
            open_core=False,
        ) as bridge:
            if args.command == "wp":
                if args.wp_command == "test":
                    _print(bridge.test_wordpress().safe_summary())
                    return 0
                if args.wp_command == "info":
                    _print(bridge.wordpress_site_info().safe_summary())
                    return 0
                if args.wp_command == "categories":
                    terms = bridge.wordpress_categories(search=args.search, per_page=args.per_page)
                    _print({"taxonomy": "category", "count": len(terms), "terms": [item.safe_summary() for item in terms]})
                    return 0
                if args.wp_command == "tags":
                    terms = bridge.wordpress_tags(search=args.search, per_page=args.per_page)
                    _print({"taxonomy": "post_tag", "count": len(terms), "terms": [item.safe_summary() for item in terms]})
                    return 0
                if args.wp_command == "draft":
                    if args.content_file:
                        content = Path(args.content_file).read_text(encoding="utf-8-sig")
                    else:
                        content = args.content
                    post = bridge.create_text_draft(
                        title=args.title,
                        content=content,
                        excerpt=args.excerpt,
                        slug=args.slug,
                        category_id=args.category_id,
                        featured_media_id=args.featured_media_id,
                    )
                    _print(post.safe_summary())
                    return 0
                if args.wp_command == "media":
                    if args.media_command == "upload":
                        result = bridge.upload_wordpress_media(
                            args.file,
                            mime_type=args.mime_type,
                            title=args.title,
                            caption=args.caption,
                            description=args.description,
                            alt_text=args.alt_text,
                            parent_post_id=args.parent_post_id,
                        )
                        _print(result.safe_summary())
                        return 0
                    if args.media_command == "info":
                        _print(bridge.wordpress_media(args.media_id).safe_summary())
                        return 0

            if args.command == "composer":
                assert composition_request is not None
                if args.composer_command == "preview":
                    result = bridge.preview_wordpress_composition(composition_request)
                elif args.composer_command == "status":
                    result = bridge.wordpress_composition_status(composition_request)
                else:
                    if args.max_media_mb <= 0:
                        raise PublicationWorkflowError(
                            "max-media-mb must be positive.", code="composition_invalid_limit"
                        )
                    result = bridge.publish_wordpress_composition(
                        composition_request, max_media_bytes=args.max_media_mb * 1024 * 1024
                    )
                _print(result.safe_summary())
                return 0

            if args.command == "usage":
                peer = _load_peer(args.peer_file)
                _print(bridge.wordpress_message_usage(peer, args.message_id))
                return 0

            if args.command == "publication":
                peer = _load_peer(args.peer_file)
                common = {
                    "title": args.title,
                    "category_id": args.category_id,
                    "include_media": not args.no_media,
                }
                if args.publication_command == "preview":
                    result = bridge.preview_wordpress_publication(
                        peer, args.message_id, **common
                    )
                    _print(result.safe_summary())
                    return 0
                if args.publication_command == "status":
                    result = bridge.wordpress_publication_status(
                        peer, args.message_id, **common
                    )
                    _print(result.safe_summary())
                    return 0
                if args.publication_command == "run":
                    if args.max_media_mb <= 0:
                        raise PublicationWorkflowError(
                            "max-media-mb must be positive.",
                            code="publication_invalid_limit",
                        )
                    result = bridge.publish_stored_message(
                        peer,
                        args.message_id,
                        max_media_bytes=args.max_media_mb * 1024 * 1024,
                        retry_skipped=args.retry_skipped,
                        **common,
                    )
                    _print(result.safe_summary())
                    return 0
                if args.publication_command == "update-preview":
                    result = bridge.preview_wordpress_publication_update(
                        peer,
                        args.message_id,
                        allow_live_update=args.allow_live_update,
                        restore_trashed=args.restore_trashed,
                        **common,
                    )
                    _print(result.safe_summary())
                    return 0
                if args.publication_command == "update":
                    if args.max_media_mb <= 0:
                        raise PublicationWorkflowError(
                            "max-media-mb must be positive.",
                            code="publication_invalid_limit",
                        )
                    result = bridge.update_wordpress_publication(
                        peer,
                        args.message_id,
                        max_media_bytes=args.max_media_mb * 1024 * 1024,
                        allow_live_update=args.allow_live_update,
                        overwrite_remote_drift=args.overwrite_remote_drift,
                        restore_trashed=args.restore_trashed,
                        **common,
                    )
                    _print(result.safe_summary())
                    return 0
        return 2
    except BridgeError as exc:
        _print({
            "ok": False,
            "error_code": exc.code,
            "component": exc.component,
            "safe_context": exc.safe_context,
            "debug_file": exc.debug_file,
        })
        return 1
    except (OSError, UnicodeError) as exc:
        _print({"ok": False, "error_code": "local_file_error", "error_type": type(exc).__name__})
        return 1
    except Exception as exc:
        _print({"ok": False, "error_code": "unexpected_error", "error_type": type(exc).__name__})
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
