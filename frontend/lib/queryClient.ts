// SSE client for POST /query.
// fetch() with streaming body — the standard EventSource API only supports GET,
// so we parse the SSE wire format manually.

import type { Recommendation, SseEvent } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type StreamCallbacks = {
  onAck?: (sessionId: string) => void;
  onNode?: (node: string) => void;
  onFinal?: (rec: Recommendation) => void;
  onError?: (message: string) => void;
};

export async function streamQuery(
  query: string,
  sessionId: string,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    cb.onError?.(`HTTP ${resp.status}`);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by a blank line ("\n\n")
    let sepIdx: number;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      handleEvent(raw, cb);
    }
  }
}

function handleEvent(raw: string, cb: StreamCallbacks): void {
  let event: string | undefined;
  let dataStr: string | undefined;
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataStr = line.slice(5).trim();
  }
  if (!event) return;

  let data: SseEvent["data"];
  try {
    data = dataStr ? JSON.parse(dataStr) : {};
  } catch {
    cb.onError?.(`malformed event data: ${dataStr?.slice(0, 80)}`);
    return;
  }

  switch (event) {
    case "ack":
      cb.onAck?.((data as { session_id: string }).session_id);
      break;
    case "node_done":
      cb.onNode?.((data as { node: string }).node);
      break;
    case "final":
      cb.onFinal?.(data as Recommendation);
      break;
    case "error":
      cb.onError?.((data as { message: string }).message);
      break;
  }
}
