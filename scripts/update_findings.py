import re

with open('docs/project-memory/FINDINGS_REGISTER.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_finding = """
### UI & Backend: Unmasking Phone Numbers & Eitaa Account Display
- **Context:** The system historically masked Messenger Account phone numbers (e.g., +98***) in the SQLite database (display_hint) and strictly verified this in CoordinatorSchema.
- **Finding:** Masking phone numbers degraded the user experience in the MessengerAccountGate UI where users couldn't distinguish between their Eitaa accounts. Eitaa OTP login isn't strictly gated by this mask, but schema tests were.
- **Resolution:** Modified identity.py to stop masking, wrote a DPAPI script to decrypt and overwrite legacy masks in the DB, and stripped masking validation from contracts.py and store.py. (2026-08-21)

### UI: AppUser Creation Dialog
- **Context:** Admins could create new AppUsers via an inline form at the bottom of the Settings page.
- **Finding:** The inline approach lacked prominence and didn't match the "Add Messenger Account" UX flow.
- **Resolution:** Refactored AppUserManagementPanel.tsx to use an explicit Material UI <Dialog> triggered by a dedicated button for adding users. (2026-08-21)
"""

content = content.replace("## Active Engineering Tasks\n", "## Active Engineering Tasks\n" + new_finding)

with open('docs/project-memory/FINDINGS_REGISTER.md', 'w', encoding='utf-8') as f:
    f.write(content)
