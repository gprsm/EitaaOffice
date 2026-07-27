# Eitaa Bridge v0.7 UI MVP 5.3 Validation Report

## Release identity

- Product: `0.7.0-ui-mvp5.4`
- Python package: `0.7.0.dev10`
- UI package: `0.7.7`
- Core product: `0.6.0-core7.4.3`
- Core package: `0.6.0.dev17`
- SQLite schema: `8`

## Fixed defects

1. A remote `RpcError` or network failure during the harmless authentication probe no longer masquerades as `auth_session_open_failed`.
2. A local Session that opens successfully remains authenticated; a failed remote probe is reported as a non-destructive connectivity warning.
3. After explicit Session archival, the recovery component is unmounted immediately and a newly mounted Login Gate is displayed.
4. The phone input is explicitly editable (`disabled=false`, `readOnly=false`), receives focus, and no longer inherits stale recovery/busy state.
5. The reset endpoint verifies that the active Session path is absent and returns `login_ready=true`.

## Validation results

- Backend source tests: `125/125` passed.
- Installed Wheel tests in an isolated virtual environment: `125/125` passed.
- TypeScript strict check: passed.
- Vite production build: passed.
- Bridge Wheel built successfully: `eitaa_bridge-0.7.0.dev10-py3-none-any.whl`.
- Bundled Core Wheel remained `eitaa_core-0.6.0.dev17-py3-none-any.whl` and was not modified.
- No user Session, live database, credentials, diagnostic payloads, or downloaded avatars are included.

## Environmental limitation

The Electron binary download from GitHub was unavailable in the Linux validation environment. UI dependencies were therefore installed with `--ignore-scripts` for TypeScript and production-build validation. On the user's Windows system, `install_app.bat` performs the normal public-registry install and downloads Electron.
