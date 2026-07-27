# WordPress Media phase

## Purpose

WordPress Media 1 proves the reusable WordPress-side media adapter before any automated Eitaa publication workflow is added.

## Supported operations

### Upload

Bridge sends one authenticated multipart `POST` to:

```text
/wp-json/wp/v2/media
```

The request contains one streamed local file and may include:

- `title`
- `caption`
- `description`
- `alt_text`
- `post` as the parent Post ID

The complete file is not loaded into memory and the file handle is closed immediately after the request returns.

### Retrieve

Bridge performs an authenticated, retry-safe `GET` to:

```text
/wp-json/wp/v2/media/<id>?context=edit
```

### Featured media

Draft creation may include an existing positive Media ID as `featured_media`. The upload and Draft creation are intentionally separate commands. This prevents Bridge from continuing into a second write when the first write has an unknown outcome.

## MIME handling

Bridge first uses the local filename extension to infer the MIME type. If it cannot infer one, the operator must pass `--mime-type`. WordPress remains the final authority on whether the selected site allows that MIME type and file size.

## Result model

A successful media operation returns a typed `WordPressMedia` object containing:

- Media ID
- status
- media type
- MIME type
- source URL presence
- slug presence
- selected `site_key`
- optional parent Post ID
- whether the item is an image

Diagnostics and normal safe summaries do not expose the local filename or textual metadata.

## Failure model

Local validation failures return `media_file_error` before a network request. WordPress rejection returns a typed HTTP/authentication error. Any uncertain POST result returns `wordpress_ambiguous_write` and is not retried.

## Core boundary

This phase does not call `core.media`, `core.messages`, `core.retrieval`, or `core.publications`. The WordPress adapter accepts a local path so a later workflow can pass a path produced by the public Core media service without changing this adapter.
