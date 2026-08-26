from __future__ import annotations

from dataclasses import dataclass

from ...domain import WordPressPost
from ..services.wordpress_service import WordPressService


@dataclass(slots=True)
class CreateTextDraft:
    wordpress: WordPressService

    def execute(
        self,
        *,
        title: str,
        content: str,
        excerpt: str | None = None,
        slug: str | None = None,
        category_id: int | None = None,
        featured_media_id: int | None = None,
    ) -> WordPressPost:
        return self.wordpress.create_text_draft(
            title=title,
            content=content,
            excerpt=excerpt,
            slug=slug,
            category_id=category_id,
            featured_media_id=featured_media_id,
        )
