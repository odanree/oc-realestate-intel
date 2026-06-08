// Client-side API helpers.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8003";

export type Citation = { apn: string; address?: string | null };
export type Parcel = {
  apn?: string;
  address?: string;
  city?: string;
  zip?: string;
  owner?: string | null;
  owner_kind?: string | null;
  year_built?: number | null;
  // Title chain is embedded in the Qdrant payload for lookup queries.
  // For title_chain-intent queries, this lives on graph_facts instead.
  title_chain?: GraphFact[];
};
export type GraphFact = {
  date?: string;
  doc_number?: string;
  grantor?: string;
  grantee?: string;
  price?: number | null;
};

export type StreamEvent =
  | { kind: "router"; intent: string }
  | { kind: "retrieval"; parcels: Parcel[]; graph_facts: GraphFact[] }
  | { kind: "comparison"; parcels: Parcel[] }
  | {
      kind: "summarize";
      answer: string;
      citations: Citation[];
    }
  | { kind: "error"; message: string }
  | { kind: "done" };

/**
 * Stream query node-by-node from the FastAPI SSE endpoint.
 * Each yielded event corresponds to one LangGraph node completing.
 */
export async function* streamQuery(
  query: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const url = new URL(`${API_BASE}/api/v1/query/stream`);
  url.searchParams.set("q", query);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "text/event-stream" },
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // sse_starlette emits CRLF terminators. Normalize so a single split
    // pattern works regardless of which line-ending style the server uses.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let separatorIdx: number;
    while ((separatorIdx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, separatorIdx);
      buffer = buffer.slice(separatorIdx + 2);
      const evt = parseSseBlock(block);
      if (evt) yield evt;
    }
  }
}

function parseSseBlock(block: string): StreamEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    const payload = JSON.parse(data);
    switch (event) {
      case "router":
        return { kind: "router", intent: payload.intent };
      case "retrieval":
        return {
          kind: "retrieval",
          parcels: payload.parcels ?? [],
          graph_facts: payload.graph_facts ?? [],
        };
      case "comparison":
        return { kind: "comparison", parcels: payload.parcels ?? [] };
      case "summarize":
        return {
          kind: "summarize",
          answer: payload.answer ?? "",
          citations: payload.citations ?? [],
        };
      case "error":
        return { kind: "error", message: payload.error ?? "unknown error" };
      case "done":
        return { kind: "done" };
    }
  } catch (e) {
    return { kind: "error", message: `parse error: ${(e as Error).message}` };
  }
  return null;
}
