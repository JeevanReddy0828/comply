# Comply — Review & Confidence Methodology

**Artifact 7 of 7.** Defines what `confidence` and `review_status` mean on every control, who can change them, and the rule that keeps "implemented in the platform" strictly separate from "legally validated."

This is the artifact that lets engineering move at full speed without hard-coding unreviewed legal interpretation as truth.

---

## The two-axis model

Every control carries two independent metadata axes. They must never be conflated.

### Axis 1 — `confidence` (interpretation certainty)
*How certain are we that this control correctly captures the regulatory obligation?*

| Value | Meaning |
|---|---|
| `HIGH` | The Act states this obligation explicitly; mapping is near-verbatim. |
| `MEDIUM` | Reasonable interpretation; the Act implies it but wording leaves room. |
| `LOW` | Inferred or anticipatory; depends on forthcoming harmonized standards/guidance. |

### Axis 2 — `review_status` (validation state)
*Has a qualified human validated this control's interpretation?*

| Value | Meaning |
|---|---|
| `UNREVIEWED` | Drafted by engineering from the Act text. No legal eyes yet. **Default.** |
| `NEEDS_LEGAL_REVIEW` | Flagged for review — typically `confidence: LOW/MEDIUM` or contested. |
| `LEGAL_APPROVED` | A qualified reviewer has signed off. Only this status may back customer-facing conformity claims without a disclaimer. |

---

## The hard rule

> **No control may back a customer-facing conformity claim as "validated" unless `review_status == LEGAL_APPROVED`.**

Controls below that bar still function — they drive the dashboard, gap detection, and draft documentation — but generated output derived from them is watermarked **DRAFT — pending legal review**. This keeps the platform useful on day one while making every unreviewed regulatory assumption explicit and auditable.

---

## Provisional catalog policy (Option 3)

The initial catalog is **provisional by design**. Engineering drafts controls directly from the Act text so the platform can be built; legal validation happens in parallel and lands as `review_status` updates — a row change, never a refactor.

Seeding defaults:
- Every newly drafted control starts `review_status: UNREVIEWED`.
- Any control with `confidence: LOW` is auto-set `NEEDS_LEGAL_REVIEW`.
- `confidence: MEDIUM` controls touching automated decisions or biometrics are flagged `NEEDS_LEGAL_REVIEW`.

## Who can change what

| Action | Allowed role |
|---|---|
| Draft / edit a control (raise to UNREVIEWED) | Engineering |
| Set `NEEDS_LEGAL_REVIEW` | Engineering, Compliance Officer |
| Set `LEGAL_APPROVED` | Compliance Officer (qualified reviewer) only |

Every `review_status` transition emits an `audit_event` (`action: UPDATE`, `entity_type: CONTROL`) — so the validation history of the regulatory content is itself tamper-evident.

## Versioning

Any change to a control's `description`, `evidence_requirements`, `article_refs`, or `annex_refs` **must** bump `version` and reset `review_status` to `NEEDS_LEGAL_REVIEW` (a prior approval no longer applies to changed content). Confidence may be adjusted in the same change.

## Disclaimer surface

Generated documents state, per control used:
- `LEGAL_APPROVED` → no disclaimer
- anything else → "DRAFT — this section relies on controls pending legal review"

This is the contractual firewall between *"Comply implemented a control"* and *"this is legally validated compliance."* It is non-negotiable and predates the first customer.
