# Comply — Compliance Graph Schema

**Artifact 1 of 7.** Defines the core data model. This is the stable spine every framework, report, integration, and dashboard is generated from.

Status: DESIGN. No ORM yet. These schemas describe version-controlled YAML content (`compliance/`) that the Week 2 backend will load and mirror into Postgres.

---

## The graph

```
Framework
  └── Requirement
        └── Control          ← the stable product asset
              └── EvidenceRequirement   (what satisfies the control)
                    ↑
              EvidenceItem    (runtime data, churns constantly)
```

Plus, attached to a registered system:

```
AISystem
  └── Assessment            (a point-in-time evaluation)
        └── AssessmentResult (per-control status + score)
```

And cross-cutting:

```
AuditEvent   (hash-chained ledger — see audit_ledger.md)
Approval     (human sign-off — data, not workflow, in v1)
```

---

## Node definitions

### Framework
A regulatory or standards framework. EU AI Act today; ISO 42001 / NIST AI RMF later — same engine.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `EU_AI_ACT` |
| `name` | string | "EU AI Act" |
| `version` | string | "Regulation (EU) 2024/1689" |
| `jurisdiction` | string | "EU" |
| `effective_dates` | map | keyed milestones, e.g. `high_risk: 2026-08-02` |
| `source_url` | string | canonical legal text |

### Requirement
A discrete obligation within a framework. Maps to one or more legal articles. Slow-changing.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `TRACEABILITY` |
| `framework` | string | FK → Framework.id |
| `name` | string | "Logging & Traceability" |
| `description` | string | plain-language obligation |
| `article_refs` | list | `[Art.12, Art.19]` |
| `applies_to` | list | risk tiers this requirement binds, e.g. `[HIGH_RISK]` |

### Control — the stable layer
A concrete, testable measure that (partly or wholly) satisfies one or more requirements. **This is the product moat.** Evidence churns; regulations shift occasionally; controls stay stable. Stored as self-contained YAML (one file per control) so each is independently portable across frameworks.

| Field | Type | Notes |
|---|---|---|
| `control_id` | string | `LOG_001` |
| `name` | string | "Decision Trace Retention" |
| `description` | string | what the control asserts |
| `frameworks` | list | `[EU_AI_ACT]` |
| `requirements` | list | `[TRACEABILITY]` |
| `article_refs` | list | `[Art.12]` |
| `annex_refs` | list | `[Annex IV Section 2]` |
| `evidence_requirements` | list | see below — drives gap engine + scoring |
| `confidence` | enum | `HIGH \| MEDIUM \| LOW` (interpretation certainty) |
| `review_status` | enum | `UNREVIEWED \| NEEDS_LEGAL_REVIEW \| LEGAL_APPROVED` |
| `version` | int | bump on any change |

### EvidenceRequirement
Embedded in a control. Declares what evidence satisfies it. The single block that drives classification, gap detection, scoring, and the Annex IV section.

| Field | Type | Notes |
|---|---|---|
| `type` | enum | `TELEMETRY \| DOCUMENT \| ATTESTATION \| CONFIG` |
| `field` | string | logical evidence key, e.g. `decision_trace` |
| `freshness` | duration | max age before stale, e.g. `7d` (Art.72 continuity) |
| `min_score` | int | minimum evidence trust score (0–100) to count |
| `required` | bool | hard requirement vs. supplementary |

### EvidenceItem — the churning layer
A concrete piece of evidence captured for a system. Never edited in place; superseded by newer items. Hashed for the audit ledger.

| Field | Type | Notes |
|---|---|---|
| `id` | string | uuid |
| `system_id` | string | FK → AISystem |
| `control_id` | string | which control it serves |
| `source` | enum | `AGENTWATCH \| OTEL \| MANUAL \| API` |
| `evidence_type` | enum | `TELEMETRY \| DOCUMENT \| ATTESTATION \| CONFIG` |
| `trust_score` | int | derived from source (see evidence scoring, Wk4) |
| `captured_at` | datetime | when the evidence was produced |
| `payload` | JSONB | the evidence itself |
| `hash` | string | sha256(payload) — feeds audit chain |

### AISystem
A registered AI system under assessment.

| Field | Type | Notes |
|---|---|---|
| `id` | string | uuid |
| `organization_id` | string | tenant |
| `name` | string | |
| `intended_purpose` | string | classifier input |
| `deployment_context` | string | classifier input |
| `risk_tier` | enum | `UNACCEPTABLE \| HIGH \| LIMITED \| MINIMAL` |
| `annex_iii_category` | string | nullable |
| `classification` | JSONB | full classifier output (tier, confidence, reasoning) |

### Assessment / AssessmentResult
A point-in-time evaluation of a system against its applicable controls.

`AssessmentResult` per control:

| Field | Type | Notes |
|---|---|---|
| `system_id` | string | |
| `control_id` | string | |
| `status` | enum | `SATISFIED \| PARTIAL \| MISSING` |
| `score` | int | weighted evidence score 0–100 |
| `freshness_grade` | enum | `A \| B \| C \| D` |
| `evidence_count` | int | items backing this result |
| `missing_requirements` | list | unmet EvidenceRequirements |
| `last_evaluated` | datetime | |

---

## Why control-centric, not article-centric

One control often satisfies multiple frameworks' requirements:

```
LOG_001 (Decision Trace Retention)
  ├── EU AI Act      → Art.12 / TRACEABILITY
  ├── ISO 42001      → A.6.2.8 (future)
  └── NIST AI RMF    → MEASURE 2.1 (future)
```

Article-centric modeling duplicates this control per framework. Control-centric modeling maps it once and references it many times. Adding a new framework becomes catalog data entry, not engineering.
