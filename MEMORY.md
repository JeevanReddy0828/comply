# MEMORY — Decision Log

Permanent architectural facts and ratified decisions. Append, don't rewrite history.
The locked invariants live in CLAUDE.md; this captures the *why* behind changes.

## 2026-06-08 — Annex IV conformity report
- Backend assembles the report (owns evidence/hashes/audit); frontend only renders a print-ready page.
- Reconstructed by re-running `evaluate()` at the frozen `assessment.created_at` (invariant #8) so statuses + traced evidence are self-proving — NOT read from a denormalized store.
- Section→control map: `compliance/mappings/annex_iv_map.yaml` is **authoritative for controls**; `annex_iv_model.yaml` supplies labels/titles/fields only. (The two YAMLs disagree on feeding controls — map wins.)
- Watermark `DRAFT` unless every feeding control is `LEGAL_APPROVED` (nothing is today).
- `GET /systems/{id}/report` is read-only: no writes, no audit event (like `/compliance`).

## 2026-06-08 — control_hash backfill (catalog integrity)
- Controls inserted before migration 0006 had `control_hash = NULL`; the loader skips existing `(control_id, version)` rows on reload, so the hash never backfilled.
- Decision: loader backfills the hash **in place** when content is unchanged but hash is NULL (option b), using the existing canonicalization. Content-preserving, never bumps version, idempotent, self-heals on the startup catalog load. No data migration needed.

## 2026-06-08 — Remediation tasks (first operational loop)
- `RemediationTask` is a **first-class, audited, mutable** entity — task closures are NOT folded into the `ASSESSMENT_RUN` payload (keeps task history / SLA metrics / auditor evidence directly queryable on the task).
- **Invariant #4 reinterpreted (ratified):** "one business operation may emit *multiple* atomic, hash-chained audit events committed together." `run_assessment` emits `ASSESSMENT_RUN` + one `TASK_RESOLVED` per auto-closed task, all in one transaction.
- Auto-resolve terminal-state guard: only `OPEN`/`IN_PROGRESS` tasks are touched; `RESOLVED` is never reopened/re-resolved.
- One open task per `(system, control)` via a **partial unique index** `WHERE status <> 'RESOLVED'` — preserves resolved history so a control can regress later.
- `source_gap_reason` frozen at creation (NO_EVIDENCE | BELOW_MIN_SCORE | STALE) because live control state may no longer explain why the task was raised.
- Owner = existing org **User FK only** (no free-text/email). Statuses: `OPEN`/`IN_PROGRESS`/`RESOLVED` (minimal). `resolution`: `MANUAL` | `AUTO_SATISFIED`.
- New first-class capability `CAN_MANAGE_REMEDIATION` (Admin, ComplianceOfficer). Migration 0008 backfills it onto users created before the feature (capabilities are stored per-user).

## 2026-06-08 — Profile page
- `GET /auth/organization` returns the current user's org (name, created_at, member_count); auth-only, no special capability. Profile page is read-only (no edit/password change yet).

## 2026-06-08 — Ask → Control linking (framework-level)
- `GET /catalog/articles`: EU AI Act article → feeding controls, from the **article-level** `control_article_map.yaml` (NOT per-control `article_refs`, which are sub-article like `Art.14(1)`). Resolves to current controls, ordered by article number.
- Ask page detects article references (`/\bart(?:icle)?\.?\s*(\d+)/i`) in the question + answer + source citations, then renders the affected controls with review_status. The control linking is a catalog/DB concern, decoupled from the RAG/ML service.
- **Shipped framework-level only.** The system-aware overlay (a system picker → that system's gap status + open tasks + create-task action) is the next slice and needs the system-context decision.

## Release / process
- Shipped as 4 commits on `main`: reporting → catalog backfill → remediation → profile.
- Features built sequentially in one tree share files (`assessment.py`, frontend `api/*`, `SystemDetailPage.tsx`, `app.css`); when splitting commits, snapshot to a tag and verify `HEAD == snapshot` before merging.
- Branch hygiene: delete local+remote feature branches once fully merged with no planned follow-up.

## Deferred (do NOT build without a user/lawyer forcing it)
- **Next highest-ROI:** Ask → Control linking shipped (framework-level); the **system-aware overlay** (gap status + tasks for a selected system, with create-task action) is the next slice — needs the system-context decision.
- Task observability metrics (created/resolved/auto-resolved %/avg resolution time) — cheap now that every transition is an audit event.
- Evidence-as-documents = an architectural fork, not a feature: extend `EvidenceItem` with a content-hashed blob pointer for DOCUMENT-category evidence; do NOT build a separate document vault.
- Compliance Workspace page, profile editing, external integrations — wait for user pull.
