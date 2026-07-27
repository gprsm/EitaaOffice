# Frozen Foundation 3 baseline plan

This historical document is retained to show the exact frozen baseline from which v0.2 was derived.

## Objective

Create an independent, installable middleware package that proves the frozen Core 7.4.1 dependency boundary and provides the minimum safe WordPress integration needed for later publication workflows.

## Decisions derived from the actual Core archive

1. Consume `eitaa-core==0.6.0.dev15`; do not copy its `src/eitaa_core` directory.
2. Require product version `0.6.0-core7.4.1` and schema 7.
3. Compose Core only with `EitaaCore.open(EitaaCoreConfig(...))`.
4. Reserve `target_type="wordpress"` and WordPress `site_key` for later use with `core.publications`.
5. Keep message hashing, `needs_update`, attempts, publication state, retrieval cursors, media download, and SQLite persistence in Core.
6. Keep WordPress credentials only in environment variables loaded from `.env`.
7. Bundle the unmodified Core Wheel as an installable dependency artifact, not as Bridge source.

## Foundation components

### Configuration

- schema-versioned JSON
- path resolution relative to the configuration file
- typed Core dependency settings
- typed WordPress site settings
- one active site in normal use, with `site_key`-scoped configuration ready for future expansion

### Security

- `.env` loader with no environment dump
- recursive redaction
- separate diagnostic files per component
- no request/response bodies, Authorization headers, credentials, message/post text, phone numbers, token, IMEI, access hash, or SQLite contents

### Core binding

- exact package/product version validation
- public facade field validation
- optional Core opening through public configuration
- Core Doctor and capability validation when a session is available

### WordPress adapter

- public site information
- authenticated user and permission test
- simple text Draft creation
- Basic Authentication with Application Password through `requests`
- bounded retry for network errors and temporary HTTP statuses
- typed safe errors without response-body leakage

### Operational interface

- `setup_venv.bat`
- `run_doctor.bat`
- `run_tests.bat`
- `run_wp_test.bat`
- `build_wheel.bat`
- console command `eitaa-bridge`

## Explicitly deferred

- WordPress media upload
- Featured Image
- publication state transitions against Core
- edited-message update workflow
- category/tag/author mapping
- FastAPI
- queue, worker, scheduler
- desktop UI
- multi-provider messaging abstraction
