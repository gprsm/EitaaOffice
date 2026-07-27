# GMI 4.2 Windows Acceptance Checklist

1. Extract into a fresh folder; do not overwrite GMI 4.1.
2. Run `install_app.bat`; confirm `ui\dist\.material-ui-v1` is created.
3. Run `run_doctor.bat` and then `EitaaBridge.bat`.
4. Confirm the whole document and MUI dialogs are RTL and Persian.
5. Test light, dark and system theme; right navigation remains black.
6. Resize at 360, 600, 768, 1024, 1366 and 1920 px; no horizontal overflow.
7. Open «مخاطبان ایتا» from the right menu; paging/search must not freeze.
8. Add one test contact to Eitaa and local storage; verify duplicate add creates no duplicate local record.
9. Import a small Excel/CSV/TXT twice, once local-only and once with «افزودن به ایتا» enabled.
10. In Target Contacts, select one category and verify only its union is visible; clear all categories and verify zero contacts are shown.
11. Remove a category tick and verify contacts exclusive to that category disappear immediately.
12. Send a non-sensitive text to a controlled test conversation from the quick-send box.
13. Send one small photo and one file; confirm staged files are removed from `runtime\uploads` afterward.
14. Switch image display mode; verify portrait images are fully visible in dynamic mode.
15. Rapidly switch conversations and scroll; avatars/media must remain lazy and no repeated storm should occur.
16. Verify person contacts without an available photo fall back to initials.
17. Confirm no template can send automatically; the template button is disabled.
