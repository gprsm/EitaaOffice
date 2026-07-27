# Extracted Core 7.4.1 contract

The supplied Core archive was inspected directly before Bridge construction.

## Packaging

- project name: `eitaa-core`
- package version: `0.6.0.dev15`
- product version: `0.6.0-core7.4.1`
- Python: `>=3.11`
- dependencies: `requests>=2.31,<3`, `tzdata>=2024.1`
- bundled Wheel: `eitaa_core-0.6.0.dev15-py3-none-any.whl`
- SQLite schema: `7`

## Facade

The stable public entry point is:

```python
from eitaa_core import EitaaCore, EitaaCoreConfig
core = EitaaCore.open(EitaaCoreConfig(...))
```

Relevant public services are `core.messages`, `core.retrieval`, `core.media`, `core.publications`, and `core.sync`. `core.doctor()` runs deterministic local checks. `core.capabilities()` reports `publication_workflow=True` and `database_schema=7`.

## Publications API

The public `PublicationService` exposes:

- `get(...)`
- `mark_pending(...)`
- `mark_processing(...)`
- `mark_published(..., external_post_id, external_url)`
- `mark_failed(..., error_code)`
- `mark_skipped(...)`
- `list(...)`

`mark_published` records the current Core message hash. When a published local message changes, Core returns the publication as `needs_update` and sets `stale=True`. Bridge must not reproduce this logic.

## Installation decision

The Bridge distribution includes the exact Core Wheel under `vendor/`; it does not include Core source. `setup_venv.bat` installs that Wheel as a dependency and then installs Bridge. This keeps the projects independent and removes manual merge steps.

## Sender-filtered retrieval

Foundation 3 requires the public `MessageSearchQuery.sender` field. Bridge does not query Core SQLite directly; future workflows pass the conversation peer, sender identity, limit, and cursor through `core.messages.search`.
