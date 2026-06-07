// Client for the isolated ML service (Guard). Separate base URL from the core
// Comply API; the Guard is advisory and never part of compliance scoring.

const ML_URL = (import.meta.env.VITE_ML_URL as string | undefined) ?? "http://localhost:8100";

export interface GuardReason {
  source: "rule" | "model";
  detail: string;
  severity?: number | null;
  score?: number | null;
}

export interface GuardVerdict {
  action: "allow" | "flag" | "block";
  blocked: boolean;
  risk_score: number;
  injection_probability: number | null;
  classifier_available: boolean;
  reasons: GuardReason[];
}

export interface RagSource {
  citation: string;
  source: string;
  score: number;
  text: string;
}

export interface RagResponse {
  mode: "generated" | "retrieval";
  answer: string | null;
  sources: RagSource[];
  note?: string | null;
}

export async function ragQuery(question: string): Promise<RagResponse> {
  let res: Response;
  try {
    res = await fetch(`${ML_URL}/rag/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error(`Could not reach the ML service at ${ML_URL}. Is it running?`);
  }
  if (!res.ok) {
    if (res.status === 503) throw new Error("The knowledge index isn't built yet. Run the RAG ingest.");
    throw new Error(`Query failed (${res.status})`);
  }
  return (await res.json()) as RagResponse;
}

export async function guardCheck(text: string): Promise<GuardVerdict> {
  let res: Response;
  try {
    res = await fetch(`${ML_URL}/guard/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new Error(`Could not reach the ML service at ${ML_URL}. Is it running?`);
  }
  if (!res.ok) {
    if (res.status === 429) throw new Error("Rate limit exceeded — try again shortly.");
    throw new Error(`Guard check failed (${res.status})`);
  }
  return (await res.json()) as GuardVerdict;
}
