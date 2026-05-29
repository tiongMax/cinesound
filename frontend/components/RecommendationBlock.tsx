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
  return (
    <div className="space-y-3">
      {rec.movies.map((m) => (
        <MovieCard
          key={m.tmdb_id}
          movie={m}
          onVote={onVote ? (v) => onVote({ tmdb_id: m.tmdb_id }, v) : undefined}
        />
      ))}
      {rec.music.map((t) => (
        <MusicCard
          key={t.spotify_uri}
          music={t}
          onVote={onVote ? (v) => onVote({ spotify_uri: t.spotify_uri }, v) : undefined}
        />
      ))}
      {rec.pairing_note && (
        <PairingNote note={rec.pairing_note} mood={rec.mood_detected} />
      )}
    </div>
  );
}
