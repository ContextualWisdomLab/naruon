# Naruon 20B Responsive Product Design QA

Audit date: 2026-07-02 KST

## Scope

Surface audited: Naruon full-product buyer-review IA.

Routes:

```text
/, /mail, /search, /calendar, /tasks, /projects, /data, /ai-hub, /security, /settings
```

Viewports:

```text
desktop: 1440 x 1024
mobile: 390 x 844
```

Destination:

- Local screenshot evidence: `/tmp/naruon-full-product-responsive-qa/`
- Durable contact sheet: `docs/superpowers/reports/assets/2026-07-02-naruon-responsive-qa-contact-sheet.png`
- Figma destination: `68b5XB58w8nwT2LYOOnikK / QA Notes / Naruon 20B Responsive QA Evidence`
- Figma board node: `18:3`
- Figma contact-sheet image target node: `18:7`

## Command

```bash
NARUON_FULL_PRODUCT_SCREENSHOT_DIR=/tmp/naruon-full-product-responsive-qa \
NARUON_FULL_PRODUCT_VIEWPORTS=desktop,mobile \
pnpm --dir frontend run full:smoke
```

Result:

```text
Naruon full-product route smoke passed.
Routes: /, /mail, /search, /calendar, /tasks, /projects, /data, /ai-hub, /security, /settings
Viewports: desktop(1440x1024), mobile(390x844)
Critical interactions: desktop:mail:select-message, desktop:mail:create-source-linked-task, desktop:search:select-result, desktop:search:capture-sender-relationship, desktop:tasks:create-reply-sla-followup, desktop:settings:switch-ai-model-tab, desktop:settings:select-calendar-startup-view, mobile:mail:select-message, mobile:mail:create-source-linked-task, mobile:search:select-result, mobile:search:capture-sender-relationship, mobile:tasks:create-reply-sla-followup, mobile:settings:switch-ai-model-tab, mobile:settings:select-calendar-startup-view
Accessibility checks: home:a11y-basics, mail:a11y-basics, search:a11y-basics, calendar:a11y-basics, tasks:a11y-basics, projects:a11y-basics, data:a11y-basics, ai-hub:a11y-basics, security:a11y-basics, settings:a11y-basics, home:a11y-basics, mail:a11y-basics, search:a11y-basics, calendar:a11y-basics, tasks:a11y-basics, projects:a11y-basics, data:a11y-basics, ai-hub:a11y-basics, security:a11y-basics, settings:a11y-basics
```

Figma placement result:

```text
QA Notes board created and verified.
Contact-sheet upload accepted with response imageHash cd7f5034a2651ad47d6154f9053f2a43fd9c4522.
Figma node 18:7 verified with image fill hash cd7f5034a2651ad47d6154f9053f2a43fd9c4522 and FIT scale mode.
Verification screenshot confirmed the contact sheet and notes are visible inside board node 18:3.
```

## Evidence Files

Captured screenshot files:

```text
desktop-ai-hub.png
desktop-calendar.png
desktop-data.png
desktop-home.png
desktop-mail.png
desktop-projects.png
desktop-search.png
desktop-security.png
desktop-settings.png
desktop-tasks.png
mobile-ai-hub.png
mobile-calendar.png
mobile-data.png
mobile-home.png
mobile-mail.png
mobile-projects.png
mobile-search.png
mobile-security.png
mobile-settings.png
mobile-tasks.png
```

All desktop screenshots were verified at `1440 x 1024`. All mobile screenshots were verified at `390 x 844`.

## Findings

1. Desktop route and selected interaction coverage is now stable enough for buyer technical review.
   - Evidence: all ten IA routes render expected buyer-visible text and produce non-empty screenshots.
   - Interaction evidence: mail selection and source-linked task creation, search result relationship capture, task reply-SLA escalation, and settings tab/startup selection all passed.
   - Health: pass for route-level and selected interaction smoke.

2. Mobile route and selected interaction coverage is now stable enough for buyer technical review.
   - Evidence: all ten IA routes render expected buyer-visible text and produce mobile screenshots.
   - Interaction evidence: mail selection and source-linked task creation, search result relationship capture, task reply-SLA escalation, and settings tab/startup selection all passed on the mobile viewport.
   - Health: pass for route-level and selected interaction smoke.

3. Desktop and mobile accessibility basics now have repeatable smoke evidence.
   - Evidence: all ten IA routes passed visible duplicate-ID, visible interactive accessible-name, and keyboard Tab focus-entry checks on desktop and mobile.
   - Health: pass for basic automated accessibility smoke.

4. Mobile Settings had a responsive label wrapping defect before correction.
   - Evidence: `mobile-settings.png` initially showed `일정 관리` split awkwardly inside a narrow 3-column card.
   - Fix: `frontend/src/components/SettingsLayout.tsx` now switches the startup view selector from `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`.
   - Health: fixed and re-captured.

5. The smoke gate still does not prove full workflow completion.
   - Evidence: the command now checks expected route text, console errors, not-found states, screenshot creation, selected desktop/mobile interactions, and basic automated accessibility checks.
   - Remaining gap: send, writeback confirmation, graph expansion, permission edits, connector rotation, settings save persistence, and route-specific drawer/modal states need workflow-specific assertions before final procurement readiness.

## Accessibility Risks

- The current automated gate proves only three basic checks: no visible duplicate IDs, no visible interactive controls without accessible names, and keyboard Tab entry reaches a focusable element.
- It does not prove full keyboard order, focus trapping, screen-reader semantics, color contrast, zoom reflow, target size, or assistive-technology robustness.
- Bottom mobile navigation is visually present across routes; target-size and full focus-order verification remain unproven from screenshots and the basic gate alone.

## Product Design Assessment

The current branch now has repeatable desktop and mobile visual evidence for the ten buyer-review IA routes, selected desktop/mobile critical-interaction smoke evidence, and basic automated accessibility evidence across desktop and mobile. This moves the package from route-existence evidence to responsive route-level evidence with partial workflow and accessibility proof, but it does not prove full sale readiness.

The remaining Product Design P0/P1 work is:

1. Expand interaction-state coverage to the remaining important buyer flows:
   - mail reply draft and source drawer
   - search result source drawer and graph expansion
   - calendar writeback intent
   - task completion
   - project evidence opening
   - data quality action
   - AI Hub run/log detail
   - security permission review
   - settings save persistence and connector rotation
2. Expand accessibility evidence beyond the basic gate:
   - deterministic focus order for primary workflows
   - modal/drawer focus trapping
   - contrast sampling
   - screen-reader semantics for evidence drawers and workflow panels
3. Keep placing final screenshot evidence in Figma `QA Notes` after each accepted run.
4. Avoid claiming public launch or final procurement readiness until live provider, production deployment, rollback, support, security, and measured ROI evidence exist.
