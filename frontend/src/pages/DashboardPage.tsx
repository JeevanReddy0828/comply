import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AISystem } from "../api/types";

const ONBOARDING_STEPS = [
  { t: "Register a system", d: "Tell us about an AI system you operate." },
  { t: "Run an assessment", d: "See which EU AI Act controls it meets." },
  { t: "Add evidence", d: "Attach proof for the gaps it surfaces." },
  { t: "Re-assess", d: "Watch failing controls turn green." },
];

export function DashboardPage() {
  const [systems, setSystems] = useState<AISystem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .listSystems()
      .then(setSystems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load systems."));
  }, []);

  if (error) return <div className="container"><p className="error-text">{error}</p></div>;
  if (systems === null) return <div className="center-muted">Loading…</div>;

  // Day 0 — guided onboarding instead of a dead dashboard.
  if (systems.length === 0) {
    return (
      <div className="container">
        <div className="card onboarding">
          <h1>Welcome to Comply</h1>
          <p className="lead muted">
            Comply assesses your AI systems against the EU AI Act and shows you exactly what evidence is
            missing — and how to close each gap. Here's the path:
          </p>
          <div className="steps">
            {ONBOARDING_STEPS.map((s, i) => (
              <div key={s.t} className="card step">
                <span className="num">{i + 1}</span>
                <h3>{s.t}</h3>
                <p>{s.d}</p>
              </div>
            ))}
          </div>
          <button className="primary" onClick={() => navigate("/systems/new")}>
            Create your first system
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Systems</h1>
          <p className="sub muted">AI systems registered in your organization.</p>
        </div>
        <button className="primary" onClick={() => navigate("/systems/new")}>
          + Register system
        </button>
      </div>
      <div className="system-list">
        {systems.map((s) => (
          <Link key={s.id} to={`/systems/${s.id}`} className="card system-row">
            <div>
              <div className="name">{s.name}</div>
              <div className="meta">
                {s.risk_tier ? `${s.risk_tier} risk` : "Risk tier not set"}
                {s.annex_iii_category ? ` · ${s.annex_iii_category}` : ""}
              </div>
            </div>
            <span className="subtle">View →</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
