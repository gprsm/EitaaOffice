from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...domain import WordPressMedia
from ..services.wordpress_service import WordPressService


@dataclass(slots=True)
class UploadWordPressMedia:
    wordpress: WordPressService

    def execute(
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
        return self.wordpress.upload_media(
            file_path,
            mime_type=mime_type,
            slug=slug,
            title=title,
            caption=caption,
            description=description,
            alt_text=alt_text,
            parent_post_id=parent_post_id,
        )
