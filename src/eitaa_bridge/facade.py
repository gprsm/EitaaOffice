from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
import threading
from typing import Any, ClassVar

from eitaa_core import MessageSearchQuery, Peer

from .application import BridgeDoctor, WordPressService
from .application.workflows import (
    ComposeMessagesToWordPress,
    CreateTextDraft,
    PublishStoredMessageToWordPress,
    UploadWordPressMedia,
)
from .config import BridgeConfig, CoreDependencyConfig
from .errors import CompositionValidationError
from .domain import (
    DoctorReport,
    WordPressCompositionRequest,
    WordPressCompositionResult,
    WordPressConnection,
    WordPressMedia,
    WordPressPost,
    WordPressPublicationResult,
    WordPressSiteInfo,
    WordPressTerm,
)
from .infrastructure.config import BridgeConfigLoader, EnvLoader
from .infrastructure.composition_store import JsonCompositionStore
from .infrastructure.data_scope import ProviderAccountScope
from .infrastructure.diagnostics import BridgeDiagnosticManager
from .infrastructure.eitaa import CoreBinding, CoreCompatibility
from .infrastructure.wordpress import WordPressClient, load_wordpress_credentials
from .version import __version__


@dataclass(slots=True)
class EitaaBridge:
    config: BridgeConfig
    diagnostics: BridgeDiagnosticManager
    site_key: str
    data_scope: ProviderAccountScope
    actor_app_user_id: str | None
    wordpress: WordPressService
    create_text_draft_workflow: CreateTextDraft
    upload_media_workflow: UploadWordPressMedia
    publish_message_workflow: PublishStoredMessageToWordPress
    compose_messages_workflow: ComposeMessagesToWordPress
    core_binding: CoreBinding
    _wordpress_client: WordPressClient
    _core: Any | None = None
    _owns_core: bool = True

    _shared_core_lock: ClassVar[threading.RLock] = threading.RLock()
    _shared_cores: ClassVar[dict[tuple[str, str, str], Any]] = {}

    @classmethod
    def open(
        cls,
        config_path: str | Path = "bridge.json",
        *,
        env_file: str | Path | None = None,
        site_key: str | None = None,
        open_core: bool = False,
        wordpress_session: Any | None = None,
        diagnostics: BridgeDiagnosticManager | None = None,
        reuse_core: bool = False,
        core_config_override: CoreDependencyConfig | None = None,
        data_scope: ProviderAccountScope | None = None,
        actor_app_user_id: str | None = None,
    ) -> "EitaaBridge":
        config = BridgeConfigLoader.load(config_path, env_file=env_file)
        if core_config_override is not None:
            core_config_override.validate()
            config = replace(config, core=core_config_override)
        EnvLoader.load(config.env_file)
        diagnostics = diagnostics or BridgeDiagnosticManager(config.diagnostics.root, enabled=config.diagnostics.enabled)
        selected_scope = data_scope or ProviderAccountScope.legacy()
        site = config.site(site_key)
        # Core/Eitaa operations must remain usable before WordPress is configured.
        # Authenticated WordPress calls validate these credentials lazily in the
        # client, immediately before any network request is made.
        credentials = load_wordpress_credentials(site, required=False)
        wp_client = WordPressClient(site, credentials, diagnostics=diagnostics, session=wordpress_session)
        wp_service = WordPressService(wp_client)
        binding = CoreBinding(config.core, diagnostics)
        binding.assert_compatible()
        core = None
        owns_core = True
        if open_core and reuse_core:
            key = cls._shared_core_key(config)
            with cls._shared_core_lock:
                core = cls._shared_cores.get(key)
                if core is None:
                    core = binding.open()
                    cls._shared_cores[key] = core
            owns_core = False
        elif open_core:
            core = binding.open()
        diagnostics.emit(
            "bridge",
            "bridge_opened",
            fields={
                "version": __version__,
                "site_key": site.site_key,
                "core_opened": core is not None,
                "wordpress_credentials": credentials.safe_summary(),
                "data_scope": selected_scope.safe_summary(),
                "actor_app_user_id": actor_app_user_id,
            },
        )
        composition_store = JsonCompositionStore(
            config.composition_state_file,
            scope=selected_scope,
            owner_app_user_id=actor_app_user_id,
        )
        return cls(
            config=config,
            diagnostics=diagnostics,
            site_key=site.site_key,
            data_scope=selected_scope,
            actor_app_user_id=actor_app_user_id,
            wordpress=wp_service,
            create_text_draft_workflow=CreateTextDraft(wp_service),
            upload_media_workflow=UploadWordPressMedia(wp_service),
            publish_message_workflow=PublishStoredMessageToWordPress(
                wp_service, diagnostics, config.core.media_directory
            ),
            compose_messages_workflow=ComposeMessagesToWordPress(
                wp_service, diagnostics, config.core.media_directory, composition_store
            ),
            core_binding=binding,
            _wordpress_client=wp_client,
            _core=core,
            _owns_core=owns_core,
        )

    @classmethod
    def doctor_from_file(
        cls,
        config_path: str | Path = "bridge.json",
        *,
        env_file: str | Path | None = None,
        site_key: str | None = None,
        online: bool = False,
        open_core: bool = True,
    ) -> DoctorReport:
        config = BridgeConfigLoader.load(config_path, env_file=env_file)
        EnvLoader.load(config.env_file)
        diagnostics = BridgeDiagnosticManager(config.diagnostics.root, enabled=config.diagnostics.enabled)
        return BridgeDoctor(config, diagnostics).run(online=online, site_key=site_key, open_core=open_core)

    @property
    def core(self) -> Any:
        if self._core is None:
            self._core = self.core_binding.open()
        return self._core

    def core_compatibility(self) -> CoreCompatibility:
        return self.core_binding.assert_compatible()

    def test_wordpress(self) -> WordPressConnection:
        return self.wordpress.test_connection()

    def wordpress_site_info(self) -> WordPressSiteInfo:
        return self.wordpress.get_site_info()

    def wordpress_categories(self, *, search: str | None = None, per_page: int = 100) -> tuple[WordPressTerm, ...]:
        return self.wordpress.list_categories(search=search, per_page=per_page)

    def wordpress_tags(self, *, search: str | None = None, per_page: int = 100) -> tuple[WordPressTerm, ...]:
        return self.wordpress.list_tags(search=search, per_page=per_page)

    def create_wordpress_tag(self, *, name: str, slug: str | None = None) -> WordPressTerm:
        return self.wordpress.create_tag(name=name, slug=slug)

    def create_text_draft(
        self,
        *,
        title: str,
        content: str,
        excerpt: str | None = None,
        slug: str | None = None,
        category_id: int | None = None,
        featured_media_id: int | None = None,
    ) -> WordPressPost:
        return self.create_text_draft_workflow.execute(
            title=title,
            content=content,
            excerpt=excerpt,
            slug=slug,
            category_id=category_id,
            featured_media_id=featured_media_id,
        )

    def upload_wordpress_media(
        self,
        file_path: str | Path,
        *,
        mime_type: str | None = None,
        slug: str | None = None,
        title: str | None = None,
        caption: str | None = None,
        description: str | None = None,
        alt_text: str | None = None,
        parent_post_id: int | None = None,
    ) -> WordPressMedia:
        return self.upload_media_workflow.execute(
            file_path,
            mime_type=mime_type,
            slug=slug,
            title=title,
            caption=caption,
            description=description,
            alt_text=alt_text,
            parent_post_id=parent_post_id,
        )

    def wordpress_post(self, post_id: int) -> WordPressPost:
        return self.wordpress.get_post(post_id)

    def wordpress_media(self, media_id: int) -> WordPressMedia:
        return self.wordpress.get_media(media_id)

    def preview_wordpress_publication(
        self,
        peer: Peer,
        message_id: int,
        *,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
    ) -> WordPressPublicationResult:
        return self.publish_message_workflow.preview(
            self.core,
            peer,
            message_id,
            site_key=self.site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )

    def wordpress_publication_status(
        self,
        peer: Peer,
        message_id: int,
        *,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
    ) -> WordPressPublicationResult:
        return self.publish_message_workflow.status(
            self.core,
            peer,
            message_id,
            site_key=self.site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
        )

    def preview_wordpress_publication_update(
        self,
        peer: Peer,
        message_id: int,
        *,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
        allow_live_update: bool = False,
        restore_trashed: bool = False,
    ) -> WordPressPublicationResult:
        return self.publish_message_workflow.update_preview(
            self.core,
            peer,
            message_id,
            site_key=self.site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
            allow_live_update=allow_live_update,
            restore_trashed=restore_trashed,
        )

    def update_wordpress_publication(
        self,
        peer: Peer,
        message_id: int,
        *,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
        max_media_bytes: int | None = 100 * 1024 * 1024,
        allow_live_update: bool = False,
        overwrite_remote_drift: bool = False,
        restore_trashed: bool = False,
    ) -> WordPressPublicationResult:
        return self.publish_message_workflow.update_execute(
            self.core,
            peer,
            message_id,
            site_key=self.site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
            max_media_bytes=max_media_bytes,
            allow_live_update=allow_live_update,
            overwrite_remote_drift=overwrite_remote_drift,
            restore_trashed=restore_trashed,
        )

    def publish_stored_message(
        self,
        peer: Peer,
        message_id: int,
        *,
        title: str | None = None,
        category_id: int | None = None,
        include_media: bool = True,
        max_media_bytes: int | None = 100 * 1024 * 1024,
        retry_skipped: bool = False,
    ) -> WordPressPublicationResult:
        return self.publish_message_workflow.execute(
            self.core,
            peer,
            message_id,
            site_key=self.site_key,
            title=title,
            category_id=category_id,
            include_media=include_media,
            max_media_bytes=max_media_bytes,
            retry_skipped=retry_skipped,
        )

    def preview_wordpress_composition(
        self, request: WordPressCompositionRequest
    ) -> WordPressCompositionResult:
        if request.site_key != self.site_key:
            raise CompositionValidationError("Composition site_key must match the opened Bridge site.", code="composition_site_mismatch")
        return self.compose_messages_workflow.preview(self.core, request)

    def publish_wordpress_composition(
        self,
        request: WordPressCompositionRequest,
        *,
        max_media_bytes: int | None = 100 * 1024 * 1024,
    ) -> WordPressCompositionResult:
        if request.site_key != self.site_key:
            raise CompositionValidationError("Composition site_key must match the opened Bridge site.", code="composition_site_mismatch")
        return self.compose_messages_workflow.execute(
            self.core, request, max_media_bytes=max_media_bytes
        )

    def wordpress_composition_status(
        self, request: WordPressCompositionRequest
    ) -> WordPressCompositionResult:
        if request.site_key != self.site_key:
            raise CompositionValidationError("Composition site_key must match the opened Bridge site.", code="composition_site_mismatch")
        return self.compose_messages_workflow.status(self.core, request)

    def update_wordpress_composition(
        self,
        request: WordPressCompositionRequest,
        *,
        max_media_bytes: int | None = 100 * 1024 * 1024,
    ) -> WordPressCompositionResult:
        if request.site_key != self.site_key:
            raise CompositionValidationError("Composition site_key must match the opened Bridge site.", code="composition_site_mismatch")
        return self.compose_messages_workflow.update(
            self.core, request, max_media_bytes=max_media_bytes
        )

    def wordpress_compositions(self, *, limit: int = 100) -> tuple[Any, ...]:
        return self.compose_messages_workflow.store.list(self.site_key, limit=limit)

    def wordpress_message_usage_details(self, peer: Peer, message_id: int) -> dict[str, object]:
        publication = self.core.publications.get(
            peer, message_id, target_type="wordpress", target_key=self.site_key
        )
        source_key = f"{peer.type.value}:{peer.id}:{message_id}"
        compositions = self.compose_messages_workflow.store.find_by_source(self.site_key, source_key)
        composition = compositions[0] if compositions else None
        used = bool((publication and publication.external_post_id) or composition)
        stale = bool(publication and publication.stale)
        return {
            "site_key": self.site_key,
            "source_key": source_key,
            "used": used,
            "usage_state": "stale" if stale else ("used" if used else "unused"),
            "stale": stale,
            "publication_status": publication.status.value if publication else ("published" if composition else None),
            "external_post_id": publication.external_post_id if publication and publication.external_post_id else (composition.post_id if composition else None),
            "external_url": publication.external_url if publication and publication.external_url else (composition.post_url if composition else None),
            "compositions": [
                {
                    "composition_key": item.composition_key,
                    "post_id": item.post_id,
                    "post_url": item.post_url,
                    "status": item.status,
                    "title": item.title,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in compositions
            ],
        }

    def _application_message_item(
        self, peer: Peer, message: Any, *, album_size: int = 1
    ) -> dict[str, object]:
        media = None
        if message.media is not None:
            media = {
                "type": message.media.type.value,
                "mime_type": message.media.mime_type,
                "file_name": message.media.file_name,
                "size": message.media.size,
                "is_image": message.media.type.value in {"photo", "image_document", "sticker"},
            }
        sender_key = None
        if message.from_peer is not None and message.from_peer.type.value == "user":
            sender_key = f"user:{message.from_peer.id}"
        elif message.outgoing:
            sender_key = "self"
        return {
            "id": message.id,
            "date": message.date.isoformat(),
            "text": message.text,
            "text_length": len(message.text),
            "media": media,
            "outgoing": message.outgoing,
            "sender_key": sender_key,
            "reply_to_message_id": message.reply_to_message_id,
            "grouped_id": message.grouped_id,
            "album_size": album_size,
            "usage": self.wordpress_message_usage_details(peer, message.id),
        }

    def _application_message_items(
        self, peer: Peer, messages: tuple[Any, ...] | list[Any]
    ) -> list[dict[str, object]]:
        album_sizes: dict[int, int] = {}
        for message in messages:
            if message.grouped_id is not None:
                album_sizes[message.grouped_id] = album_sizes.get(message.grouped_id, 0) + 1
        return [
            self._application_message_item(
                peer,
                message,
                album_size=album_sizes.get(message.grouped_id, 1),
            )
            for message in messages
        ]

    def _expand_local_albums(
        self, peer: Peer, messages: tuple[Any, ...]
    ) -> tuple[Any, ...]:
        """Complete locally available albums that cross a message-list boundary."""
        merged = {message.id: message for message in messages}
        grouped_ids = {
            message.grouped_id
            for message in messages
            if message.grouped_id is not None
        }
        for grouped_id in grouped_ids:
            for member in self.core.messages.list_album(peer, grouped_id):
                merged[member.id] = member
        return tuple(sorted(merged.values(), key=lambda message: message.id, reverse=True))

    def application_messages(
        self, peer: Peer, *, limit: int = 100, before_id: int | None = None
    ) -> dict[str, object]:
        if not 1 <= limit <= 500:
            raise CompositionValidationError(
                "Message list limit must be between 1 and 500.", code="api_invalid_message_limit"
            )
        messages = self.core.messages.list(peer, limit=limit, before_id=before_id)
        messages = self._expand_local_albums(peer, messages)
        items = self._application_message_items(peer, messages)
        return {
            "site_key": self.site_key,
            "peer": peer.safe_summary(),
            "message_count": len(items),
            "next_before_id": min((item["id"] for item in items), default=None),
            "messages": items,
        }

    def application_messages_by_date(
        self,
        peer: Peer,
        *,
        date_from: datetime,
        date_to: datetime,
        limit: int = 500,
    ) -> dict[str, object]:
        if not 1 <= limit <= 10_000:
            raise CompositionValidationError(
                "Date-filtered message limit must be between 1 and 10000.",
                code="api_invalid_message_limit",
            )
        page = self.core.messages.search(
            MessageSearchQuery(
                peer=peer, date_from=date_from, date_to=date_to, limit=limit
            )
        )
        items = self._application_message_items(peer, list(page.messages))
        return {
            "site_key": self.site_key,
            "peer": peer.safe_summary(),
            "message_count": len(items),
            "messages": items,
            "next_cursor_present": page.next_cursor is not None,
        }

    def sync_application_messages(
        self,
        peer: Peer,
        *,
        pages: int = 1,
        page_size: int = 20,
        offset_id: int = 0,
        stop_when_unchanged: bool = True,
    ) -> dict[str, object]:
        result = self.core.sync.sync(
            peer,
            pages=pages,
            page_size=page_size,
            offset_id=offset_id,
            stop_when_unchanged=stop_when_unchanged,
        )
        return result.safe_summary()


    def sync_application_messages_date_range(
        self,
        peer: Peer,
        *,
        date_from: datetime,
        date_to: datetime,
        pages: int = 100,
        page_size: int = 100,
    ) -> dict[str, object]:
        result = self.core.sync.sync_date_range(
            peer,
            date_from=date_from,
            date_to=date_to,
            pages=pages,
            page_size=page_size,
            store=True,
        )
        return result.safe_summary()

    def application_capabilities(self) -> dict[str, object]:
        return {
            "bridge_version": __version__,
            "api_version": "v1",
            "wordpress_post_statuses": ["draft", "publish"],
            "publish_requires_confirmation": True,
            "multi_message_composer": True,
            "message_usage_state": True,
            "message_sync": True,
            "grouped_media_albums": True,
            "taxonomies": ["category", "post_tag"],
            "core": self.core.capabilities(),
        }

    def wordpress_message_usage(self, peer: Peer, message_id: int) -> dict[str, object]:
        return self.compose_messages_workflow.message_usage(
            self.core, site_key=self.site_key, peer=peer, message_id=message_id
        )

    @staticmethod
    def _shared_core_key(
        config: BridgeConfig | CoreDependencyConfig,
    ) -> tuple[str, str, str]:
        core = config.core if isinstance(config, BridgeConfig) else config
        return (
            str(core.session_file.resolve()),
            str(core.database_file.resolve()),
            str(core.media_directory.resolve()),
        )

    @classmethod
    def close_shared_core(cls, core_config: CoreDependencyConfig) -> None:
        """Close only the Core owned by one explicit storage boundary."""

        key = cls._shared_core_key(core_config)
        with cls._shared_core_lock:
            core = cls._shared_cores.pop(key, None)
        if core is not None:
            try:
                core.close()
            except Exception:
                pass

    @classmethod
    def close_shared_cores(cls) -> None:
        with cls._shared_core_lock:
            cores = list(cls._shared_cores.values())
            cls._shared_cores.clear()
        for core in cores:
            try:
                core.close()
            except Exception:
                pass

    def close(self) -> None:
        if self._core is not None and self._owns_core:
            self._core.close()
        self._core = None
        self._wordpress_client.close()
        self.diagnostics.emit("bridge", "bridge_closed", fields={"shared_core": not self._owns_core})

    def __enter__(self) -> "EitaaBridge":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc is not None:
            self.diagnostics.emit(
                "bridge",
                "bridge_context_failed",
                level="error",
                fields={"error_type": type(exc).__name__},
            )
        self.close()
