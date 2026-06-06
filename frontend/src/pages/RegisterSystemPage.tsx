import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";

// EU AI Act risk tiers. The classifier that would derive this automatically is
// not built yet, so the user selects it — with an explicit acknowledgement.
const RISK_TIERS = [
  { value: "HIGH", label: "High risk", hint: "Annex III system — full obligations apply" },
  { value: "LIMITED", label: "Limited risk", hint: "Transparency obligations only" },
  { value: "MINIMAL", label: "Minimal risk", hint: "No mandatory obligations" },
  { value: "PROHIBITED", label: "Prohibited", hint: "Not permitted under the Act" },
];

const ANNEX_III = [
  "employment",
  "biometric_identification",
  "education",
  "essential_services",
  "law_enforcement",
  "migration_asylum",
  "critical_infrastructure",
  "justice_democracy",
];

export function RegisterSystemPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [context, setContext] = useState("production");
  const [riskTier, setRiskTier] = useState("");
  const [annex, setAnnex] = useState("");
  const [ack, setAck] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const system = await api.createSystem({
        name,
        intended_purpose: purpose,
        deployment_context: context,
        risk_tier: riskTier || null,
        annex_iii_category: annex || null,
      });
      navigate(`/systems/${system.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create the system.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container narrow">
      <div className="page-head">
        <div>
          <h1>Register a system</h1>
          <p className="sub muted">Describe an AI system to assess it against the EU AI Act.</p>
        </div>
      </div>

      <div className="card auth-card">
        <form onSubmit={submit} className="stack">
          <div className="field">
            <label htmlFor="name">System name</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
          </div>

          <div className="field">
            <label htmlFor="purpose">Intended purpose</label>
            <textarea
              id="purpose"
              rows={3}
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              placeholder="e.g. Rank job applicants for recruiter review."
            />
          </div>

          <div className="field">
            <label htmlFor="context">Deployment context</label>
            <select id="context" value={context} onChange={(e) => setContext(e.target.value)}>
              <option value="production">Production</option>
              <option value="pilot">Pilot</option>
              <option value="staging">Staging</option>
              <option value="development">Development</option>
              <option value="internal">Internal use</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="risk">Risk classification</label>
            <select id="risk" value={riskTier} onChange={(e) => setRiskTier(e.target.value)} required>
              <option value="" disabled>
                Select a risk tier…
              </option>
              {RISK_TIERS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label} — {t.hint}
                </option>
              ))}
            </select>
            <p className="notice warn" style={{ marginTop: "0.6rem" }}>
              Risk classification is currently user-selected. Automated classification is planned in a
              future release.
            </p>
          </div>

          <div className="field">
            <label htmlFor="annex">Annex III category (optional)</label>
            <select id="annex" value={annex} onChange={(e) => setAnnex(e.target.value)}>
              <option value="">Not applicable / unsure</option>
              {ANNEX_III.map((c) => (
                <option key={c} value={c}>
                  {c.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>

          <label className="row" style={{ alignItems: "flex-start", fontWeight: 400, color: "var(--text)" }}>
            <input
              type="checkbox"
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
              style={{ width: "auto", marginTop: "0.2rem" }}
            />
            <span style={{ fontSize: "0.9rem" }}>
              I understand this risk tier was set manually and not determined by Comply.
            </span>
          </label>

          {error && <p className="error-text">{error}</p>}

          <div className="btn-row">
            <button type="button" onClick={() => navigate("/")} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="primary" disabled={busy || !ack}>
              {busy ? "Creating…" : "Create system"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
