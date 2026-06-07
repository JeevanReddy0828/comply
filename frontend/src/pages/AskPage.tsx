import { useState } from "react";
import { ragQuery } from "../api/ml";
import type { RagResponse } from "../api/ml";

const EXAMPLES = [
  "What are the human oversight obligations for high-risk AI systems?",
  "What record-keeping does the EU AI Act require?",
  "What evidence does control LOG_001 need?",
];

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<RagResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    const query = q.trim();
    if (!query) return;
    setQuestion(query);
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      setResult(await ragQuery(query));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container narrow">
      <div className="page-head">
        <div>
          <h1>Ask the Act</h1>
          <p className="sub muted">
            Ask questions about the EU AI Act and your control catalog. Answers are grounded in the
            regulation text and cite their sources.
          </p>
        </div>
      </div>

      <div className="card auth-card stack">
        <div className="field">
          <label htmlFor="q">Question</label>
          <textarea
            id="q"
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What transparency obligations apply to high-risk AI?"
          />
        </div>
        <div className="spread">
          <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
            {EXAMPLES.map((ex) => (
              <button key={ex} className="link" style={{ fontSize: "0.8rem" }} onClick={() => ask(ex)}>
                {ex.length > 38 ? ex.slice(0, 38) + "…" : ex}
              </button>
            ))}
          </div>
          <button className="primary" onClick={() => ask(question)} disabled={loading || !question.trim()}>
            {loading ? "Searching…" : "Ask"}
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
      </div>

      {result && (
        <div className="card auth-card stack" style={{ marginTop: "1rem" }}>
          {result.mode === "generated" && result.answer ? (
            <div>
              <label>Answer</label>
              <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{result.answer}</p>
            </div>
          ) : (
            <div className="notice info" style={{ margin: 0 }}>
              {result.note ??
                "Generated answers are off — showing the most relevant passages from the Act and catalog."}
            </div>
          )}

          <div>
            <label>Sources</label>
            <div className="stack" style={{ gap: "0.6rem" }}>
              {result.sources.map((s, i) => (
                <div key={i} className="card" style={{ padding: "0.7rem 0.9rem" }}>
                  <div className="spread" style={{ marginBottom: "0.3rem" }}>
                    <span style={{ fontWeight: 600 }}>
                      [{i + 1}] {s.citation}
                    </span>
                    <span className="badge neutral">
                      {s.source === "eu_ai_act" ? "EU AI Act" : "Catalog"}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: "0.88rem" }}>
                    {s.text.length > 320 ? s.text.slice(0, 320).trim() + "…" : s.text}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
