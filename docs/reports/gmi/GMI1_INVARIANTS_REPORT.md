# GMI 1 invariants report

Baseline: accepted MVP 6.1.1 UI 3.3 ZIP.

## Byte-identical frozen logic

- Scroll math: identical.
- UI 3.3 reading-position/runtime patch: identical.
- Eitaa scheduler: identical.
- WordPress domain, service, workflow and client logic: identical.
- Runtime ownership, backup, restore, diagnostics and launch logic: identical.
- Installer definition, office payload and install/launcher logic: identical.

## Necessary identity-only changes

The following frozen-area integration files change only exact package/product
identity literals:

- `setup_venv.bat`: Core dev18 to dev19; Bridge dev25 to dev26;
- `BUILD_OFFICE_SETUP_EXE.bat`: the same two Wheel filenames;
- `scripts/check_runtime_environment.py`: exact distributions and product ID;
- `ui/electron/main.cjs`: expected Bridge product ID.

No control flow, command order, privilege boundary or recovery behavior changed
in those files.

## Intentional functional changes

- Core message decode/model/repository and schema migration;
- public local `messages.list_album` contract;
- Bridge album completion/serialization;
- message-list album rendering, search expansion and whole-album selection;
- UI production build finalization to preserve the accepted UI 3.3 runtime
  patch before the rebuilt main module.

## Confirmed exclusions

- no new Eitaa RPC;
- no Scheduler priority or worker change;
- no WordPress request/publish/update change;
- no Runtime ownership change;
- no Installer behavior change;
- no heuristic album inference;
- no production content-index implementation.

