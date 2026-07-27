# Application API v1

## Purpose

The API is the stable local boundary used by the Electron UI. It exposes only public Core and Bridge facades and returns JSON. Electron communicates through its isolated preload process, so the renderer does not require permissive CORS or Node integration.

## UI flow

1. `auth/status` selects the login gate or workspace.
2. staged auth endpoints perform phone, code, and optional 2FA login.
3. `dialogs/list` discovers dialogs and creates reusable peer files.
4. `messages/sync` and `messages/list` provide scroll-based local history;
   grouped media include nullable `grouped_id` and local `album_size` metadata.
5. `messages/media-preview` provides bounded cached image previews.
6. category and tag endpoints populate WordPress controls.
7. composition endpoints Preview or create one WordPress post from ordered messages.
8. compositions and message usage endpoints provide used/stale UI state.
9. explicit local-index endpoints build and expose advisory category
   suggestions without making a WordPress write or using the Eitaa scheduler.

## Routes

```text
GET  /api/v1/health
GET  /api/v1/schema
GET  /api/v1/auth/status
POST /api/v1/auth/request-code
POST /api/v1/auth/submit-code
POST /api/v1/auth/submit-password
POST /api/v1/auth/logout
GET  /api/v1/sites
GET  /api/v1/capabilities
GET  /api/v1/compositions
GET  /api/v1/wordpress/categories
GET  /api/v1/wordpress/tags
POST /api/v1/dialogs/list
POST /api/v1/messages/list
POST /api/v1/messages/media-preview
POST /api/v1/messages/sync
POST /api/v1/messages/usage
POST /api/v1/messages/index/start
GET  /api/v1/messages/index/status
POST /api/v1/messages/index/cancel
POST /api/v1/messages/index/results
POST /api/v1/messages/index/feedback
POST /api/v1/compositions/preview
POST /api/v1/compositions/status
POST /api/v1/compositions/publish
```

## Write safety

- Draft is the default.
- Publish requires `post_status=publish` and `confirm_publish=true`.
- WordPress `publish_posts` is checked before upload.
- already-used Eitaa sources block a new composition.
- media previews are limited and cached locally.
- login challenges stay in memory and secret challenge values never appear in JSON.
- local indexing has a 50,000-message hard cap, explicit progress/cancellation
  and staging-table promotion; its database contains hashes and suggestions,
  not raw message text.

## HTTP security

The server binds to `127.0.0.1:8765` by default. Bearer authentication is optional on loopback and mandatory for non-loopback binding. The renderer uses Electron IPC rather than direct cross-origin browser requests.
