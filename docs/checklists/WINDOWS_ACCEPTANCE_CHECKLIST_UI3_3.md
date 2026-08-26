# Eitaa Bridge UI 3.3 – Windows acceptance checklist

## Safe installation

1. Extract the ZIP into a new folder; do not overwrite the live UI 3.2 installation.
2. Close the previous application completely.
3. Run `install_app.bat`.
4. Confirm product `0.7.0-ui-mvp6.1.1-ui3.3` and Bridge package `0.7.0.dev25`.

## WordPress usage-state test

1. Open an existing WordPress composition.
2. Add one previously unused Eitaa message and update the same WordPress post.
3. Confirm the WordPress post ID does not change.
4. Confirm the newly added Eitaa message becomes red immediately.
5. Start a new composition and click the same message; it must not become selectable.
6. Close and reopen the application; the message must remain red and unavailable.
7. If verification fails, the form must not silently reset as though every source was committed.

## Unread-first test

1. Choose a dialog with several unread messages.
2. Open it and confirm the view settles around the unread separator rather than the newest message or an older remembered point.
3. Scroll elsewhere, switch dialogs, and return while unread messages still remain; unread remains the primary opening point.
4. Use “ادامه از آخرین موقعیت” to return to the remembered location when the marker is shown.

## Persisted reading-position test

1. Open a dialog with no unread messages.
2. Scroll to a recognizable group of messages and remain there for at least three seconds.
3. Close the application normally.
4. Reopen it and open the same dialog.
5. Confirm it returns approximately to the same message group without loading an excessive history.
6. Repeat with two different dialogs to confirm their positions remain independent.
7. Confirm ordinary scrolling does not create visible freezes or continuous network requests.

## Regression checks

- WordPress create, update, preview, and draft still work.
- Bulk member operations still work.
- UI 2 scroll remains smooth.
- Closing the application stops its Python processes.
- No automatic WordPress credential error appears at startup.

## Safe diagnostics if a test fails

Send only these files when present:

- `runtime/logs/launcher.log`
- `runtime/logs/server-console.log`
- `diagnostics/application.jsonl`
- `diagnostics/bridge.jsonl`

Do not send `.env`, session files, databases, downloaded media, or access hashes.
