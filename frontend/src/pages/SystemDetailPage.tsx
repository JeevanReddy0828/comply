import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AISystem, Compliance, ControlResult } from "../api/types";
import { useCatalog } from "../catalog/CatalogContext";
import { StatusBadge } from "../components/StatusBadge";
import { AddEvidenceModal } from "../components/AddEvidenceModal";
import { remediationFor } from "../lib/remediation";

interface EvidenceTarget {
  controlId: string;
  field: string;
  category: string;
}

export function SystemDetailPage() {
  const { id = "" } = useParams();
  const { summaries } = useCatalog();
  const [system, setSystem] = useState<AISystem | null>(null);
  const [compliance, setCompliance] = useState<Compliance | null>(null);
  const [neverRun, setNeverRun] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [evidenceTarget, setEvidenceTarget] = useState<EvidenceTarget | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSystem(id)
      .then(setSystem)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load system."));
    api
      .getCompliance(id)
      .then((c) => {
        setCompliance(c);
        setNeverRun(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setNeverRun(true);
        else setError(err instanceof ApiError ? err.message : "Failed to load compliance.");
      });
  }, [id]);

  const runAssessment = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      const c = await api.runAssessment(id);
      setCompliance(c);
      setNeverRun(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to run assessment.");
    } finally {
      setRunning(false);
    }
  }, [id]);

  // After adding evidence: close modal, re-run, and highlight the result.
  // Evidence is already saved by the time this runs, so if the re-assessment
  // fails we must say so explicitly rather than fail silently.
  const onEvidenceSubmitted = useCallback(
    async (controlId: string) => {
      const before = compliance?.results.find((r) => r.control_id === controlId)?.status;
      setEvidenceTarget(null);
      setError(null);
      try {
        const c = await api.runAssessment(id);
        setCompliance(c);
        setNeverRun(false);
        const after = c.results.find((r) => r.control_id === controlId)?.status;
        if (before !== after) {
          setFlash(`${controlId}: ${before} → ${after}`);
          setTimeout(() => setFlash(null), 5000);
        }
      } catch (err) {
        setError(
          err instanceof ApiError
            ? `Evidence was saved, but re-assessment failed: ${err.message}`
            : "Evidence was saved, but re-assessment failed. Re-run the assessment to see its impact.",
        );
      }
    },
    [compliance, id],
  );

  if (error) return <div className="container"><p className="error-text">{error}</p></div>;
  if (!system) return <div className="center-muted">Loading…</div>;

  return (
    <div className="container">
      <div style={{ marginBottom: "1rem" }}>
        <Link to="/" className="subtle">
          ← All systems
        </Link>
      </div>

      <div className="page-head">
        <div>
          <h1>{system.name}</h1>
          <p className="sub muted">
            {system.risk_tier ? `${system.risk_tier} risk` : "Risk tier not set"}
            {system.annex_iii_category ? ` · ${system.annex_iii_category.replace(/_/g, " ")}` : ""}
            {system.deployment_context ? ` · ${system.deployment_context}` : ""}
          </p>
        </div>
        <div className="row" style={{ gap: "0.75rem" }}>
          {!neverRun && compliance?.applicability === "APPLICABLE" && (
            <Link to={`/systems/${id}/report`} className="button-link">
              Annex IV report
            </Link>
          )}
          <button className="primary" onClick={runAssessment} disabled={running}>
            {running ? "Assessing…" : neverRun ? "Run assessment" : "Re-run assessment"}
          </button>
        </div>
      </div>

      {flash && <div className="notice toast-ok" style={{ marginBottom: "1rem" }}>✓ {flash}</div>}

      {neverRun && (
        <div className="card center-muted">
          <p>No assessment has been run yet.</p>
          <button className="primary" onClick={runAssessment} disabled={running}>
            {running ? "Assessing…" : "Run first assessment"}
          </button>
        </div>
      )}

      {!neverRun && compliance && compliance.applicability === "NOT_APPLICABLE" && (
        <div className="card">
          <div className="notice info" style={{ margin: "1rem" }}>
            This system is classified <b>{system.risk_tier ?? "non-high"}</b> risk, so the EU AI Act's
            high-risk obligations do not apply. No controls are assessed. Change the risk tier to HIGH to
            evaluate Annex III controls.
          </div>
        </div>
      )}

      {!neverRun && compliance && compliance.applicability === "APPLICABLE" && (
        <>
          <div className="summary">
            <div className="card">
              <div className="k">Compliance score</div>
              <div className="v">{compliance.system_score ?? 0}%</div>
            </div>
            <div className="card">
              <div className="k">Satisfied</div>
              <div className="v ok">{compliance.counts.SATISFIED}</div>
            </div>
            <div className="card">
              <div className="k">Partial</div>
              <div className="v warn">{compliance.counts.PARTIAL}</div>
            </div>
            <div className="card">
              <div className="k">Missing</div>
              <div className="v bad">{compliance.counts.MISSING}</div>
            </div>
          </div>

          <div className="card">
            <table className="controls-table">
              <thead>
                <tr>
                  <th style={{ width: "6rem" }}>Control</th>
                  <th>Name</th>
                  <th style={{ width: "8rem" }}>Status</th>
                  <th style={{ width: "5rem" }}>Score</th>
                  <th style={{ width: "2rem" }}></th>
                </tr>
              </thead>
              <tbody>
                {compliance.results.map((r) => (
                  <ControlRow
                    key={r.control_id}
                    result={r}
                    name={summaries[r.control_id]?.name ?? r.control_id}
                    open={expanded === r.control_id}
                    onToggle={() => setExpanded(expanded === r.control_id ? null : r.control_id)}
                    onAddEvidence={(field, category) =>
                      setEvidenceTarget({ controlId: r.control_id, field, category })
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {evidenceTarget && (
        <AddEvidenceModal
          systemId={id}
          controlId={evidenceTarget.controlId}
          field={evidenceTarget.field}
          category={evidenceTarget.category}
          onClose={() => setEvidenceTarget(null)}
          onSubmitted={() => onEvidenceSubmitted(evidenceTarget.controlId)}
        />
      )}
    </div>
  );
}

function ControlRow({
  result,
  name,
  open,
  onToggle,
  onAddEvidence,
}: {
  result: ControlResult;
  name: string;
  open: boolean;
  onToggle: () => void;
  onAddEvidence: (field: string, category: string) => void;
}) {
  return (
    <>
      <tr className="row-toggle" onClick={onToggle}>
        <td className="id">{result.control_id}</td>
        <td className="name">{name}</td>
        <td>
          <StatusBadge status={result.status} />
        </td>
        <td>{result.score}%</td>
        <td className="subtle">{open ? "▾" : "▸"}</td>
      </tr>
      {open && (
        <tr>
          <td className="expand-cell" colSpan={5}>
            {result.status === "SATISFIED" ? (
              <div className="satisfied-note">
                ✓ All required evidence is present and current ({result.evidence_count} item
                {result.evidence_count === 1 ? "" : "s"}).
              </div>
            ) : (
              <div className="remediation">
                {result.missing_requirements.map((m) => {
                  const rem = remediationFor(m);
                  return (
                    <div key={`${m.field}-${m.type}`} className="item">
                      <div className="spread">
                        <div className="what">{rem.what}</div>
                        <button className="primary" onClick={() => onAddEvidence(m.field, m.type)}>
                          Add evidence
                        </button>
                      </div>
                      <div className="why">{rem.why}</div>
                      <div className="next">
                        <b>Next:</b> {rem.next}
                      </div>
                      <div className="tech">reason: {rem.technical}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
