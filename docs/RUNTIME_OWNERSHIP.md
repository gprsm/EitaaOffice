# Runtime ownership — MVP 6.1.1 Runtime 3

## دروازهٔ فعال‌سازی پیش از مالکیت Runtime

در نصب self-contained، Launcher پیش از `ensure_backend` وضعیت مجوز دستگاه را با process مستقل و بدون شبکه کنترل می‌کند. اگر مجوز وجود نداشته یا نامعتبر باشد، فقط پنجرهٔ فعال‌سازی اجرا می‌شود و Backend، Coordinator، Provider و Edge App شروع نمی‌شوند. اجرای مستقیم HTTP API نیز همان gate را پیش از Config/DB اعمال می‌کند؛ در نتیجه دورزدن Launcher مسیر عادی اجرای محصول را باز نمی‌کند.

پس از موفقیت، Launcher فقط reason code امن `license_activation_verified` را در log خود ثبت می‌کند و نه request code، fingerprint، activation code یا اطلاعات سخت‌افزاری. سپس قرارداد معمول Install ID/Owner Token/Heartbeat ادامه می‌یابد.

The lightweight Office launcher no longer trusts a service only because it answers on port 8765.

Each installation creates local private runtime files under `runtime`:

- `install-id.txt`: stable ID for this installation
- `backend-owner.token`: private owner token
- `backend-state.json`: PID, root, API/product versions and ownership metadata for the active backend
- `ui-state.json`: launcher and Edge process metadata
- `office-launcher.lock`: held while the owned Office window is active

The launcher reuses a backend only when the protected runtime identity endpoint confirms all of the following:

- runtime protocol
- API version
- Bridge product version
- install ID
- canonical installation root
- valid owner token

A foreign or incompatible service is reported as a conflict. It is never stopped automatically.

## Shutdown policy

The Office launcher sends an authenticated shutdown request when the owned Edge application window closes. It also sends a heartbeat while the UI is alive. Edge may hand the app window from the initially spawned process to another process in its private profile; the launcher therefore tracks the visible owned window across PID handoffs instead of treating the first PID as the lifetime of the UI. If the launcher crashes and heartbeats stop, the owned backend shuts itself down after the configured grace period.

`stop_eitaa_bridge.bat` uses the same ownership handshake. If the endpoint is unavailable, it may stop a legacy process only after parsing its command line and matching an absolute config or UI path exactly. Prefix-like sibling paths such as `EitaaBridge-Backup` are rejected. It never enumerates or kills a process by port.

## Installer policy

`install_app.bat` stops only an owned runtime and skips package installation when the existing environment exactly matches the bundled versions and passes import/timezone checks.

`repair_app.bat` is the explicit recovery path that performs force-reinstallation after the owned runtime has stopped. The self-contained Office installer carries an application-local Python runtime and does not require a system Python or Node.js installation. It mirrors only generated code directories (`python`, `python-packages`, `dist`, `vendor`, `scripts`, `docs`, and `ui`) and preserves runtime data, configuration, sessions, media, diagnostics, and backups. Shareable Setup builds exclude the build computer's live configuration, session, databases, media, diagnostics, logs, and backups by construction.
