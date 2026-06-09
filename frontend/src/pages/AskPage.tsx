import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ragQueryStream } from "../api/ml";
import type { RagSource } from "../api/ml";
import { api } from "../api/client";
import type { ArticleControls } from "../api/types";

const EXAMPLES = [
  "What are the human oversight obligations for high-risk AI systems?",
  "What record-keeping does the EU AI Act require?",
  "What evidence does control LOG_001 need?",
];

// Pull article references ("Article 14", "Art. 14", "Art.14(1)") out of free text
// and normalize to the catalog's article-level keys ("Art.14").
function detectArticles(text: string): Set<string> {
  const set = new Set<string>();
  const re = /\bart(?:icle)?\.?\s*(\d{1,3})/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) set.add(`Art.${m[1]}`);
  return set;
}

function reviewClass(status: string): string {
  if (status === "LEGAL_APPROVED") return "ok";
  if (status === "NEEDS_LEGAL_REVIEW") return "warn";
  return "neutral";
}

export function AskPage() {
  const [question, setQuestion] = useState("");
  const [sources, setSources] = useState<RagSource[]>([]);
  const [reasoning, setReasoning] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [mode, setMode] = useState<"generated" | "retrieval" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asked, setAsked] = useState(false);
  const [articleMap, setArticleMap] = useState<ArticleControls[]>([]);
  const [affected, setAffected] = useState<ArticleControls[]>([]);

  useEffect(() => {
    api.listArticleControls().then(setArticleMap).catch(() => setArticleMap([]));
  }, []);

  async function ask(q: string) {
    const query = q.trim();
    if (!query) return;
    setQuestion(query);
    setError(null);
    setSources([]);
    setReasoning("");
    setAnswerText("");
    setMode(null);
    setAffected([]);
    setAsked(true);
    setLoading(true);
    let finalAnswer = "";
    let finalSources: RagSource[] = [];
    try {
      await ragQueryStream(query, (e) => {
        if (e.type === "sources") {
          finalSources = e.sources;
          setSources(e.sources);
        } else if (e.type === "reasoning") setReasoning((r) => r + e.delta);
        else if (e.type === "answer") {
          finalAnswer += e.delta;
          setAnswerText((a) => a + e.delta);
        } else if (e.type === "error") setError(e.message);
        else if (e.type === "done") setMode(e.mode ?? null);
      });
      // Bridge the answer back to the catalog: which controls back the articles it cites?
      const detected = detectArticles([query, finalAnswer, ...finalSources.map((s) => s.citation)].join(" "));
      setAffected(articleMap.filter((a) => detected.has(a.article)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
    } finally {
      setLoading(false);
    }
  }

  const thinking = loading && !answerText;

  return (
    <div className="container wide">
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
        <div className="ask-result">
          <div className="card auth-card stack">
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
                <div className="markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{answerText}</ReactMarkdown>
                </div>
                {loading && <span className="subtle">▍</span>}
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
          </div>

          <div className="card auth-card">
            <label>Sources</label>
            {sources.length === 0 ? (
              <p className="subtle" style={{ fontSize: "0.85rem", margin: 0 }}>Retrieving…</p>
            ) : (
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
            )}
          </div>
        </div>
      )}

      {affected.length > 0 && (
        <div className="card affected-controls">
          <label>Controls this touches</label>
          <p className="subtle" style={{ fontSize: "0.85rem", margin: "0.25rem 0 0.85rem" }}>
            Catalog controls mapped to the EU AI Act articles cited above — the bridge from regulation to your
            compliance posture. Open a system to see status and assign remediation.
          </p>
          {affected.map((a) => (
            <div key={a.article} className="affected-article">
              <div className="affected-article-head">{a.article}</div>
              <div className="affected-control-list">
                {a.controls.map((c) => (
                  <div key={c.control_id} className="affected-control">
                    <span className="affected-control-id">{c.control_id}</span>
                    <span className="affected-control-name">{c.name}</span>
                    <span className={`badge ${reviewClass(c.review_status)}`}>
                      {c.review_status.replace(/_/g, " ").toLowerCase()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
