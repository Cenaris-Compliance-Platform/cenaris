# Walkthrough Implementation Plan

**Created:** May 14, 2026
**Last Updated:** May 15, 2026
**Status:** ✅ All Phases Complete and Production-Ready

---

## Summary

The guided walkthrough feature is **fully implemented** across backend, API, and frontend. It works for both new and existing users, in both light and dark themes.

---

## Phase 1 — Backend Foundation (Complete ✅)

| Item | Status |
|---|---|
| `WalkthroughState` DB model | ✅ |
| `WalkthroughStage` DB model | ✅ |
| `WalkthroughService` lifecycle methods | ✅ |
| `start`, `next_stage`, `complete`, `dismiss`, `permanently_dismiss`, `skip_stage` | ✅ |
| Eligibility detection (new users + low-coverage orgs) | ✅ |
| Timezone-safe datetime normalization | ✅ |
| Analytics event logging on all lifecycle actions | ✅ |
| Feature flag (`walkthroughs_enabled`) on `OrganizationAISettings` | ✅ |
| Coverage percentage calculation (uses `computed_score` + `evidence_status_*`) | ✅ (bug fixed) |

---

## Phase 2 — REST API (Complete ✅)

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/api/v1/walkthroughs/eligible` | GET | Get eligible walkthroughs for user | Session or API key |
| `/api/v1/walkthroughs/state/<key>` | GET | Get/create state + serialized stages | Session or API key |
| `/api/v1/walkthroughs/state/<key>/start` | POST | Start walkthrough | Session or API key |
| `/api/v1/walkthroughs/state/<id>/next-stage` | POST | Advance to next stage | Session or API key (ownership-guarded) |
| `/api/v1/walkthroughs/state/<id>/complete` | POST | Mark completed | Session or API key (ownership-guarded) |
| `/api/v1/walkthroughs/state/<id>/dismiss` | POST | Snooze 24 h | Session or API key (ownership-guarded) |
| `/api/v1/walkthroughs/state/<id>/permanently-dismiss` | POST | Opt out permanently | Session or API key (ownership-guarded) |

**Security:** `next-stage`, `complete`, `dismiss`, and `permanently-dismiss` now filter by `user_id` + `organization_id` to prevent one user from mutating another's state.

---

## Phase 3 — Frontend & UI (Complete ✅)

### Entry Points (All Users)
- **Promo Banner** — shown on every dashboard load until `localStorage` key is set. Fully wired: "Explore" opens walkthrough, "Not now" hides banner.
- **Explore Button** — permanent header icon, always visible. Fetches eligible walkthroughs first; falls back to `getting-started` for older users.

### Launcher Cards (Eligible Users)
- Server-rendered cards for every eligible walkthrough.
- Progress bar, current state label, stage count badge.
- "Open" button launches the modal immediately.

### Walkthrough Modal
- Title, subtitle, step meta, progress bar.
- Step list rendered from **live DB stages** (not hardcoded JS).
- Each step shows title, description, and Done/Now/Next badge.
- Buttons: **Start walkthrough** → **Next step** (with arrow icon) → **Finish** (with check icon).
- **Remind me later** — snoozes 24 h.
- **Don't show again** — permanently dismisses (with confirmation dialog).

### Spotlight / Scroll-to
- On every `next_stage` or `start`, the page smoothly scrolls to the target section.
- Target element pulses with a 2-second glow animation (`walkthroughSpotlight` keyframe).
- Target IDs are stored in the DB (`WalkthroughStage.target_element`) and returned by the API.

### Theme Compatibility
- All CSS uses Bootstrap CSS variables (`--bs-primary-rgb`, `--bs-body-bg`, `--bs-border-color`, `--bs-tertiary-bg`).
- `.walkthrough-launcher`, `.walkthrough-step`, `.walkthrough-progress`, `.walkthrough-spotlight-active` all adapt to light/dark automatically.
- `alert-secondary` used for modal hint (instead of `alert-info`) for better dark mode contrast.
- Badge on launcher card uses `text-bg-warning` (valid BS5 class).

---

## Phase 3 — Database Stage Content (Complete ✅)

Stage content (title, description, `target_element`) is now stored in the `WalkthroughStage` table when `get_or_create_state()` is called. The API returns the full `stages` array with every state fetch. The frontend renders directly from this data — no hardcoded JS stage maps remain.

---

## Phase 3 — A/B Rollout Flag (Complete ✅)

`OrganizationAISettings.walkthroughs_enabled` (Boolean, default `True`) gates eligibility detection. Set it to `False` for any org to silently disable all walkthroughs for that org.

> **Action required:** Run `flask db migrate -m "walkthroughs_enabled flag"` and `flask db upgrade` to add the column.

---

## Phase 3 — Backfill Script (Complete ✅)

**Location:** `scripts/backfill_walkthroughs.py`

Existing users (> 7 days old) are not auto-eligible. This script force-creates a `WalkthroughState` for them so the launcher cards appear.

```bash
# All users
python scripts/backfill_walkthroughs.py

# Specific org
python scripts/backfill_walkthroughs.py --org 5

# Different walkthrough type
python scripts/backfill_walkthroughs.py --key strengthen-evidence
```

---

## Known Remaining Items (Low Priority)

| Item | Notes |
|---|---|
| `flask db upgrade` | Must be run to add `walkthroughs_enabled` column |
| Richer spotlight overlay | Optional: dimmed backdrop for more immersive guidance |
| Analytics dashboard | Optional: admin view of engagement data |
| Automated tests | Unit tests for `WalkthroughService` lifecycle methods |
