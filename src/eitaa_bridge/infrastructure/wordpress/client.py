from __future__ import annotations

import mimetypes
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from requests.auth import HTTPBasicAuth

from ...config import WordPressSiteConfig
from ...domain import WordPressConnection, WordPressMedia, WordPressPost, WordPressSiteInfo, WordPressTerm
from ...errors import (
    MediaFileError,
    WordPressAmbiguousWriteError,
    WordPressAuthenticationError,
    WordPressConnectionError,
    WordPressHttpError,
    WordPressResponseError,
)
from ...version import __version__
from ..diagnostics import BridgeDiagnosticManager
from .auth import WordPressCredentials, require_wordpress_credentials

_TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}
_SAFE_RETRY_METHODS = {"GET", "HEAD", "OPTIONS"}
_WRITABLE_POST_STATUSES = {"draft", "publish", "pending", "private"}


class WordPressClient:
    def __init__(
        self,
        site: WordPressSiteConfig,
        credentials: WordPressCredentials,
        *,
        diagnostics: BridgeDiagnosticManager | None = None,
        session: requests.Session | Any | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        site.validate()
        self.site = site
        self.credentials = credentials
        self.diagnostics = diagnostics
        self.session = session or requests.Session()
        self._sleep = sleep

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def get_site_info(self) -> WordPressSiteInfo:
        data = self._request_json("GET", "/wp-json/", authenticated=False, expected={200})
        namespaces = data.get("namespaces", [])
        if not isinstance(namespaces, list):
            namespaces = []
        info = WordPressSiteInfo(
            name=str(data.get("name") or ""),
            url=str(data.get("url") or self.site.normalized_base_url),
            home=str(data["home"]) if data.get("home") else None,
            description=str(data["description"]) if data.get("description") else None,
            timezone=(
                str(data.get("timezone_string") or data.get("timezone"))
                if data.get("timezone_string") or data.get("timezone")
                else None
            ),
            namespaces=tuple(str(value) for value in namespaces),
        )
        if not info.name or not info.url:
            raise WordPressResponseError(
                "WordPress site information response is missing required fields.",
                safe_context={"site_key": self.site.site_key},
            )
        self._emit("site_info_received", info.safe_summary())
        return info

    def test_connection(self) -> WordPressConnection:
        site_info = self.get_site_info()
        data = self._request_json(
            "GET", "/wp-json/wp/v2/users/me?context=edit", authenticated=True, expected={200}
        )
        user_id = data.get("id")
        capabilities = data.get("capabilities")
        if not isinstance(user_id, int) or not isinstance(capabilities, Mapping):
            raise WordPressResponseError(
                "WordPress authenticated user response is incomplete.",
                safe_context={"site_key": self.site.site_key},
            )
        result = WordPressConnection(
            site_key=self.site.site_key,
            authenticated=True,
            user_id=user_id,
            can_edit_posts=bool(capabilities.get("edit_posts") or capabilities.get("edit_others_posts")),
            can_publish_posts=bool(capabilities.get("publish_posts")),
            can_upload_files=bool(capabilities.get("upload_files")),
            site=site_info,
        )
        self._emit("connection_test_succeeded", result.safe_summary())
        return result

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
        """Backward-compatible helper that always creates a Draft."""
        return self.create_post(
            title=title,
            content=content,
            status="draft",
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
        selected_status = str(status).strip().lower()
        if selected_status not in _WRITABLE_POST_STATUSES:
            raise WordPressResponseError(
                "Unsupported WordPress post status.",
                safe_context={"site_key": self.site.site_key, "status": selected_status},
            )
        if not title.strip():
            raise WordPressResponseError("Post title cannot be blank.")
        if not content.strip():
            raise WordPressResponseError("Post content cannot be blank.")
        payload: dict[str, Any] = {"title": title, "content": content, "status": selected_status}
        if excerpt is not None:
            payload["excerpt"] = excerpt
        if slug:
            payload["slug"] = slug
        selected_categories = self._selected_term_ids(
            singular=category_id,
            multiple=category_ids,
            default=self.site.default_category_id,
            field_name="category_ids",
        )
        selected_tags = self._validated_term_ids(tag_ids, "tag_ids")
        if selected_categories:
            payload["categories"] = list(selected_categories)
        if selected_tags:
            payload["tags"] = list(selected_tags)
        if featured_media_id is not None:
            if featured_media_id <= 0:
                raise WordPressResponseError("featured_media_id must be positive.")
            payload["featured_media"] = featured_media_id
        data = self._request_json(
            "POST", "/wp-json/wp/v2/posts", authenticated=True, expected={200, 201}, json_body=payload
        )
        post_id = data.get("id")
        returned_status = data.get("status")
        if not isinstance(post_id, int) or post_id <= 0 or not isinstance(returned_status, str):
            raise self._ambiguous_write_error(method="POST", path="/wp-json/wp/v2/posts")
        returned_featured = data.get("featured_media")
        post = WordPressPost(
            id=post_id,
            status=returned_status,
            link=str(data["link"]) if data.get("link") else None,
            slug=str(data["slug"]) if data.get("slug") else None,
            site_key=self.site.site_key,
            featured_media_id=(
                returned_featured
                if isinstance(returned_featured, int) and returned_featured > 0
                else featured_media_id
            ),
        )
        self._emit(
            "post_created",
            {
                **post.safe_summary(),
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "category_ids": selected_categories,
                "tag_ids": selected_tags,
                "requested_status": selected_status,
            },
        )
        return post

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
        """Update one existing WordPress post without automatic write retry.

        The current remote status is normally omitted from the payload, so a
        Draft remains a Draft and an explicitly allowed live post remains live.
        When ``restore_to_draft`` is true, the same trashed post is explicitly
        restored as a Draft. ``featured_media_id=None`` clears the featured image.
        """
        if post_id <= 0:
            raise WordPressResponseError("post_id must be positive.")
        if not title.strip():
            raise WordPressResponseError("Post title cannot be blank.")
        if not content.strip():
            raise WordPressResponseError("Post content cannot be blank.")
        payload: dict[str, Any] = {
            "title": title,
            "content": content,
            "featured_media": featured_media_id or 0,
        }
        if restore_to_draft and status is not None:
            raise WordPressResponseError("status and restore_to_draft cannot be combined.")
        if restore_to_draft:
            payload["status"] = "draft"
        elif status is not None:
            selected_status = str(status).strip().lower()
            if selected_status not in _WRITABLE_POST_STATUSES:
                raise WordPressResponseError(
                    "Unsupported WordPress post status.",
                    safe_context={"site_key": self.site.site_key, "status": selected_status},
                )
            payload["status"] = selected_status
        if slug:
            payload["slug"] = self._validated_slug(slug)
        if excerpt is not None:
            payload["excerpt"] = excerpt
        selected_categories = self._selected_term_ids(
            singular=category_id,
            multiple=category_ids,
            default=self.site.default_category_id,
            field_name="category_ids",
        )
        selected_tags = (
            self._validated_term_ids(tag_ids, "tag_ids")
            if tag_ids is not None else None
        )
        if selected_categories:
            payload["categories"] = list(selected_categories)
        else:
            payload["categories"] = []
        if selected_tags is not None:
            payload["tags"] = list(selected_tags)
        path = f"/wp-json/wp/v2/posts/{post_id}"
        data = self._request_json(
            "POST", path, authenticated=True, expected={200}, json_body=payload
        )
        try:
            post = self._post_from_response(data)
        except WordPressResponseError as exc:
            raise self._ambiguous_write_error(
                method="POST", path=path, error_type=type(exc).__name__
            ) from exc
        if post.id != post_id:
            raise self._ambiguous_write_error(method="POST", path=path)
        self._emit(
            "post_updated",
            {
                **post.safe_summary(),
                "title": title,
                "content": content,
                "category_ids": selected_categories,
                "tag_ids": selected_tags,
            },
        )
        return post

    def find_posts_by_slug(self, slug: str) -> tuple[WordPressPost, ...]:
        selected = self._validated_slug(slug)
        query = urlencode({
            "context": "edit",
            "slug": selected,
            "status": "any",
            "per_page": 10,
        })
        path = f"/wp-json/wp/v2/posts?{query}"
        data = self._request_json_list("GET", path, authenticated=True, expected={200})
        posts = tuple(self._post_from_response(item) for item in data)
        self._emit("posts_found_by_slug", {"slug": selected, "count": len(posts)})
        return posts

    def get_post(self, post_id: int) -> WordPressPost:
        if post_id <= 0:
            raise WordPressResponseError("post_id must be positive.")
        data = self._request_json(
            "GET", f"/wp-json/wp/v2/posts/{post_id}?context=edit",
            authenticated=True, expected={200},
        )
        post = self._post_from_response(data)
        self._emit("post_received", post.safe_summary())
        return post

    def _post_from_response(self, data: dict[str, Any]) -> WordPressPost:
        post_id = data.get("id")
        status = data.get("status")
        if not isinstance(post_id, int) or post_id <= 0 or not isinstance(status, str):
            raise WordPressResponseError(
                "WordPress post response is missing required fields.",
                safe_context={"site_key": self.site.site_key},
                debug_file=self._debug_file("wordpress"),
            )
        featured = data.get("featured_media")
        title = data.get("title")
        content = data.get("content")
        excerpt = data.get("excerpt")
        categories = data.get("categories")
        tags = data.get("tags")
        title_raw = None
        content_raw = None
        excerpt_raw = None
        if isinstance(title, Mapping):
            value = title.get("raw")
            if not isinstance(value, str):
                value = title.get("rendered")
            title_raw = value if isinstance(value, str) else None
        elif isinstance(title, str):
            title_raw = title
        if isinstance(content, Mapping):
            value = content.get("raw")
            if not isinstance(value, str):
                value = content.get("rendered")
            content_raw = value if isinstance(value, str) else None
        elif isinstance(content, str):
            content_raw = content
        if isinstance(excerpt, Mapping):
            value = excerpt.get("raw")
            if not isinstance(value, str):
                value = excerpt.get("rendered")
            excerpt_raw = value if isinstance(value, str) else None
        elif isinstance(excerpt, str):
            excerpt_raw = excerpt
        category_ids = tuple(
            value for value in categories or ()
            if isinstance(value, int) and value > 0
        ) if isinstance(categories, list) else ()
        tag_ids = tuple(
            value for value in tags or ()
            if isinstance(value, int) and value > 0
        ) if isinstance(tags, list) else ()
        return WordPressPost(
            id=post_id,
            status=status,
            link=str(data["link"]) if data.get("link") else None,
            slug=str(data["slug"]) if data.get("slug") else None,
            site_key=self.site.site_key,
            featured_media_id=featured if isinstance(featured, int) and featured > 0 else None,
            title_raw=title_raw,
            content_raw=content_raw,
            excerpt_raw=excerpt_raw,
            category_ids=category_ids,
            tag_ids=tag_ids,
            modified_gmt=str(data["modified_gmt"]) if data.get("modified_gmt") else None,
        )

    def list_categories(self, *, search: str | None = None, per_page: int = 100) -> tuple[WordPressTerm, ...]:
        return self._list_terms("categories", "category", search=search, per_page=per_page)

    def list_tags(self, *, search: str | None = None, per_page: int = 100) -> tuple[WordPressTerm, ...]:
        return self._list_terms("tags", "post_tag", search=search, per_page=per_page)

    def create_tag(self, *, name: str, slug: str | None = None) -> WordPressTerm:
        selected_name = name.strip()
        if not selected_name:
            raise WordPressResponseError("Tag name cannot be blank.")
        existing = self.list_tags(search=selected_name, per_page=100)
        for term in existing:
            if term.name.casefold() == selected_name.casefold():
                return term
        payload: dict[str, Any] = {"name": selected_name}
        if slug and slug.strip():
            payload["slug"] = slug.strip()
        data = self._request_json(
            "POST", "/wp-json/wp/v2/tags", authenticated=True, expected={200, 201}, json_body=payload
        )
        term = self._term_from_response(data, "post_tag")
        self._emit("taxonomy_term_created", {"taxonomy": "post_tag", "term_id": term.id})
        return term

    def _list_terms(
        self, endpoint: str, taxonomy: str, *, search: str | None, per_page: int
    ) -> tuple[WordPressTerm, ...]:
        if not 1 <= per_page <= 100:
            raise WordPressResponseError("per_page must be between 1 and 100.")
        query_data: dict[str, object] = {"context": "view", "per_page": per_page, "orderby": "name", "order": "asc"}
        if search and search.strip():
            query_data["search"] = search.strip()
        path = f"/wp-json/wp/v2/{endpoint}?{urlencode(query_data)}"
        data = self._request_json_list("GET", path, authenticated=True, expected={200})
        terms = tuple(self._term_from_response(item, taxonomy) for item in data)
        self._emit("taxonomy_terms_received", {"taxonomy": taxonomy, "count": len(terms), "search_present": bool(search)})
        return terms

    def _term_from_response(self, data: dict[str, Any], taxonomy: str) -> WordPressTerm:
        term_id = data.get("id")
        name = data.get("name")
        slug = data.get("slug")
        if not isinstance(term_id, int) or term_id <= 0 or not isinstance(name, str) or not isinstance(slug, str):
            raise WordPressResponseError(
                "WordPress taxonomy response is missing required fields.",
                safe_context={"site_key": self.site.site_key, "taxonomy": taxonomy},
            )
        count = data.get("count")
        parent = data.get("parent")
        return WordPressTerm(
            id=term_id, name=name, slug=slug, taxonomy=taxonomy,
            count=count if isinstance(count, int) and count >= 0 else 0,
            parent_id=parent if isinstance(parent, int) and parent > 0 else None,
        )

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
        path = Path(file_path).expanduser().resolve()
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise MediaFileError(
                "Media file was not found.",
                safe_context={"suffix": path.suffix.lower(), "file_name_present": bool(path.name)},
            ) from exc
        except OSError as exc:
            raise MediaFileError(
                "Media file could not be inspected.",
                safe_context={"suffix": path.suffix.lower(), "error_type": type(exc).__name__},
            ) from exc
        if not path.is_file():
            raise MediaFileError(
                "Media path is not a regular file.",
                safe_context={"suffix": path.suffix.lower()},
            )
        if stat.st_size <= 0:
            raise MediaFileError(
                "Media file is empty.",
                safe_context={"suffix": path.suffix.lower(), "size_bytes": stat.st_size},
            )
        if any(character in path.name for character in "\r\n\x00"):
            raise MediaFileError("Media filename contains unsupported control characters.")

        selected_mime = (mime_type or mimetypes.guess_type(path.name)[0] or "").strip().lower()
        if not selected_mime or "/" not in selected_mime or any(ch.isspace() for ch in selected_mime):
            raise MediaFileError(
                "Media MIME type could not be inferred; provide --mime-type explicitly.",
                safe_context={"suffix": path.suffix.lower()},
            )
        if parent_post_id is not None and parent_post_id <= 0:
            raise WordPressResponseError("parent_post_id must be positive.")

        form: dict[str, Any] = {}
        if slug is not None:
            form["slug"] = self._validated_slug(slug)
        if title is not None:
            form["title"] = title
        if caption is not None:
            form["caption"] = caption
        if description is not None:
            form["description"] = description
        if alt_text is not None:
            form["alt_text"] = alt_text
        if parent_post_id is not None:
            form["post"] = parent_post_id

        try:
            with path.open("rb") as handle:
                data = self._request_json(
                    "POST",
                    "/wp-json/wp/v2/media",
                    authenticated=True,
                    expected={200, 201},
                    form_body=form,
                    files={"file": (path.name, handle, selected_mime)},
                    request_summary={
                        "media_upload": True,
                        "suffix": path.suffix.lower(),
                        "size_bytes": stat.st_size,
                        "mime_type": selected_mime,
                        "metadata_fields": sorted(form),
                    },
                )
        except OSError as exc:
            raise MediaFileError(
                "Media file could not be read.",
                safe_context={"suffix": path.suffix.lower(), "error_type": type(exc).__name__},
            ) from exc

        media = self._media_from_response(data, ambiguous_on_invalid=True)
        self._emit(
            "media_uploaded",
            {
                **media.safe_summary(),
                "file": path,
                "size_bytes": stat.st_size,
                "title": title,
                "caption": caption,
                "description": description,
                "alt_text": alt_text,
            },
        )
        return media

    def get_media(self, media_id: int) -> WordPressMedia:
        if media_id <= 0:
            raise WordPressResponseError("media_id must be positive.")
        path = f"/wp-json/wp/v2/media/{media_id}?context=edit"
        data = self._request_json("GET", path, authenticated=True, expected={200})
        media = self._media_from_response(data, ambiguous_on_invalid=False)
        self._emit("media_received", media.safe_summary())
        return media

    def find_media_by_slug(self, slug: str) -> tuple[WordPressMedia, ...]:
        selected = self._validated_slug(slug)
        query = urlencode({"context": "edit", "slug": selected, "per_page": 10})
        path = f"/wp-json/wp/v2/media?{query}"
        data = self._request_json_list("GET", path, authenticated=True, expected={200})
        media = tuple(
            self._media_from_response(item, ambiguous_on_invalid=False) for item in data
        )
        self._emit("media_found_by_slug", {"slug": selected, "count": len(media)})
        return media

    @staticmethod
    def _validated_term_ids(values: tuple[int, ...] | list[int], field_name: str) -> tuple[int, ...]:
        selected = tuple(int(value) for value in values)
        if any(value <= 0 for value in selected):
            raise WordPressResponseError(f"{field_name} must contain positive ids.")
        if len(set(selected)) != len(selected):
            raise WordPressResponseError(f"{field_name} cannot contain duplicate ids.")
        return selected

    def _selected_term_ids(
        self, *, singular: int | None, multiple: tuple[int, ...] | None, default: int | None, field_name: str
    ) -> tuple[int, ...]:
        if multiple is not None:
            return self._validated_term_ids(multiple, field_name)
        selected = singular if singular is not None else default
        return self._validated_term_ids((selected,), field_name) if selected is not None else ()

    @staticmethod
    def _validated_slug(slug: str) -> str:
        selected = slug.strip().lower()
        if not selected or len(selected) > 200:
            raise WordPressResponseError("slug must contain 1 to 200 characters.")
        if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in selected):
            raise WordPressResponseError(
                "slug may contain only lowercase ASCII letters, digits, and hyphens."
            )
        return selected

    def _media_from_response(
        self,
        data: dict[str, Any],
        *,
        ambiguous_on_invalid: bool,
    ) -> WordPressMedia:
        media_id = data.get("id")
        status = data.get("status")
        media_type = data.get("media_type")
        mime_type = data.get("mime_type")
        valid = (
            isinstance(media_id, int)
            and media_id > 0
            and isinstance(status, str)
            and isinstance(media_type, str)
            and isinstance(mime_type, str)
            and "/" in mime_type
        )
        if not valid:
            if ambiguous_on_invalid:
                raise self._ambiguous_write_error(method="POST", path="/wp-json/wp/v2/media")
            raise WordPressResponseError(
                "WordPress media response is missing required fields.",
                safe_context={"site_key": self.site.site_key},
                debug_file=self._debug_file("wordpress"),
            )
        parent = data.get("post")
        return WordPressMedia(
            id=media_id,
            status=status,
            media_type=media_type,
            mime_type=mime_type,
            source_url=str(data["source_url"]) if data.get("source_url") else None,
            slug=str(data["slug"]) if data.get("slug") else None,
            site_key=self.site.site_key,
            parent_post_id=parent if isinstance(parent, int) and parent > 0 else None,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        expected: set[int],
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        request_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = self._request_data(
            method, path, authenticated=authenticated, expected=expected,
            json_body=json_body, form_body=form_body, files=files,
            request_summary=request_summary,
        )
        if not isinstance(data, dict):
            raise WordPressResponseError(
                "WordPress returned an unexpected JSON structure.",
                safe_context={"method": method.upper(), "path": path},
                debug_file=self._debug_file("wordpress"),
            )
        return data

    def _request_json_list(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        expected: set[int],
    ) -> list[dict[str, Any]]:
        data = self._request_data(
            method, path, authenticated=authenticated, expected=expected
        )
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise WordPressResponseError(
                "WordPress returned an unexpected collection structure.",
                safe_context={"method": method.upper(), "path": path},
                debug_file=self._debug_file("wordpress"),
            )
        return data

    def _request_data(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool,
        expected: set[int],
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        request_summary: dict[str, Any] | None = None,
    ) -> Any:
        method = method.upper()
        if authenticated:
            require_wordpress_credentials(self.site, self.credentials)
        url = self.site.normalized_base_url + path
        retry_safe = method in _SAFE_RETRY_METHODS
        attempts = self.site.retry_attempts + 1 if retry_safe else 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                kwargs: dict[str, Any] = {
                    "auth": (
                        HTTPBasicAuth(
                            self.credentials.username,
                            self.credentials.application_password,
                        )
                        if authenticated
                        else None
                    ),
                    "headers": {
                        "Accept": "application/json",
                        "User-Agent": f"EitaaBridge/{__version__}",
                    },
                    "timeout": self.site.timeout_seconds,
                    "verify": self.site.verify_tls,
                }
                if json_body is not None:
                    kwargs["json"] = json_body
                if form_body is not None:
                    kwargs["data"] = form_body
                if files is not None:
                    kwargs["files"] = files
                response = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                self._emit(
                    "request_network_error",
                    {
                        "method": method,
                        "path": path,
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                        "retry_safe": retry_safe,
                    },
                    level="warning" if retry_safe and attempt < attempts else "error",
                )
                if retry_safe and attempt < attempts:
                    self._sleep(self._retry_delay(attempt, None))
                    continue
                if not retry_safe:
                    raise self._ambiguous_write_error(
                        method=method,
                        path=path,
                        error_type=type(exc).__name__,
                    ) from exc
                raise WordPressConnectionError(
                    "WordPress could not be reached.",
                    safe_context={
                        "site_key": self.site.site_key,
                        "error_type": type(exc).__name__,
                    },
                    debug_file=self._debug_file("wordpress"),
                ) from exc

            status = int(response.status_code)
            self._emit(
                "request_completed",
                {
                    "method": method,
                    "path": path,
                    "status": status,
                    "attempt": attempt,
                    "retry_safe": retry_safe,
                    "request_body": json_body,
                    "form_body": form_body,
                    "request_summary": request_summary,
                },
            )
            if status in expected:
                try:
                    return self._parse_data(response, method=method, path=path)
                except WordPressResponseError as exc:
                    if not retry_safe:
                        raise self._ambiguous_write_error(
                            method=method,
                            path=path,
                            status=status,
                            error_type=type(exc).__name__,
                        ) from exc
                    raise
            if status in {401, 403}:
                raise WordPressAuthenticationError(
                    "WordPress rejected the configured credentials or permissions.",
                    safe_context={"site_key": self.site.site_key, "status": status, "path": path},
                    debug_file=self._debug_file("wordpress"),
                    code=f"wordpress_http_{status}",
                )
            if status in _TRANSIENT_STATUS:
                if retry_safe and attempt < attempts:
                    self._sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))
                    continue
                if not retry_safe:
                    raise self._ambiguous_write_error(
                        method=method,
                        path=path,
                        status=status,
                        wordpress_error_code=self._safe_wp_error_code(response),
                    )
            wp_details = self._safe_wp_error_details(response)
            wp_code = wp_details.get("wordpress_error_code")
            if wp_details.pop("auth_forbidden", False):
                raise WordPressAuthenticationError(
                    "WordPress rejected the configured credentials or permissions.",
                    safe_context={
                        "site_key": self.site.site_key,
                        "status": 401,
                        "method": method,
                        "path": path,
                        **wp_details,
                    },
                    debug_file=self._debug_file("wordpress"),
                    code="wordpress_http_401",
                )
            message = (
                "WordPress rejected one or more post, taxonomy, or media parameters."
                if wp_code == "rest_invalid_param"
                else "WordPress returned an unsuccessful HTTP status."
            )
            raise WordPressHttpError(
                message,
                safe_context={
                    "site_key": self.site.site_key,
                    "status": status,
                    "method": method,
                    "path": path,
                    **wp_details,
                },
                debug_file=self._debug_file("wordpress"),
                code=f"wordpress_http_{status}",
            )

        raise WordPressConnectionError(
            "WordPress request failed after bounded retries.",
            safe_context={
                "site_key": self.site.site_key,
                "error_type": type(last_error).__name__ if last_error else None,
            },
            debug_file=self._debug_file("wordpress"),
        )

    def _ambiguous_write_error(
        self,
        *,
        method: str,
        path: str,
        status: int | None = None,
        error_type: str | None = None,
        wordpress_error_code: str | None = None,
    ) -> WordPressAmbiguousWriteError:
        context: dict[str, Any] = {
            "site_key": self.site.site_key,
            "method": method,
            "path": path,
            "outcome": "unknown",
            "automatic_retry": False,
        }
        if status is not None:
            context["status"] = status
        if error_type:
            context["error_type"] = error_type
        if wordpress_error_code:
            context["wordpress_error_code"] = wordpress_error_code
        self._emit("write_outcome_ambiguous", context, level="error")
        return WordPressAmbiguousWriteError(
            "The WordPress write may have succeeded, so Bridge did not retry it automatically. Check the selected site before retrying.",
            safe_context=context,
            debug_file=self._debug_file("wordpress"),
        )

    def _parse_data(self, response: Any, *, method: str, path: str) -> Any:
        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise WordPressResponseError(
                "WordPress returned a non-JSON response.",
                safe_context={"status": int(response.status_code), "method": method, "path": path},
                debug_file=self._debug_file("wordpress"),
            ) from exc
        return data

    @staticmethod
    def _safe_wp_error_details(response: Any) -> dict[str, Any]:
        try:
            data = response.json()
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        result: dict[str, Any] = {}
        code = data.get("code")
        if isinstance(code, str) and len(code) <= 128 and all(ch.isalnum() or ch in "_-.:" for ch in code):
            result["wordpress_error_code"] = code
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            result["wordpress_message"] = message.strip()[:1000]
        details = data.get("data")
        if isinstance(details, dict):
            params = details.get("params")
            if isinstance(params, dict):
                result["rejected_fields"] = sorted(str(key)[:128] for key in params.keys())[:50]
            elif isinstance(params, (list, tuple)):
                result["rejected_fields"] = [str(item)[:128] for item in params[:50]]
            nested_details = details.get("details")
            if isinstance(nested_details, dict):
                for item in nested_details.values():
                    if isinstance(item, dict):
                        item_code = item.get("code")
                        item_data = item.get("data")
                        item_status = item_data.get("status") if isinstance(item_data, dict) else None
                        if item_code == "rest_forbidden_status" or item_status in {401, 403}:
                            result["auth_forbidden"] = True
                            break
        return result

    @staticmethod
    def _safe_wp_error_code(response: Any) -> str | None:
        try:
            data = response.json()
        except Exception:
            return None
        if isinstance(data, dict) and isinstance(data.get("code"), str):
            value = data["code"]
            return value[:128] if all(ch.isalnum() or ch in "_-.:" for ch in value) else None
        return None

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(4.0, 0.5 * (2 ** (attempt - 1)))

    def _emit(self, event: str, fields: dict[str, Any], *, level: str = "info") -> None:
        if self.diagnostics:
            self.diagnostics.emit("wordpress", event, level=level, fields=fields)

    def _debug_file(self, component: str) -> str | None:
        return str(self.diagnostics.file_for(component)) if self.diagnostics and self.diagnostics.enabled else None
