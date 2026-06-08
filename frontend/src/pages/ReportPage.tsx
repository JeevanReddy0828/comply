import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AnnexIVReport, ReportControl } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

function fmt(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export function ReportPage() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<AnnexIVReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notRun, setNotRun] = useState(false);

  useEffect(() => {
    api
      .getReport(id)
      .then(setReport)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setNotRun(true);
        else setError(err instanceof ApiError ? err.message : "Failed to load report.");
      });
  }, [id]);

  if (error) return <div className="container"><p className="error-text">{error}</p></div>;
  if (notRun)
    return (
      <div className="container">
        <p className="muted">No assessment has been run for this system yet.</p>
        <Link to={`/systems/${id}`} className="subtle">← Back to system</Link>
      </div>
    );
  if (!report) return <div className="center-muted">Loading…</div>;

  const draft = report.watermark !== "LEGAL_APPROVED";

  return (
    <div className="report container wide">
      {draft && <div className="report-watermark" aria-hidden>{report.watermark}</div>}

      <div className="report-toolbar no-print">
        <Link to={`/systems/${report.system.id}`} className="subtle">← Back to system</Link>
        <button className="primary" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>

      <header className="report-head">
        <div className="report-kicker">EU AI Act · Annex IV — Technical Documentation</div>
        <h1>{report.system.name}</h1>
        {draft && (
          <div className="notice warn report-draft-banner">
            <b>DRAFT — not a validated conformity claim.</b> This document is generated from an
            engineering interpretation of the EU AI Act. No control backing it has completed legal
            review (review_status ≠ LEGAL_APPROVED), so it must not be presented as a conformity
            assessment.
          </div>
        )}
      </header>

      <section className="report-meta">
        <dl>
          <div><dt>Intended purpose</dt><dd>{report.system.intended_purpose || "—"}</dd></div>
          <div><dt>Risk classification</dt><dd>{report.system.risk_tier ?? "not set"}{report.system.annex_iii_category ? ` · ${report.system.annex_iii_category.replace(/_/g, " ")}` : ""}</dd></div>
          <div><dt>Deployment context</dt><dd>{report.system.deployment_context || "—"}</dd></div>
          <div><dt>Catalog version</dt><dd>{report.catalog_version}</dd></div>
          <div><dt>Assessment</dt><dd>{report.assessment_id}</dd></div>
          <div><dt>Assessment timestamp (frozen)</dt><dd>{fmt(report.assessment_timestamp)}</dd></div>
          <div><dt>Generated</dt><dd>{fmt(report.generated_at)}</dd></div>
          {report.applicability === "APPLICABLE" && (
            <div>
              <dt>Overall</dt>
              <dd>
                {report.system_score ?? 0}% · {report.counts.SATISFIED} satisfied ·{" "}
                {report.counts.PARTIAL} partial · {report.counts.MISSING} missing
              </dd>
            </div>
          )}
        </dl>
      </section>

      {report.applicability === "NOT_APPLICABLE" ? (
        <div className="notice info">{report.note}</div>
      ) : (
        report.sections.map((s) => (
          <section key={s.section} className="report-section">
            <h2>
              <span className="report-section-num">{s.section}</span> {s.title}
            </h2>
            {s.fields.length > 0 && (
              <p className="report-section-fields muted">
                Required elements: {s.fields.map((f) => f.replace(/_/g, " ")).join(", ")}
              </p>
            )}
            {s.controls.length === 0 ? (
              <p className="muted">No controls feed this section for this system.</p>
            ) : (
              s.controls.map((c) => <ControlBlock key={`${s.section}-${c.control_id}`} control={c} />)
            )}
          </section>
        ))
      )}
    </div>
  );
}

function ControlBlock({ control: c }: { control: ReportControl }) {
  return (
    <div className="report-control">
      <div className="report-control-head">
        <div>
          <span className="report-control-id">{c.control_id}</span>
          <span className="report-control-name">{c.name}</span>
        </div>
        <StatusBadge status={c.status} />
      </div>
      <div className="report-control-meta muted">
        v{c.control_version} · review: {c.review_status} · confidence: {c.confidence}
        {c.control_hash ? <> · <code>{c.control_hash.slice(0, 12)}…</code></> : null}
      </div>

      {c.evidence.length > 0 ? (
        <table className="report-evidence">
          <thead>
            <tr>
              <th>Field</th>
              <th>Type</th>
              <th>Source</th>
              <th>Trust</th>
              <th>Captured</th>
              <th>Evidence hash</th>
            </tr>
          </thead>
          <tbody>
            {c.evidence.map((e) => (
              <tr key={e.id}>
                <td>{e.field}</td>
                <td>{e.evidence_type}</td>
                <td>{e.source}</td>
                <td>{e.trust_score}</td>
                <td>{fmt(e.captured_at)}</td>
                <td><code>{e.hash.slice(0, 16)}…</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="report-no-evidence muted">
          No qualifying evidence — gap.
          {c.missing_requirements.length > 0 &&
            " Missing: " + c.missing_requirements.map((m) => m.field).join(", ")}
        </p>
      )}
    </div>
  );
}
