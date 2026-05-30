import type { Pairing } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SharedPairing {
  short_code: string;
  pairing: Pairing;
  mood: string;
}

export async function createShare(
  pairing: Pairing,
  mood: string,
): Promise<SharedPairing> {
  const r = await fetch(`${API_URL}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pairing, mood }),
  });
  if (!r.ok) throw new Error(`share: HTTP ${r.status}`);
  return r.json();
}

export async function getShare(code: string): Promise<SharedPairing> {
  const r = await fetch(`${API_URL}/share/${encodeURIComponent(code)}`);
  if (!r.ok) throw new Error(`share: HTTP ${r.status}`);
  return r.json();
}
