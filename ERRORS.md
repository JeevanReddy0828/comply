# ERRORS — Failure Log

Failures hit and how they were resolved, so they aren't re-debugged from scratch.

## 2026-06-08 — API 404s from a stale running backend
- **Symptom:** new endpoints (`/systems/{id}/report`, `/auth/organization`) returned 404 / route missing while the assessment run returned 201.
- **Cause:** the uvicorn process on :8000 was started before the code changes (or had been reaped and restarted on old code). The route simply wasn't loaded.
- **Fix:** restart the backend after backend changes. Kill the listener then relaunch:
  `Get-NetTCPConnection -LocalPort 8000 -State Listen | %{ Stop-Process -Id $_.OwningProcess -Force }`, then `uvicorn app.main:app --port 8000`.
- **Standing note:** this dev box reaps background processes & Docker when idle — backend/ml-service/Postgres often need restarting at the start of a session, and after any backend edit.

## 2026-06-08 — control_hash NULL in the dev DB (passed tests, broke demo)
- **Symptom:** Annex IV report and `assessment_results.control_hash` showed blank hashes in the live demo, but the 50+ backend tests passed.
- **Cause:** the test DB is recreated fresh each run (hashes populated on insert); the live `comply` DB had 30 controls inserted before migration 0006, and the loader skips existing rows → hashes stayed NULL. Tests masked a live-data drift.
- **Fix:** loader now backfills NULL hashes on reload; ran the loader once against the live DB (30 rehashed, 0 remaining).
- **Lesson:** green tests on a fresh DB don't prove the live/seeded DB is correct — verify against the actual demo data for data-state issues.

## 2026-06-08 — eslint `react-hooks/set-state-in-effect`
- **Symptom:** lint error calling an async `refreshTasks()` (which wraps `setState`) synchronously inside `useEffect`.
- **Fix:** use the existing promise-chain pattern in the effect — `api.listTasks(id).then(setTasks).catch(...)` — and keep the `useCallback` helper for event handlers only.

## 2026-06-08 — stale Vite HMR "Failed to reload" console errors
- **Symptom:** `[vite] Failed to reload /src/...tsx` errors pile up in the preview console.
- **Cause:** HMR tried to hot-swap files that were saved mid-edit (transiently inconsistent). They persist in the console buffer.
- **Fix / how to tell it's noise:** `npm run build` (tsc + vite) passing is the source of truth; restart the dev server (`preview_stop` + `preview_start`) or full-reload to clear the buffer. Don't chase them as runtime defects.

## 2026-06-08 — splitting intermingled uncommitted work into clean commits
- **Symptom:** three features built in one working tree shared 5 files; a clean per-commit split needed hunk-level separation, which `git add -p` can't do non-interactively here.
- **Fix:** commit everything to a throwaway snapshot tag, `reset --hard main`, rebuild each commit by `git checkout <snap> -- <files>` and stripping the other feature's hunks per shared file, then verify `git diff snap HEAD` is empty before merging. The empty diff guarantees the merged result equals the tested state.
