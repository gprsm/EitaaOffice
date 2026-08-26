from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class WordPressSiteInfo:
    name: str
    url: str
    home: str | None = None
    description: str | None = None
    timezone: str | None = None
    namespaces: tuple[str, ...] = ()

    def safe_summary(self) -> dict[str, object]:
        return {
            "name_length": len(self.name),
            "url": self.url,
            "home_present": self.home is not None,
            "description_present": bool(self.description),
            "timezone": self.timezone,
            "namespace_count": len(self.namespaces),
            "wp_v2_available": "wp/v2" in self.namespaces,
        }


@dataclass(slots=True, frozen=True)
class WordPressConnection:
    site_key: str
    authenticated: bool
    user_id: int | None
    can_edit_posts: bool
    can_publish_posts: bool
    can_upload_files: bool
    site: WordPressSiteInfo

    def safe_summary(self) -> dict[str, object]:
        return {
            "site_key": self.site_key,
            "authenticated": self.authenticated,
            "user_id_present": self.user_id is not None,
            "can_edit_posts": self.can_edit_posts,
            "can_publish_posts": self.can_publish_posts,
            "can_upload_files": self.can_upload_files,
            "site": self.site.safe_summary(),
        }


@dataclass(slots=True, frozen=True)
class WordPressPost:
    id: int
    status: str
    link: str | None
    slug: str | None
    site_key: str
    featured_media_id: int | None = None
    title_raw: str | None = None
    content_raw: str | None = None
    excerpt_raw: str | None = None
    category_ids: tuple[int, ...] = ()
    tag_ids: tuple[int, ...] = ()
    modified_gmt: str | None = None

    def contains_marker(self, marker: str) -> bool:
        return bool(marker and self.content_raw and marker in self.content_raw)

    def matches_bridge_payload(
        self,
        *,
        title: str,
        content: str,
        featured_media_id: int | None,
        category_id: int | None = None,
        category_ids: tuple[int, ...] | None = None,
        tag_ids: tuple[int, ...] | None = None,
        excerpt: str | None = None,
    ) -> bool:
        if self.title_raw is not None and self.title_raw != title:
            return False
        if self.content_raw is not None and self.content_raw.strip() != content.strip():
            return False
        if self.featured_media_id != featured_media_id:
            return False
        if category_id is not None and self.category_ids and category_id not in self.category_ids:
            return False
        if category_ids is not None and tuple(self.category_ids) != tuple(category_ids):
            return False
        if tag_ids is not None and tuple(self.tag_ids) != tuple(tag_ids):
            return False
        if excerpt is not None and self.excerpt_raw is not None and self.excerpt_raw.strip() != excerpt.strip():
            return False
        return True

    def safe_summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "link_present": self.link is not None,
            "slug_present": bool(self.slug),
            "site_key": self.site_key,
            "featured_media_id": self.featured_media_id,
            "title_length": len(self.title_raw) if self.title_raw is not None else None,
            "content_length": len(self.content_raw) if self.content_raw is not None else None,
            "excerpt_length": len(self.excerpt_raw) if self.excerpt_raw is not None else None,
            "category_ids": list(self.category_ids),
            "tag_ids": list(self.tag_ids),
            "modified_gmt": self.modified_gmt,
        }


@dataclass(slots=True, frozen=True)
class WordPressMedia:
    id: int
    status: str
    media_type: str
    mime_type: str
    source_url: str | None
    slug: str | None
    site_key: str
    parent_post_id: int | None = None

    @property
    def is_image(self) -> bool:
        return self.media_type == "image" or self.mime_type.startswith("image/")

    def safe_summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "media_type": self.media_type,
            "mime_type": self.mime_type,
            "source_url_present": self.source_url is not None,
            "slug_present": bool(self.slug),
            "site_key": self.site_key,
            "parent_post_id": self.parent_post_id,
            "is_image": self.is_image,
        }


@dataclass(slots=True, frozen=True)
class WordPressTerm:
    id: int
    name: str
    slug: str
    taxonomy: str
    count: int = 0
    parent_id: int | None = None

    def safe_summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "taxonomy": self.taxonomy,
            "count": self.count,
            "parent_id": self.parent_id,
        }
