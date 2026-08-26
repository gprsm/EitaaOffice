# Account Management UI and Unmasking Report
**Date:** 2026-08-21
**Phase:** 6 (UI Improvements & Feature Refinements)

## Overview
This report details the modifications made to the Messenger Account and AppUser Management sections. The changes address explicit phone number display (removing legacy masking), Eitaa branding in the UI, and an improved modal-based flow for AppUser creation.

## 1. Unmasking Messenger Account Phone Numbers
### Concept & Rationale
Previously, Eitaa Bridge masked phone numbers upon onboarding (e.g., `+98912***67`). This masking was statically stored in the `display_hint` column of the `phone_accounts` SQLite table and enforced throughout the system (e.g., during DPAPI key recovery). For better usability, the explicit phone number must now be displayed.

### Code & File Changes
- **`src/eitaa_bridge/infrastructure/coordinator/identity.py`**
  - Modified `masked_phone()` function to bypass masking and return the full canonical E.164 phone number.
- **Database Migration (`data/coordinator/coordinator.sqlite3`)**
  - Executed a one-off automated runtime script utilizing `WindowsDpapiPhoneProtector` to decrypt all existing `phone_ciphertext` DPAPI blobs and overwrite the masked `display_hint` column with explicit phone numbers.
- **`src/eitaa_bridge/infrastructure/coordinator/store.py`**
  - Removed the schema validation constraint in `replace_messenger_account_phone_identity` and `bootstrap_legacy_account` that previously rejected unmasked hints (e.g., `len(hint_digits) > 2`).
- **`src/eitaa_bridge/providers/contracts.py`**
  - Removed `ProviderContactSummary` strict enforcement of masking characters (`*`, ``, `x`) for `identity_hint`.
- **`tests/test_coordinator_schema.py` & `tests/test_phase11b2_provider_neutral_orchestration.py`**
  - Removed outdated test assertions (`test_bootstrap_rejects_display_hint_with_too_many_digits`, `test_phone_mask_never_contains_the_full_number`) that expected strict phone masking.

## 2. UI: Eitaa Branding on Account Cards
### Concept & Rationale
In the `SettingsPage`, users need a clear visual indicator for the Messenger Account's provider. A styled Eitaa brand icon was added to complement the newly unmasked phone number.

### Code & File Changes
- **`ui/src/MessengerAccountGate.tsx`**
  - Adjusted the `AccountCard` component.
  - Added an inline `<Box>` styled as a circular orange Eitaa logo (color: `#f26522`, letter 'e') in a row alongside `account.phone_hint`.

## 3. UI: Add AppUser (حساب کاربری نرم‌افزار) Flow
### Concept & Rationale
Administrators need an intuitive flow to create new multi-session users (`AppUser`). The existing inline creation form at the bottom of the management panel was not prominent enough and lacked standard UI isolation.

### Code & File Changes
- **`ui/src/AppUserManagementPanel.tsx`**
  - Replaced the inline `<form>` with a prominent `افزودن حساب کاربری (AppUser)` outlined button.
  - Implemented a Material UI `<Dialog>` containing the user creation form (`DisplayName`, `Username`, `Password`, and `Role`).
  - Adjusted state logic (`createDialogOpen`) to automatically close the dialog upon successful user registration and display the success alert.

## Validation Results
- **TypeScript:** `npm run check` completed with 0 errors.
- **Python Backend:** `pytest` executed completely (`590/590`), confirming DPAPI functionality and new schema rules are robust.

## Status
All UI and backend logic associated with this step are implemented, stable, and integrated into the `master` branch workflow.
