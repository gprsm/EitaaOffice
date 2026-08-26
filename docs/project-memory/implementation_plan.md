# UI Optimization and Refactoring Plan

> وضعیت در 2026-08-25: این برنامهٔ توسعه‌ای تا پایان تثبیت `F-039` تا `F-044` در حالت `DEFERRED` است. مرجع اجرایی جاری [برنامهٔ جامع تثبیت و رفع اشکال](STABILIZATION_REMEDIATION_PLAN_2026-08-25.md) و [دفتر اجرای آن](STABILIZATION_EXECUTION_LOG.md) است. هیچ Phase توسعه‌ای این سند نباید پیش از دستور صریح کاربر و بسته‌شدن اهداف تثبیت آغاز شود.

This document outlines the multi-phase execution strategy to systematically optimize, modularize, and enhance the Eitaa Bridge UI, adhering strictly to a mobile-first philosophy and Material UI standards.

## Phase 1: Architectural Modularization (`App.tsx` Refactoring)
**Goal:** Dismantle the monolithic `App.tsx` (which has grown to ~211KB and contains thousands of lines of logic) to improve maintainability and resolve any perceived or actual linter/TypeScript errors.
- **Actions:**
  - Extract major sections (e.g., Auth flow, Main Dashboard, Media Viewer) into separate isolated React components.
  - Implement React Contexts or a state management structure to decouple business logic from rendering.
  - Ensure 100% type safety and zero errors in `npm run check`.
- **Validation:** Full application startup, testing navigation, and confirming zero regressions in functionality.

## Phase 2: UX Enhancements & Mobile-First Optimizations
**Goal:** Refine the user experience, focusing on responsiveness, active states, and latency compensation.
- **Actions:**
  - **Sidebar Active Color:** Modify the `&.Mui-selected` style in `ConversationListPage.tsx` (and `WorkspaceNavigation.tsx` if applicable) to use a neutral, subtle grey/contrast color instead of the default Material blue (`primary.main`) to provide a more elegant and professional feel on both desktop and mobile.
  - **Optimistic UI Updates:** Implement immediate state updates for actions like clicking the "Favorite" (Star) icon, so the UI reacts instantly without waiting for the backend disk write.
  - **Mobile Layout Audit:** Verify that touch targets, margins, dialog widths (`fullWidth maxWidth="sm"`/`fullScreen`), and bottom navigations are perfectly aligned with mobile-first standards.
- **Validation:** Visual verification on mobile viewports (via DevTools or manual review) and confirming the Star button reacts instantly.

## Phase 3: Indexing Section Upgrade
**Goal:** Address the disabled "Start Indexing" button and elevate the indexing feature into an independent, fully functional module.
- **Actions:**
  - Investigate the `canStart` state logic in `ContentIndexDialog.tsx` to determine why the button is currently disabled.
  - Refactor the indexing workflow to be more intuitive for mobile users.
  - Test the entire indexing pipeline from the UI down to the backend `POST /api/v1/content-index/start`.
- **Validation:** Successfully trigger an indexing job from the UI and verify its progress and completion.

---

### Execution Protocol
Each phase will be executed sequentially. No phase will begin until the previous phase is **100% complete, fully logged, tested, and validated**.
