# Eitaa Bridge UI Architecture Map

## Current State Analysis (Monolithic Structure)
The UI is built with Vite, React, and Material UI (`@mui/material`), running in an Electron shell.
Currently, `ui/src/App.tsx` acts as a massive monolithic file (211KB, ~5000 lines) containing nearly all core views and state management logic.

### Core Components inside `App.tsx` (To be extracted):
- **`App` / `EitaaApp`**: Root providers, theming, and layout shells (`MobileShell`, `DesktopShell`).
- **`LoginGate` / `SessionRecovery`**: AppUser authentication flows.
- **`Workspace`**: The main dashboard handling the active `siteKey`, `dialogs`, and `messages` state.
- **`VirtualMessageList`**: Complex `@tanstack/react-virtual` list for rendering chat history, read receipts, and intersections.
- **`Composer`**: WordPress publishing integration, category/tag selection, and multi-message composition.
- **`BulkOperationsModal`**: Bulk messaging and member operations logic.
- **`CommunityMembersModal`**: Member lists and sync operations.

### Existing Modular Components:
- **`MessengerAccountGate.tsx`**: Manages Eitaa messenger onboarding, DPAPI unmasking, and Worker state.
- **`AppUserManagementPanel.tsx`**: Admin panel for creating local OS/App users.
- **`SettingsPage.tsx`**: Global and site-specific settings management.
- **`ContactDirectoryModal.tsx`**: Standalone modal for syncing Eitaa contacts.
- **`ConversationListPage.tsx`**: The left/bottom sidebar for rendering dialogs/channels.
- **`WorkspaceNavigation.tsx`**: The primary tab router (All, Channels, Groups, Favorites).

## Phase 1 Modularization Strategy
To improve productivity, modularity, and mobile-responsiveness, the following new directory structure will be created:

```text
ui/src/
├── components/
│   ├── auth/           # LoginGate.tsx, SessionRecovery.tsx
│   ├── chat/           # VirtualMessageList.tsx, MessageContentCard.tsx
│   ├── composer/       # Composer.tsx, BulkOperationsModal.tsx
│   ├── dialogs/        # CommunityMembersModal.tsx, ManualDialogModal.tsx
│   ├── layout/         # MobileShell.tsx, DesktopShell.tsx, Splash.tsx
│   └── shared/         # JalaliDatePicker.tsx, DialogAvatar.tsx, MaterialLegacyDialog.tsx
├── contexts/
│   ├── AuthContext.tsx       # Manages global AppUser session
│   └── WorkspaceContext.tsx  # Manages Dialogs, Messages, and SiteKey state
├── pages/
│   └── Workspace.tsx         # The main dashboard layout orchestrator
├── utils/
│   └── jalali.ts             # All Jalali calendar math and string parsers
├── App.tsx                   # Cleaned up root entry point
└── main.tsx
```

## Benefits of this Map
1. **Developer Productivity:** Smaller files mean faster IDE parsing and immediate TypeScript feedback.
2. **Reduced Errors:** Isolating `VirtualMessageList` prevents its complex intersection observer hooks from conflicting with `Workspace` state updates.
3. **Optimistic UI:** Context separation allows easier injection of immediate state changes (like the Star/Favorite fix).
4. **Mobile First:** Extracting `MobileShell` makes it easier to inject `100dvh` viewport fixes and touch-target safe areas without polluting desktop logic.
