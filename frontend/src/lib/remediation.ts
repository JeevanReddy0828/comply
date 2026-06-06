// Translate the engine's machine reasons into plain language a compliance buyer
// can act on. The raw enum stays available underneath for the technical reader.

import type { MissingRequirement } from "../api/types";

const TYPE_NOUN: Record<string, string> = {
  TELEMETRY: "runtime telemetry",
  DOCUMENT: "a document",
  ATTESTATION: "a signed attestation",
  CONFIG: "a configuration record",
};

export function humanizeField(field: string): string {
  return field.replace(/_/g, " ");
}

function typeNoun(type: string): string {
  return TYPE_NOUN[type] ?? type.toLowerCase();
}

export interface Remediation {
  /** What is missing — short, plain. */
  what: string;
  /** Why the control is failing on this requirement. */
  why: string;
  /** The concrete next action. */
  next: string;
  /** The raw engine reason, for the technical reader. */
  technical: string;
}

export function remediationFor(m: MissingRequirement): Remediation {
  const field = humanizeField(m.field);
  const noun = typeNoun(m.type);
  const technical = m.detail ? `${m.reason} / ${m.detail}` : m.reason;

  if (m.reason === "NO_EVIDENCE") {
    return {
      what: `Missing ${noun} for ${field}.`,
      why: `No evidence of "${field}" has been provided yet.`,
      next: `Add ${noun} demonstrating ${field}.`,
      technical,
    };
  }

  if (m.reason === "INSUFFICIENT" && m.detail === "STALE") {
    return {
      what: `Out-of-date ${noun} for ${field}.`,
      why: `Evidence for "${field}" exists but is older than this control allows.`,
      next: `Provide more recent ${noun} for ${field}.`,
      technical,
    };
  }

  if (m.reason === "INSUFFICIENT" && m.detail === "BELOW_MIN_SCORE") {
    return {
      what: `Low-trust ${noun} for ${field}.`,
      why: `Evidence for "${field}" exists but its trust level is below this control's threshold.`,
      next: `Provide a higher-trust source (e.g. signed or automated) for ${field}.`,
      technical,
    };
  }

  return {
    what: `Unmet requirement for ${field}.`,
    why: `The "${field}" requirement is not satisfied.`,
    next: `Add qualifying ${noun} for ${field}.`,
    technical,
  };
}
