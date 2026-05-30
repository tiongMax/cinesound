// TypeScript mirrors of backend Pydantic schemas (app/schemas.py).
// Keep in sync when the backend types change.

export interface MovieRec {
  tmdb_id: number;
  title: string;
  year?: number | null;
  rating?: number | null;
  genres: string[];
  reason: string;
  trailer_url?: string | null;
  poster_url?: string | null;
}

export interface MusicRec {
  spotify_uri: string;
  track: string;
  artist: string;
  album?: string | null;
  mood_tag: string;
  reason: string;
  spotify_url: string;
  album_art_url?: string | null;
  preview_url?: string | null;
}

export interface Pairing {
  movie: MovieRec;
  music: MusicRec;
  pairing_note: string;
}

export interface Recommendation {
  mood_detected: string;
  pairings: Pairing[];
  fallback_message?: string | null;
}

export type SseEvent =
  | { event: "ack"; data: { session_id: string } }
  | { event: "node_done"; data: { node: string } }
  | { event: "final"; data: Recommendation }
  | { event: "error"; data: { message: string } };

export type Vote = "up" | "down";

export interface FeedbackBody {
  session_id: string;
  vote: Vote;
  tmdb_id?: number;
  spotify_uri?: string;
}

export interface PlaylistTrack {
  spotify_uri: string;
  track: string;
  artist: string;
  album?: string | null;
  spotify_url: string;
  album_art_url?: string | null;
  preview_url?: string | null;
  reason: string;
}

export interface Playlist {
  mood_detected: string;
  title: string;
  intro: string;
  tracks: PlaylistTrack[];
}
