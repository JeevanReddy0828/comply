# Comply

**AI-compliance automation for the EU AI Act.** Comply turns runtime evidence from AI
systems into EU AI Act conformity artifacts — the technical documentation a provider of a
high-risk system actually has to produce.

The thesis: compliance is non-discretionary spend (fines up to €15M / 3% of turnover under
the Act), so the product survives in any market. Positioned as "TurboTax for the EU AI
Act," with an initial wedge in HR-tech (Annex III Category 4 — the clearest high-risk
classification).

> **Status:** active development, `v0.5.0`. The control catalog is **provisional** —
> engineering interpretations of the Act text, not legal advice. No output is presented as a
> validated conformity claim; everything is watermarked **DRAFT** until a control passes
> legal review.

---

## The core idea

Regulation is modeled as a **graph of data, not code**:

```
Framework → Requirement → Control → EvidenceRequirement → EvidenceItem
```

A new framework (ISO 42001, NIST AI RMF) becomes a catalog entry — version-controlled YAML
reviewed like a knowledge base — not an engineering project. The backend loads that catalog
into graph tables and scores systems against it deterministically.

## What it does

- **Catalog** — the EU AI Act as 10 requirements / 30 controls / evidence requirements,
  plus article and Annex IV mappings. Version-controlled YAML; the DB is a queryable mirror.
- **Deterministic assessment** — scores a system against applicable controls at a frozen
  timestamp. Reproducible: re-evaluating with a stored timestamp reconstructs the identical
  result from the append-only log.
- **Immutable, hash-chained audit** — every business operation emits an audit event in the
  same transaction; the ledger is tamper-evident and `verify_chain` reports the first break.
- **Annex IV report** — the real deliverable: technical documentation assembled from a
  system's evidence, evidence-traced and control-hash-stamped, rendered print-ready (→ PDF).
- **Remediation workflow** — control gaps become owned, tracked tasks that **auto-resolve**
  (audited) when a re-assessment satisfies the control. The first complete operational loop:
  `assessment → gap → owner → evidence → re-assessment → auto-resolution → audit`.
- **Guard** (ML, advisory) — prompt-injection detection (regex + DeBERTa); a blocked attempt
  can be logged back into Comply as scored evidence.
- **Ask the Act** (ML, advisory) — RAG over the EU AI Act text + catalog, with citations and
  streamed answers.

## Architectural invariants

1. **Catalog is the source of truth; the DB is a mirror.** Content changes = edit YAML →
   re-run the loader. The API never edits controls.
2. **Controls are versioned, never mutated** — identity `(control_id, version)`; a content
   change bumps the version. Each carries a `control_hash` over its canonical content.
3. **Evidence is immutable** — pure inserts; superseding sets a pointer on the *new* row.
   Enforced by a DB-level append-only trigger.
4. **One business operation → audited, atomically** — `validate → write → append_event →
   commit`, hash-chained.
5. **Routers never touch ORM models directly** — strict `router → service → db → audit`, so
   audit emission and tenancy can't be bypassed.
6. **Tenant isolation in the service layer** — every cross-tenant lookup goes through
   `scoped_get(db, model, org_id, pk)`.
7. **Capabilities are first-class** — endpoints depend on `require_capability(can_x)`, never
   on a role string.
8. **Assessments are deterministic and reproducible** — frozen timestamp; each result stamps
   the exact `control_version` + `control_hash`, so a historical result is self-proving.

## Repository layout

```
compliance/    Version-controlled regulatory content (the catalog, as YAML)
               frameworks / requirements / controls / mappings / schemas / VERSION.yaml
backend/       FastAPI + SQLAlchemy 2.0 + Alembic + Postgres
               app/{models,schemas,routers,services} · migrations 0001–0008 · pytest (60)
frontend/      React 19 + Vite + TypeScript (plain CSS)
ml-service/    Isolated FastAPI ML subsystem (own venv, py3.12): Guard + RAG
scripts/       demo_journey.py (smoke test) · seed_demo.py (realistic demo)
```

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy 2.0 · Alembic |
| Database | PostgreSQL (driver `psycopg3`, `postgresql+psycopg://`) — JSONB + DDL-level append-only enforcement |
| Frontend | TypeScript · React 19 · Vite |
| ML service | FastAPI · FAISS retrieval · DeBERTa (Guard) · NVIDIA NIM (RAG generation) |
| Auth | JWT, capability-based RBAC (first user in an org = Admin) |
| Testing | pytest (backend, dedicated `comply_test` DB) · vitest (frontend) |

## Quickstart

**Prerequisites:** Docker, Python 3.14+, Node 20+.

```bash
# 1. Database (Postgres 16 on :5432, comply/comply/comply)
docker compose up -d

# 2. Backend  (http://localhost:8000)
cd backend
python -m venv venv && venv/Scripts/pip install -r requirements.txt   # Windows
venv/Scripts/alembic upgrade head        # apply migrations
venv/Scripts/python -m pytest tests/ -q  # 60 tests
venv/Scripts/uvicorn app.main:app --reload --port 8000   # catalog auto-loads on startup

# 3. Frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
# .env: VITE_API_URL=http://localhost:8000, VITE_ML_URL=http://localhost:8100

# 4. ML service (optional, http://localhost:8100)
cd ml-service
python -m venv venv && venv/Scripts/pip install -r requirements.txt
venv/Scripts/python -m app.rag.ingest    # build the FAISS index once
venv/Scripts/uvicorn app.main:app --port 8100
# RAG generation needs NVIDIA_API_KEY in ml-service/.env (retrieval-only without it)
```

Then open http://localhost:5173, register (first user becomes Admin), register a HIGH-risk
system, run an assessment, add evidence, and watch a gap flip to SATISFIED.

## Testing

```bash
cd backend  && venv/Scripts/python -m pytest tests/ -q   # 60 tests
cd ml-service && venv/Scripts/python -m pytest tests/ -q  # 6 tests
cd frontend && npm run lint && npm run build
```

## Project notes

- **Decision & failure logs:** `MEMORY.md` (architectural decisions) and `ERRORS.md`
  (failures + fixes) capture cross-session context. `CLAUDE.md` holds agent operating
  principles and the locked invariants.
- **Catalog is provisional** — `review_status` advances UNREVIEWED → NEEDS_LEGAL_REVIEW →
  LEGAL_APPROVED; nothing is LEGAL_APPROVED yet, so all conformity output is DRAFT.

_Private repository. Not legal advice._
