# Accessibility Acceptance Runbook

## Purpose

This runbook defines the manual acceptance required before closing accessibility
work for the public v2 map. Playwright protects deterministic DOM, layout and
keyboard behavior, but it does not prove the reading order or announcements of
NVDA, Narrator or TalkBack.

Do not record a pass from automated checks alone.

## Scope

Validate the public route (`/`) at the release commit. The administrator route is
outside the current Issue #58 acceptance scope unless the release changes shared
layout or navigation code.

The acceptance covers:

- keyboard navigation and visible focus
- landmarks, headings and reading order
- filter labels and result announcements
- current-location success, denial and clear flows
- facility card, score rationale and report form navigation
- mobile reflow without clipped or overlapping content

## Required environments

Run at least one Windows screen reader and TalkBack. Record the exact versions.

| Environment | Required setup |
|---|---|
| NVDA | Windows 11, current Firefox or Chromium-based browser |
| Narrator | Windows 11, current Microsoft Edge |
| TalkBack | Android, current Chrome, portrait orientation |

NVDA and Narrator are separate evidence. A single Windows run does not count as
both. When a platform is unavailable, leave it unchecked and keep the tracking
issue open.

## Preflight

1. Verify the checkout is the intended release commit and the worktree is clean.
2. Start the frontend against a stable test API or the local v2 stack.
3. Run the deterministic frontend checks:

```bash
cd v2/frontend
npm install --no-audit --no-fund
npm run typecheck
npm run build
npm run test:ui
```

4. Use test data only. Do not include a home address, precise personal location,
   API key or other secret in screenshots, recordings or issue comments.
5. Reset browser zoom to 100% before the screen-reader pass. Run the separate
   reflow check at 200% zoom.

## Desktop keyboard and screen-reader procedure

Perform the following with NVDA and Narrator independently.

### 1. Entry and skip link

- [ ] The first `Tab` exposes and focuses "メインコンテンツへスキップ".
- [ ] `Enter` moves focus to the main content instead of only changing the URL.
- [ ] The page exposes one main landmark and one top-level heading.
- [ ] The management navigation is announced separately from the main content.

**Pass:** focus visibly moves to the main region and the screen reader announces
that region without repeating the whole page.

### 2. Search controls

Navigate forward using `Tab`, and backward using `Shift+Tab`.

- [ ] Search, prefecture, category, minimum score and minimum trust have distinct names.
- [ ] Wheelchair, changing table, free and 24-hour checkboxes announce name and state.
- [ ] The current-location button is reachable and its purpose is clear.
- [ ] Focus is never trapped in filters, cards, disclosure content or the map.
- [ ] Every focused interactive element has a visible focus indicator.

**Pass:** controls are announced in visual order, names are unambiguous, and the
user can leave every control with standard keyboard commands.

### 3. Result updates

- [ ] Changing one filter announces loading or the resulting count once.
- [ ] A zero-result response announces that no facilities matched.
- [ ] An API failure announces the failure and does not announce stale results as current.
- [ ] The result list is announced as "検索結果" and cards are exposed as list items.

**Pass:** the user receives one understandable status update per completed action,
with no rapid duplicate announcements.

### 4. Current location

Test success, permission denial and clear flows. Use a non-sensitive test location.

- [ ] Starting location lookup announces "現在地を取得中".
- [ ] Success announces that facilities within 10 km are shown in distance order.
- [ ] Permission denial announces the actionable permission message.
- [ ] After selecting "解除", the 10 km status is no longer announced or left visible.
- [ ] Focus remains on a predictable control after each action.

**Pass:** location state, visible text and API query state agree in all three flows.

### 5. Facility card and report form

- [ ] Facility name is announced before supporting metadata.
- [ ] Rated and unrated facilities are distinguishable without relying on color.
- [ ] Score rationale disclosure announces collapsed/expanded state.
- [ ] Equipment mentions are presented as source information, not guaranteed facts.
- [ ] Opening the report form exposes named issue-type and detail fields.
- [ ] Submit status is announced, and keyboard focus is not lost after completion or failure.

**Pass:** the card remains understandable when read linearly and the report flow
can be completed without pointer input.

## TalkBack procedure

Use Android Chrome in portrait orientation. Swipe navigation is the primary input;
repeat the action controls with an external keyboard when available.

- [ ] The page title and main heading are announced once.
- [ ] Filters follow the visual order and announce current values or checked state.
- [ ] Result count changes are announced after filters settle.
- [ ] The map is announced as a named region and does not trap swipe navigation.
- [ ] Facility cards remain grouped in a coherent reading order.
- [ ] Score rationale and report form controls expose role, name and state.
- [ ] Current-location success, denial and clear messages match the visible state.

**Pass:** all public search and report tasks are possible without touch exploration
of unlabeled controls.

## Mobile reflow and zoom

Run without a screen reader first, then repeat key navigation with the active
screen reader.

- [ ] 390 x 844 CSS pixels: no horizontal page scrolling.
- [ ] Guidance, freshness, quality metrics, badges and score rationale wrap inside the viewport.
- [ ] Report form fields and buttons remain fully visible.
- [ ] Desktop browser at 200% zoom: no clipped labels or overlapping controls.
- [ ] Text spacing changes do not hide content or controls.

Automated Playwright coverage is the regression gate for the 390 px layout. Manual
acceptance is still required for browser zoom, font rendering and screen-reader
interaction.

## Evidence template

Copy this section into Issue #58 or a dated report under `docs/rehearsals/`.

```text
Commit SHA:
Environment:
Browser and version:
Screen reader and version:
Input method:

Entry and skip link: PASS / FAIL / NOT RUN
Search controls: PASS / FAIL / NOT RUN
Result updates: PASS / FAIL / NOT RUN
Current location: PASS / FAIL / NOT RUN
Facility card and report form: PASS / FAIL / NOT RUN
Mobile reflow and zoom: PASS / FAIL / NOT RUN

Defects found:
Evidence links:
Tester:
Date:
```

Use `NOT RUN`, not `PASS`, when an environment or scenario was unavailable.

## Completion criteria

Issue #58 can be closed only when:

1. the frontend typecheck, production build and Playwright suite pass at the recorded commit;
2. NVDA or Narrator has passed every desktop scenario;
3. TalkBack has passed every mobile scenario;
4. the other Windows screen reader is either passed or explicitly tracked in a
   follow-up issue with a reason and owner;
5. all discovered severity-high accessibility defects are fixed and reverified;
6. evidence is attached without secrets or precise personal location data.

A failure creates a focused issue containing the environment, exact steps,
expected announcement, actual announcement and the smallest relevant evidence.
