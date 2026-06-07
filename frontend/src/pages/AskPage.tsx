import { useState } from "react";
import { ragQueryStream } from "../api/ml";
import type { RagSource } from "../api/ml";

const EXAMPLES = [
  "What are the human oversight obligations for high-risk AI systems?",
  "What record-keeping does the EU AI Act require?",
  "What evidence does control LOG_001 need?",
];

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [sources, setSources] = useState<RagSource[]>([]);
  const [reasoning, setReasoning] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [mode, setMode] = useState<"generated" | "retrieval" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asked, setAsked] = useState(false);

  async function ask(q: string) {
    const query = q.trim();
    if (!query) return;
    setQuestion(query);
    setError(null);
    setSources([]);
    setReasoning("");
    setAnswerText("");
    setMode(null);
    setAsked(true);
    setLoading(true);
    try {
      await ragQueryStream(query, (e) => {
        if (e.type === "sources") setSources(e.sources);
        else if (e.type === "reasoning") setReasoning((r) => r + e.delta);
        else if (e.type === "answer") setAnswerText((a) => a + e.delta);
        else if (e.type === "error") setError(e.message);
        else if (e.type === "done") setMode(e.mode ?? null);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
    } finally {
      setLoading(false);
    }
  }

  const thinking = loading && !answerText;

  return (
    <div className="container narrow">
      <div className="page-head">
        <div>
          <h1>Ask the Act</h1>
          <p className="sub muted">
            Ask questions about the EU AI Act and your control catalog. Answers stream in, grounded in
            the regulation text, and cite their sources.
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
            {loading ? "Asking…" : "Ask"}
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
      </div>

      {asked && (
        <div className="card auth-card stack" style={{ marginTop: "1rem" }}>
          {reasoning && (
            <details>
              <summary className="subtle" style={{ cursor: "pointer", fontSize: "0.85rem" }}>
                Model reasoning
              </summary>
              <p className="muted" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                {reasoning}
              </p>
            </details>
          )}

          {answerText ? (
            <div>
              <label>Answer</label>
              <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                {answerText}
                {loading && <span className="subtle"> ▍</span>}
              </p>
            </div>
          ) : thinking ? (
            <div className="muted" style={{ fontSize: "0.9rem" }}>
              {reasoning ? "Reasoning…" : "Retrieving and thinking…"}
            </div>
          ) : (
            mode === "retrieval" && (
              <div className="notice info" style={{ margin: 0 }}>
                Generated answers are off — showing the most relevant passages from the Act and catalog.
              </div>
            )
          )}

          {sources.length > 0 && (
            <div>
              <label>Sources</label>
              <div className="stack" style={{ gap: "0.6rem" }}>
                {sources.map((s, i) => (
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
          )}
        </div>
      )}
    </div>
  );
}
