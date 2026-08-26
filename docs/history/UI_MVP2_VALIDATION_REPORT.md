# Eitaa Bridge v0.7 UI MVP 2 — Validation Report

## Baseline

- Product: `0.7.0-ui-mvp2`
- Python package: `0.7.0.dev3`
- Core product: `0.6.0-core7.4.1`
- Core package: `0.6.0.dev15`
- Core schema: `7`

## Implemented scope

- persistent Bridge-owned dialog catalogue;
- background and manual multi-page dialog synchronization;
- manual peer addition by username or technical peer identity;
- persistent favorite and display-type override;
- explicit group/channel correction without changing the Core peer type;
- images rendered above message text;
- checkbox-based multi-category selection;
- multi-tag selection and WordPress tag creation;
- current WordPress metadata retrieval for editing;
- in-place update of the same multi-message WordPress Post ID;
- daisyUI component classes layered over the custom responsive messenger shell.

## Automated validation

- Source test suite: `117 passed`
- Installed-wheel test suite: `117 passed`
- Python source compilation: passed
- TypeScript strict build check: passed
- Vite production build: passed
- Bridge wheel import: `0.7.0-ui-mvp2`
- Core wheel import: `0.6.0-core7.4.1`

The Vite build was validated in the isolated build environment with a local CSS-resolution stub because that environment cannot resolve the public npm registry. JavaScript/TypeScript, Vite bundling and the application CSS were built successfully. The distributable does not ship the stub or `node_modules`; `install_app.bat` installs the real pinned `daisyui@5.6.18` package from the public npm registry and rebuilds the UI on the user's machine.

## New test coverage

- persistent manual group classification and favorites;
- remote refresh preserving a locked group/channel override;
- manual dialog API and validation;
- favorite and display-kind API actions;
- WordPress tag reuse and creation;
- editable WordPress post metadata endpoint;
- image-before-text body rendering;
- same-Post-ID composition update;
- update rejection when the source-message set changes.

## Architectural checks

- Frozen Core wheel SHA-256 is unchanged.
- No `sqlite3` import in Bridge.
- No direct SQL statements in Bridge.
- No import from Core infrastructure, protocol, storage or internal modules.
- No Eitaa protocol constructors in Bridge.
- Electron renderer uses `contextIsolation: true`, `nodeIntegration: false`, and sandboxing.

## Doctor result in sanitized build environment

All structural checks passed: Python version, configuration schema, HTTPS policy, Core version and schema, public facade, writable paths, API, Electron manifest, production UI build and publish confirmation. The sanitized validation environment intentionally lacked a real Eitaa session and WordPress credentials, so those three environment-specific checks were expected to fail. They are supplied by the upgrade script on the user's system.

## Live-write status

No public WordPress post was created or updated during package validation. Automated fakes verify same-ID update behavior, categories, tags, featured media, post status and collision blocking. The user's existing WordPress connection remains the acceptance environment.

## Known limitation

The frozen Core public dialog model does not expose enough metadata to distinguish every protocol-level channel from a supergroup, and server pagination can repeat or stop. UI MVP 2 handles this conservatively with a persistent catalogue, pagination-stall warnings, manual addition and a locked display-type override. It does not modify Core or guess a peer's technical identity.
