# Migration Guide

## From v0.4 WordPress Update 1.2

Use a clean extracted v0.5 directory:

```bat
upgrade_from_wordpress_update1_2.bat "D:\path\to\eitaa_bridge_v0_4_wordpress_update1_2"
setup_venv.bat
run_tests.bat
run_doctor.bat
```

The upgrade script copies `bridge.json` and `.env`. The optional `bridge.composition_state_file` setting is backward-compatible; when absent it defaults to `data/bridge_compositions.json` beside `bridge.json`.

Existing v0.3/v0.4 one-message Core publication records are preserved. Those messages are considered already used by v0.5 and are blocked from a new composition unless the previous relationship is deliberately handled in a future migration tool.

No manual source merge is supported or required.


## v0.5 to v0.6

Use `upgrade_from_wordpress_composer1.bat`. The migration copies configuration, credentials, the current composition manifest, selected peer files, and Bridge composition state when present. No source merge or Core change occurs.

## v0.6 Application API 1 to v0.7 UI MVP 1.1

Run:

```bat
upgrade_from_application_api1.bat "D:\path\to\eitaa_bridge_v0_6_application_api1"
install_app.bat
```

The migration copies configuration, environment file, session, local data directory, composition file, selected peer files, and diagnostics. It does not copy the old virtual environment or merge source code.

## UI MVP 1.1 to UI MVP 2

Use a fresh extracted folder and run:

```bat
upgrade_from_ui_mvp1_1.bat "D:\path\to\eitaa_bridge_v0_7_ui_mvp1_1"
install_app.bat
```

The migration preserves user configuration, session, Core database, downloaded media, peer files, diagnostics and composition state. It intentionally does not copy `node_modules`, an old npm lockfile or a previous compiled UI. UI MVP 2 creates the persistent dialog catalogue under `data/ui-peers/catalog.json` and merges discovered/manual peers there.

## UI MVP 2 to UI MVP 3

Use `upgrade_from_ui_mvp2.bat`. The migration copies configuration, credentials environment file, Eitaa session, local database, persistent dialog catalogue, downloaded media, composition state, diagnostics and selected peer files. It intentionally does not copy `node_modules` or the old compiled renderer. Run `install_app.bat` to install from the public npm lock and build the Telegram-inspired UI.

## UI MVP 3 to UI MVP 4

Use a fresh extracted folder and run:

```bat
upgrade_from_ui_mvp3.bat "D:\path\to\eitaa_bridge_v0_7_ui_mvp3"
install_app.bat
```

The migration preserves user configuration, credentials, Eitaa session, local database, persistent dialog catalogue, downloaded media, composition state, diagnostics, selected peer files and an optional user-supplied IRANSans font. It intentionally does not copy `node_modules` or the old compiled renderer. MVP 4 installs daisyUI and React-Toastify from the public npm lock and rebuilds the UI.
