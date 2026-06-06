"""Audit action taxonomy. Locked early so reports can filter by action type and
lifecycles are traceable. Use these constants — never ad-hoc action strings."""

# System lifecycle
SYSTEM_CREATED = "SYSTEM_CREATED"
SYSTEM_UPDATED = "SYSTEM_UPDATED"
SYSTEM_DELETED = "SYSTEM_DELETED"

# Evidence (Step 7)
EVIDENCE_INGESTED = "EVIDENCE_INGESTED"
EVIDENCE_SUPERSEDED = "EVIDENCE_SUPERSEDED"

# Assessment (Step 8)
ASSESSMENT_RUN = "ASSESSMENT_RUN"

# Entity types
ENTITY_AI_SYSTEM = "ai_system"
ENTITY_EVIDENCE = "evidence_item"
ENTITY_ASSESSMENT = "assessment"
