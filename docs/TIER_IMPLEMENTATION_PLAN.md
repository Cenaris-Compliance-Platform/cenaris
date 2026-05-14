# Cenaris Tier Implementation Plan

Last updated: 2026-05-13

## Goals
- Close partial features to full production grade
- Ship missing beta-critical features safely
- Avoid breaking existing data

## Phase 1 - Plan Alignment and Gating (2-3 days)
- Map pricing tiers to plan codes or add a new plan tier
- Expand FEATURE_MIN_PLAN for every feature in the matrix
- Add UI lock states and plan upgrade CTA

## Phase 2 - Policy Studio Completion (1-2 weeks)
- Add policy_drafts and policy_versions tables (done)
- Add version history UI (done)
- Add restore and export operations (restore done, export already existed)
- Add template library

## Phase 3 - Mapping and Evidence (1-2 weeks)
- Add clause-level requirements table
- Add clause evidence link table
- Add bulk/AI mapping suggestions

## Phase 4 - Audit Readiness and Exports (1 week)
- Add audit readiness view
- Add export evidence list to CSV/XLSX
- Add plan gating for exports

## Phase 5 - Review Schedules (1 week)
- Add review schedule table
- Add next-due calculation job
- Add dashboard calendar widget

## Phase 6 - Beta Missing Features (2-4 weeks)
Must-have:
-- Manual reminders (done)
-- Policy version control (done)
-- Audit/change log register (done, expand coverage)
-- Evidence expiry tracking (done)
-- User limits (free tier) (done, invite enforcement)

Should-have:
- Compliance calendar (read-only)
- Obligations register
- Risk register
- Owner accountability
- Auditor access portal

## DB Safety Rules
- Additive migrations only
- No column drops or renames
- Backfill with optional scripts
- Feature flags for new behaviors
