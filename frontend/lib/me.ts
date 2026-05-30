const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface GenreCount {
  genre: string;
  count: number;
}

export interface MeSnapshot {
  session_id: string;
  counts: {
    watched_movies: number;
    heard_tracks: number;
    queries_with_mood: number;
  };
  top_liked_genres: GenreCount[];
  top_disliked_genres: GenreCount[];
  recent_moods: string[];
  recent_queries: string[];
  content_prefs: Record<string, boolean>;
}

export async function fetchMe(sessionId: string): Promise<MeSnapshot> {
  const r = await fetch(
    `${API_URL}/me?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!r.ok) throw new Error(`/me: HTTP ${r.status}`);
  return r.json();
}

export async function clearMe(sessionId: string): Promise<void> {
  const r = await fetch(
    `${API_URL}/me?session_id=${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
  if (!r.ok) throw new Error(`/me: HTTP ${r.status}`);
}
