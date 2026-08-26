with open('docs/project-memory/VALIDATION_LEDGER.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_ledger = """
| 2026-08-21 | E.164 Identity Unmasking | Removed display_hint masking logic. Validated DB DPAPI decryption. | 	est_account_phone_identity_recovery_is_confirmed_backed_up_and_audited repaired. 590/590 |
| 2026-08-21 | AppUser Management UI | Converted AppUser creation into a Material UI <Dialog>. | 
pm run check passed. UI renders correctly. |
"""

content = content.replace("|------------|---------------------|----------------------------------------------------|---------------------------------------|\n", "|------------|---------------------|----------------------------------------------------|---------------------------------------|\n" + new_ledger)

with open('docs/project-memory/VALIDATION_LEDGER.md', 'w', encoding='utf-8') as f:
    f.write(content)
