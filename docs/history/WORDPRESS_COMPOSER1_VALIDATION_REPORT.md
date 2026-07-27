# Eitaa Bridge v0.5 WordPress Composer 1 — Validation Report

Date: 2026-07-17

## Accepted baseline

- Direct baseline: Eitaa Bridge v0.4 WordPress Update 1.2
- Foundation baseline: Eitaa Bridge v0.1 Foundation 3
- Core product: `0.6.0-core7.4.1`
- Core package: `0.6.0.dev15`
- Core SQLite schema: `7`
- Core wheel SHA-256: `0e16dac9fbb1d1994301012f36f5a83286ce56631cb0d22f0425a56f87d8a092`
- The bundled Core wheel is byte-identical to Foundation 3.

## Bridge release

- Product: `0.5.0-wordpress-composer1`
- Package: `0.5.0.dev1`
- Composition-state schema: `1`
- Configuration schema: `1` (backward-compatible optional state-file path)

## Implemented capability

- one WordPress Draft from 1–100 ordered Eitaa messages;
- non-contiguous and cross-peer source selection through a Composition JSON file;
- normal body rendering of source text and image/video/audio/document media;
- multiple category IDs and tag IDs;
- manual excerpt;
- featured image selected from an image-bearing source;
- deterministic aggregate post slug and per-source media slugs;
- per-message duplicate detection through Core PublicationService;
- all sources linked to the same external WordPress post ID;
- atomic Bridge-owned aggregate composition state;
- safe post/media reconciliation after ambiguous writes;
- read-only category/tag listing and per-message usage inspection.

## Automated tests

- Source test run: `91 passed`
- Installed-wheel test run in a clean virtual environment: `91 passed`
- Python: `3.13.5`
- `pip check`: no broken requirements

Covered scenarios include:

- preservation of non-contiguous source order;
- one Draft created for multiple selected messages;
- body text/media ordering;
- multiple categories, tags, excerpt, and featured media payloads;
- already-used source blocking;
- partial-state recovery by deterministic slug;
- composition-key/source-list collision prevention;
- featured-source image validation;
- message-to-composition usage reporting;
- relative peer-file resolution;
- atomic composition-state persistence;
- WordPress category/tag parsing;
- CLI manifest loading and safe output.

## Clean installation

A clean virtual environment installed:

1. bundled `eitaa_core-0.6.0.dev15` wheel;
2. built `eitaa_bridge-0.5.0.dev1` wheel.

Results:

- Bridge product import: `0.5.0-wordpress-composer1`
- Bridge package import: `0.5.0.dev1`
- Core product import: `0.6.0-core7.4.1`
- Composer and JSON state-store imports: successful
- CLI `composer preview/status/publish`: present

## Doctor

Using a valid local validation session and configured non-secret WordPress placeholders:

- Bridge Doctor: `15/15`
- Core Doctor: `18/18`
- configuration schema: valid
- Core schema: `7`
- composition-state parent: writable
- publication workflow capability: present

No online write was performed against the user's WordPress site during package construction.

## Real Core/SQLite preview

Two non-contiguous text messages were saved through the public Core facade to a real Core SQLite database. The installed Bridge wheel then loaded a Composition JSON and completed `composer preview` successfully:

- outcome: `composition_preview`
- source count: `2`
- blocked source count: `0`
- ordered source IDs: `11795`, `11817`
- categories and tags preserved in the plan
- no WordPress write and no media download

## Boundary checks

Source scan results:

- no direct SQL statements or `sqlite3` use in Bridge;
- no import from `eitaa_core.infrastructure`, `eitaa_core.ports`, or Core application internals;
- no TL constructor, `messages.getHistory`, `upload.getFile`, or Eitaa wrapper implementation in Bridge;
- no Core wheel modification.

## Deliberate limitations

- Draft creation only; no automatic live publish;
- no automatic update of multi-message compositions;
- no source-reuse override;
- no tag/category creation;
- no destructive post/media cleanup;
- no UI, API server, queue, scheduler, or background worker;
- live WordPress composition publish should be confirmed by the user with their actual categories, tags, and selected media.
