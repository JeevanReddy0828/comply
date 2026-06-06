// Mirror of compliance/schemas/evidence_types.yaml (category + trust + default
// source), so the Add-Evidence form can offer the right concrete evidence types
// for a requirement's category. Trust scores are assigned server-side regardless;
// these drive sensible defaults and ordering only.

import type { EvidenceSource } from "../api/types";

export interface EvidenceTypeDef {
  id: string;
  label: string;
  category: "TELEMETRY" | "DOCUMENT" | "ATTESTATION" | "CONFIG";
  trust: number;
  defaultSource: EvidenceSource;
}

export const EVIDENCE_TYPES: EvidenceTypeDef[] = [
  { id: "human_override_event", label: "Human override event", category: "TELEMETRY", trust: 95, defaultSource: "AGENTWATCH" },
  { id: "telemetry_trace", label: "Decision trace (AgentWatch)", category: "TELEMETRY", trust: 90, defaultSource: "AGENTWATCH" },
  { id: "signed_otel_span", label: "Signed OTEL span", category: "TELEMETRY", trust: 90, defaultSource: "OTEL" },
  { id: "monitoring_snapshot", label: "Monitoring snapshot", category: "TELEMETRY", trust: 90, defaultSource: "AGENTWATCH" },
  { id: "otel_span", label: "OTEL span", category: "TELEMETRY", trust: 85, defaultSource: "OTEL" },
  { id: "incident_record", label: "Incident record", category: "ATTESTATION", trust: 80, defaultSource: "API" },
  { id: "signed_policy", label: "Signed policy / procedure", category: "ATTESTATION", trust: 75, defaultSource: "MANUAL" },
  { id: "training_record", label: "Training record", category: "ATTESTATION", trust: 60, defaultSource: "MANUAL" },
  { id: "config_declaration", label: "Configuration declaration", category: "CONFIG", trust: 70, defaultSource: "API" },
  { id: "manual_document", label: "Uploaded document", category: "DOCUMENT", trust: 40, defaultSource: "MANUAL" },
];

export const EVIDENCE_SOURCES: EvidenceSource[] = ["AGENTWATCH", "OTEL", "MANUAL", "API"];

/** Concrete types for a requirement category, best (highest trust) first. */
export function typesForCategory(category: string): EvidenceTypeDef[] {
  return EVIDENCE_TYPES.filter((t) => t.category === category).sort((a, b) => b.trust - a.trust);
}
