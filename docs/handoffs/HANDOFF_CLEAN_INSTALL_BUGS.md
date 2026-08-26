# AI Handoff / Project Status Report

**Project Name:** Eitaa Bridge (AntiGravity2)
**Context:** Creating a clean, standalone, portable version of the project for deployment (Fresh Install) and debugging authentication issues on a new system.

## 🚨 Problems Discovered During Fresh Install
During a fresh deployment (without existing session files, databases, and configuration), the application encountered two major crashing bugs:

### 1. UI Crash on Legacy Auth Mode
- **Trigger:** When `bridge.json` is missing, the system falls back to `bridge.example.json` where `multi_session.enabled = false`.
- **Bug:** The backend's legacy auth flow (`_auth_request_code_legacy` in `api.py`) returns a challenge summary without a `challenge_id` (unlike the account-scoped flow). However, the React frontend (`App.tsx` line ~235) strictly expects a `challenge_id` and throws the error *"شناسهٔ امن چالش ورود از سرویس دریافت نشد"* immediately, even though the OTP SMS is successfully sent.

### 2. Coordinator Crash on Empty Database
- **Trigger:** When `app_user_auth.enabled = true` and `multi_session.enabled = true`, but the `data` directory (SQLite databases) is completely missing.
- **Bug:** The backend fails to initialize the Coordinator and throws `"app_auth_coordinator_missing: AppUser authentication requires an initialized coordinator"`. This happens either because the backend/setup scripts do not automatically create the `data` directory, or because the Coordinator strictly expects the `legacy_default_messenger_account_id` to exist in the database and crashes when the DB is completely empty.

## 🛠️ Action Plan & Follow-up Tasks (To-Do)
The next AI assistant should focus on implementing the following fixes in the main project:

**Phase 1: Fixing the Backend & Installation Resiliency**
- [ ] **Directory Creation:** Update the backend startup logic (or `setup_venv.bat`) to automatically create the `data` directory if it does not exist (`os.makedirs(..., exist_ok=True)`).
- [ ] **Graceful Coordinator Init:** Modify the Coordinator initialization logic so that it can gracefully handle an empty database (e.g., ignore/warn if `legacy_default_messenger_account_id` is missing, rather than crashing).
- [ ] **Legacy Auth Compatibility:** In `api.py` (`_auth_request_code_legacy`), inject a locally generated UUID as `challenge_id` into the returned summary so the frontend doesn't crash on single-session mode.

**Phase 2: Fixing the Frontend (UI)**
- [ ] **Challenge ID Handling:** Update `ui/src/App.tsx` to handle authentication flows safely even if `challenge_id` is absent, or align the frontend types with the backend's legacy response payload.

**Phase 3: Creating a Standard Setup executable**
- [ ] **Installer Generation:** Write an `Inno Setup` script (`.iss`) or configure `electron-builder` in `package.json` to package the Node UI, Python wheels (`vendor` & `dist`), and batch scripts into a single `Setup.exe`.
- [ ] **Post-Install Hooks:** Ensure the installer automatically creates required folders (`data`, `runtime/logs`, `backups/runtime`) and silently executes `setup_venv.bat /silent` during installation.
