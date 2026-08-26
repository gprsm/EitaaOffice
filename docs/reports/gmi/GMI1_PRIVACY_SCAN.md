# GMI 1 privacy scan

Result: **passed**

The clean release tree was scanned after build-cache removal.

- no `.env`;
- no `.eitaa_session.json`;
- no live `bridge.json`;
- no SQLite or other database;
- no log or JSONL diagnostic;
- no downloaded photo, video or media;
- no archive nested in the working release;
- no non-placeholder file under `data`, `runtime`, `diagnostics` or `backups`;
- no absolute user-profile path;
- no private-key marker, AWS-style access key or Iranian mobile-number pattern;
- no `.venv`, `node_modules`, pytest cache, Python bytecode, build tree or
  package egg-info.

Example configuration files, documentation references to forbidden filenames
and `.gitkeep` placeholders are intentional and contain no account data.
