# Comply — Audit Ledger Schema

**Artifact 2 of 7.** Tamper-evident record of every state change. Built Week 1 because it cannot be retrofitted honestly — any entity created before the chain exists has no provable integrity.

Status: DESIGN.

---

## Purpose

Compliance buyers ask one question above all others: *"Can someone modify evidence after the fact?"* The audit ledger answers "no, and here's the proof." Not blockchain. Simple hash chaining. The point is tamper **evidence**, not decentralization.

---

## `audit_events`

| Field | Type | Notes |
|---|---|---|
| `id` | string | uuid, monotonic insertion order |
| `actor` | string | user id or `system` for automated events |
| `action` | enum | `CREATE \| UPDATE \| SUPERSEDE \| APPROVE \| CLASSIFY \| INGEST` |
| `entity_type` | enum | `AI_SYSTEM \| EVIDENCE_ITEM \| ASSESSMENT \| CONTROL \| APPROVAL` |
| `entity_id` | string | the affected entity |
| `payload_hash` | string | sha256 of the entity snapshot at this event |
| `timestamp` | datetime | server time, UTC |
| `previous_hash` | string | `current_hash` of the prior event (genesis = `0`×64) |
| `current_hash` | string | sha256(`previous_hash` + `payload_hash` + `timestamp` + `actor` + `action` + `entity_id`) |

---

## Chain rule

```
current_hash = sha256(
    previous_hash +
    payload_hash +
    timestamp_iso +
    actor +
    action +
    entity_id
)
```

Each event commits to its predecessor. Altering any historical event breaks every `current_hash` downstream of it — detectable by re-walking the chain.

## Verification

A `GET /audit/verify` endpoint (Week 2) walks the chain from genesis, recomputes each `current_hash`, and confirms `previous_hash` linkage. Returns the first broken link if any, else `intact: true` with the chain length and head hash.

## What is NOT mutable

- `evidence_items` are never updated in place. New evidence **supersedes** old (a new row + a `SUPERSEDE` audit event referencing the prior item). This preserves the full history that the chain attests to.
- `audit_events` are append-only. No update, no delete — enforced at the DB layer (no UPDATE/DELETE grant on the table for the app role) in Week 2.

## Append discipline

Every write path that touches a graph entity emits exactly one `audit_event` in the same transaction. If the audit insert fails, the entity write rolls back. No silent state changes.
