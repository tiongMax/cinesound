"use client";

import MovieCard from "./MovieCard";
import MusicCard from "./MusicCard";
import PairingNote from "./PairingNote";
import type { Recommendation, Vote } from "@/lib/types";

interface Props {
  rec: Recommendation;
  onVote?: (target: { tmdb_id?: number; spotify_uri?: string }, vote: Vote) => void;
}

export default function RecommendationBlock({ rec, onVote }: Props) {
  if (rec.pairings.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
        {rec.fallback_message ?? "No pairings to show right now."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {rec.pairings.map((p, i) => (
        <div key={`${p.movie.tmdb_id}-${p.music.spotify_uri}`} className="space-y-3">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
            <span>Pairing {i + 1}</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <MovieCard
            movie={p.movie}
            onVote={onVote ? (v) => onVote({ tmdb_id: p.movie.tmdb_id }, v) : undefined}
          />
          <MusicCard
            music={p.music}
            onVote={
              onVote ? (v) => onVote({ spotify_uri: p.music.spotify_uri }, v) : undefined
            }
          />
          <PairingNote note={p.pairing_note} mood={rec.mood_detected} />
        </div>
      ))}
    </div>
  );
}
