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

export type RagStreamEvent =
  | { type: "sources"; sources: RagSource[] }
  | { type: "reasoning"; delta: string }
  | { type: "answer"; delta: string }
  | { type: "done"; mode?: "generated" | "retrieval" }
  | { type: "error"; message: string };

// Streams the RAG response as Server-Sent Events: sources first, then reasoning
// and answer deltas. Invokes onEvent for each parsed event.
export async function ragQueryStream(
  question: string,
  onEvent: (e: RagStreamEvent) => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${ML_URL}/rag/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error(`Could not reach the ML service at ${ML_URL}. Is it running?`);
  }
  if (!res.ok || !res.body) {
    if (res.status === 503) throw new Error("The knowledge index isn't built yet. Run the RAG ingest.");
    throw new Error(`Query failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (payload) onEvent(JSON.parse(payload) as RagStreamEvent);
    }
  }
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
