import { useMemo, useState } from "react";
import { Modal } from "./Modal";
import { api, ApiError } from "../api/client";
import { EVIDENCE_SOURCES, typesForCategory } from "../lib/evidenceTypes";
import { humanizeField } from "../lib/remediation";

interface Props {
  systemId: string;
  /** The gap this evidence is meant to close. */
  controlId: string;
  field: string;
  category: string; // requirement.type — TELEMETRY | DOCUMENT | ATTESTATION | CONFIG
  onClose: () => void;
  onSubmitted: () => void; // parent re-runs the assessment
}

// datetime-local value (no tz) -> ISO 8601. Falls back to now.
function toIso(local: string): string {
  const d = local ? new Date(local) : new Date();
  return d.toISOString();
}

function nowLocal(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function AddEvidenceModal({ systemId, controlId, field, category, onClose, onSubmitted }: Props) {
  const options = useMemo(() => typesForCategory(category), [category]);
  const [evidenceType, setEvidenceType] = useState(options[0]?.id ?? "manual_document");
  const [source, setSource] = useState(options[0]?.defaultSource ?? "MANUAL");
  const [capturedAt, setCapturedAt] = useState(nowLocal());
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = options.find((o) => o.id === evidenceType);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.addEvidence(systemId, {
        control_id: controlId,
        field,
        source,
        evidence_type: evidenceType,
        captured_at: toIso(capturedAt),
        payload: note ? { note } : {},
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add evidence.");
      setBusy(false);
    }
  }

  return (
    <Modal title="Add evidence" onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        Provide evidence of <b>{humanizeField(field)}</b> for control <b>{controlId}</b>.
      </p>
      <form onSubmit={submit} className="stack">
        <div className="field">
          <label htmlFor="etype">Evidence type</label>
          <select
            id="etype"
            value={evidenceType}
            onChange={(e) => {
              setEvidenceType(e.target.value);
              const def = options.find((o) => o.id === e.target.value);
              if (def) setSource(def.defaultSource);
            }}
          >
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label} (trust {o.trust})
              </option>
            ))}
          </select>
          {selected && (
            <p className="subtle" style={{ marginTop: "0.4rem", fontSize: "0.8rem" }}>
              Higher-trust, automated evidence is more likely to satisfy the control's threshold.
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="source">Source</label>
          <select id="source" value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
            {EVIDENCE_SOURCES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="captured">Captured at</label>
          <input
            id="captured"
            type="datetime-local"
            value={capturedAt}
            onChange={(e) => setCapturedAt(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="note">Note (optional)</label>
          <input id="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reference or description" />
        </div>

        {error && <p className="error-text">{error}</p>}

        <div className="btn-row">
          <button type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Adding…" : "Add evidence & re-assess"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
