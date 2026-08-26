from __future__ import annotations

from pathlib import Path

from ...domain import WordPressConnection, WordPressMedia, WordPressPost, WordPressSiteInfo, WordPressTerm
from ...infrastructure.wordpress import WordPressClient


class WordPressService:
    def __init__(self, client: WordPressClient) -> None:
        self.client = client

    def get_site_info(self) -> WordPressSiteInfo:
        return self.client.get_site_info()

    def test_connection(self) -> WordPressConnection:
        return self.client.test_connection()

    def create_text_draft(
        self,
        *,
        title: str,
        content: str,
        excerpt: str | None = None,
        slug: str | None = None,
        category_id: int | None = None,
        category_ids: tuple[int, ...] | None = None,
        tag_ids: tuple[int, ...] = (),
        featured_media_id: int | None = None,
    ) -> WordPressPost:
        return self.client.create_text_draft(
            title=title,
            content=content,
            excerpt=excerpt,
            slug=slug,
            category_id=category_id,
            category_ids=category_ids,
            tag_ids=tag_ids,
            featured_media_id=featured_media_id,
        )

    def create_post(
        self,
        *,
        title: str,
        content: str,
        status: str = "draft",
        excerpt: str | None = None,
        slug: str | None = None,
        category_id: int | None = None,
        category_ids: tuple[int, ...] | None = None,
        tag_ids: tuple[int, ...] = (),
        featured_media_id: int | None = None,
    ) -> WordPressPost:
        return self.client.create_post(
            title=title,
            content=content,
            status=status,
            excerpt=excerpt,
            slug=slug,
            category_id=category_id,
            category_ids=category_ids,
            tag_ids=tag_ids,
            featured_media_id=featured_media_id,
        )

    def update_post(
        self,
        post_id: int,
        *,
        title: str,
        content: str,
        slug: str | None = None,
        category_id: int | None = None,
        category_ids: tuple[int, ...] | None = None,
        tag_ids: tuple[int, ...] | None = None,
        excerpt: str | None = None,
        featured_media_id: int | None = None,
        status: str | None = None,
        restore_to_draft: bool = False,
    ) -> WordPressPost:
        return self.client.update_post(
            post_id,
            title=title,
            content=content,
            slug=slug,
            category_id=category_id,
            category_ids=category_ids,
            tag_ids=tag_ids,
            excerpt=excerpt,
            featured_media_id=featured_media_id,
            status=status,
            restore_to_draft=restore_to_draft,
        )

    def list_categories(self, *, search: str | None = None, per_page: int = 100) -> tuple[WordPressTerm, ...]:
        return self.client.list_categories(search=search, per_page=per_page)

    def list_tags(self, *, search: str | None = None, per_page: int = 100) -> tuple[WordPressTerm, ...]:
        return self.client.list_tags(search=search, per_page=per_page)

    def create_tag(self, *, name: str, slug: str | None = None) -> WordPressTerm:
        return self.client.create_tag(name=name, slug=slug)

    def upload_media(
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
        return self.client.upload_media(
            file_path,
            mime_type=mime_type,
            slug=slug,
            title=title,
            caption=caption,
            description=description,
            alt_text=alt_text,
            parent_post_id=parent_post_id,
        )

    def get_media(self, media_id: int) -> WordPressMedia:
        return self.client.get_media(media_id)

    def find_posts_by_slug(self, slug: str) -> tuple[WordPressPost, ...]:
        return self.client.find_posts_by_slug(slug)

    def get_post(self, post_id: int) -> WordPressPost:
        return self.client.get_post(post_id)

    def find_media_by_slug(self, slug: str) -> tuple[WordPressMedia, ...]:
        return self.client.find_media_by_slug(slug)
