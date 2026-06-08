// Mirrors the backend Pydantic schemas (backend/app/schemas/*). Keep in sync.

export interface User {
  id: string;
  org_id: string;
  email: string;
  name: string;
  role: string;
  capabilities: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AISystem {
  id: string;
  org_id: string;
  name: string;
  intended_purpose: string;
  deployment_context: string;
  risk_tier: string | null;
  annex_iii_category: string | null;
  classification: Record<string, unknown> | null;
  created_at: string;
}

export interface SystemCreate {
  name: string;
  intended_purpose?: string;
  deployment_context?: string;
  risk_tier?: string | null;
  annex_iii_category?: string | null;
}

export type EvidenceSource = "AGENTWATCH" | "OTEL" | "MANUAL" | "API";

export interface EvidenceCreate {
  control_id: string;
  field: string;
  source: EvidenceSource;
  evidence_type: string;
  captured_at: string; // ISO 8601
  payload?: Record<string, unknown>;
  supersedes?: string | null;
}

export interface Evidence {
  id: string;
  system_id: string;
  control_id: string;
  field: string;
  source: string;
  evidence_type: string;
  trust_score: number;
  validity_state: string;
  captured_at: string;
  ingested_at: string;
  supersedes: string | null;
  hash: string;
  payload: Record<string, unknown>;
}

export type ControlStatus = "SATISFIED" | "PARTIAL" | "MISSING";

export interface MissingRequirement {
  field: string;
  type: string;
  reason: "NO_EVIDENCE" | "INSUFFICIENT" | string;
  detail: "STALE" | "BELOW_MIN_SCORE" | null;
}

export interface ControlWarning {
  field: string;
  type: string;
  warning: string;
}

export interface ControlResult {
  control_id: string;
  control_version: number;
  status: ControlStatus;
  score: number;
  freshness_grade: string | null;
  evidence_count: number;
  missing_requirements: MissingRequirement[];
  warnings: ControlWarning[];
}

export interface Compliance {
  system_id: string;
  assessment_id: string;
  assessment_timestamp: string;
  catalog_version: string;
  applicability: "APPLICABLE" | "NOT_APPLICABLE";
  system_score: number | null;
  counts: { SATISFIED: number; PARTIAL: number; MISSING: number };
  results: ControlResult[];
}

export interface ReportEvidence {
  id: string;
  field: string;
  evidence_type: string;
  source: string;
  trust_score: number;
  captured_at: string;
  hash: string;
}

export interface ReportControl {
  control_id: string;
  control_version: number;
  control_hash: string | null;
  name: string;
  status: ControlStatus;
  score: number;
  review_status: string;
  confidence: string;
  missing_requirements: MissingRequirement[];
  evidence: ReportEvidence[];
}

export interface ReportSection {
  section: number;
  title: string;
  content_source: string | null;
  fields: string[];
  controls: ReportControl[];
}

export interface ReportSystem {
  id: string;
  name: string;
  intended_purpose: string;
  deployment_context: string;
  risk_tier: string | null;
  annex_iii_category: string | null;
}

export interface AnnexIVReport {
  system: ReportSystem;
  applicability: "APPLICABLE" | "NOT_APPLICABLE";
  assessment_id: string;
  assessment_timestamp: string;
  catalog_version: string;
  generated_at: string;
  system_score: number | null;
  counts: { SATISFIED: number; PARTIAL: number; MISSING: number };
  watermark: string; // DRAFT | LEGAL_APPROVED
  note: string | null;
  sections: ReportSection[];
}

export type TaskStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED";

export interface RemediationTask {
  id: string;
  org_id: string;
  system_id: string;
  control_id: string;
  status: TaskStatus;
  owner_id: string | null;
  due_date: string | null;
  notes: string;
  source_gap_reason: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution: "MANUAL" | "AUTO_SATISFIED" | null;
}

export interface TaskCreate {
  control_id: string;
  owner_id?: string | null;
  due_date?: string | null;
  notes?: string;
}

export interface TaskUpdate {
  status?: TaskStatus;
  owner_id?: string | null;
  due_date?: string | null;
  notes?: string | null;
}

export interface ControlSummary {
  control_id: string;
  version: number;
  name: string;
  confidence: string;
  review_status: string;
  frameworks: string[];
  article_refs: string[];
  annex_refs: string[];
  requirements: string[];
}

export interface EvidenceRequirement {
  type: string;
  field: string;
  freshness_seconds: number | null;
  min_score: number;
  required: boolean;
}

export interface ControlDetail extends ControlSummary {
  description: string;
  catalog_version: string;
  evidence_requirements: EvidenceRequirement[];
}
