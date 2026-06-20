import type { FeedbackBody } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function postFeedback(body: FeedbackBody): Promise<void> {
  const r = await fetch(`${API_URL}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    throw new Error(`feedback: HTTP ${r.status}`);
  }
}
