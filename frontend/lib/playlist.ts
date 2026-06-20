import type { Playlist } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function buildPlaylist(
  query: string,
  sessionId: string,
  length: number = 5,
): Promise<Playlist> {
  const r = await fetch(`${API_URL}/playlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId, length }),
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => null);
    throw new Error(detail?.detail ?? `playlist: HTTP ${r.status}`);
  }
  return r.json();
}
