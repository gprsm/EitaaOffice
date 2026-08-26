# نقشهٔ معماری پروژه

## جریان اجرای محلی

```text
React Renderer
  │ authenticated API + correlation
  ▼
Electron preload / Browser bridge
  │ IPC (desktop) or HTTP (web)
  ▼
Electron main / HTTP interface
  │ dispatch
  ▼
Application API + AppUser authorization
  │ account-scoped command
  ▼
Account runtime / process supervisor
  │ worker IPC
  ▼
Provider adapter (Eitaa now, Bale next)
  │
  ├── account-scoped persistence/catalog
  ├── audit + structured diagnostics
  └── optional WordPress integration
```

## مرزهای اعتماد

```text
[Untrusted Browser Input]
        │ Host/Origin/CSRF/Auth/limits
        ▼
[HTTP Interface]
        │ actor + ownership
        ▼
[Application Boundary]
        │ account_id + capability
        ▼
[Isolated Account Worker]
        │ provider session
        ▼
[External Provider Network]
```

هر عبور باید validation، authorization، correlation و خطای امن داشته باشد. Reverse Proxy تنها در صورت trusted proxy contract حق تعیین scheme/client metadata دارد.

## مدل توسعهٔ Provider

```text
Provider catalog
  └── capabilities
      ├── authentication lifecycle
      ├── dialogs/contacts/members
      ├── send/read/media
      └── limits/error mapping
           │
           ▼
MessengerAccount instance
  ├── independent session
  ├── independent worker
  ├── independent storage scope
  └── independent retry/circuit/audit
```

جزئیات symbol/file به‌صورت ماشینی در `PROJECT_FILE_MAP.md` و `SYMBOL_INDEX.json` تولید می‌شود.
