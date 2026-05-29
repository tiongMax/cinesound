"use client";

import Image from "next/image";
import { ExternalLink, Film } from "lucide-react";
import type { MovieRec } from "@/lib/types";

interface Props {
  movie: MovieRec;
  /** Optional thumbs callbacks (wired in T27) */
  onVote?: (vote: "up" | "down") => void;
}

export default function MovieCard({ movie }: Props) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-muted/20">
      <div className="flex gap-4 p-4">
        <div className="relative h-32 w-24 shrink-0 overflow-hidden rounded-md bg-background">
          {movie.poster_url ? (
            <Image
              src={movie.poster_url}
              alt={movie.title}
              fill
              sizes="96px"
              className="object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <Film className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-baseline gap-2">
            <h3 className="truncate text-lg font-semibold">{movie.title}</h3>
            {movie.year && (
              <span className="text-sm text-muted-foreground">{movie.year}</span>
            )}
          </div>
          <div className="mb-2 flex flex-wrap gap-1">
            {movie.genres.map((g) => (
              <span
                key={g}
                className="rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground"
              >
                {g}
              </span>
            ))}
            {movie.rating != null && (
              <span className="rounded-full bg-background px-2 py-0.5 text-xs text-muted-foreground">
                ★ {movie.rating.toFixed(1)}
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">{movie.reason}</p>
          {movie.trailer_url && (
            <a
              href={movie.trailer_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-foreground hover:underline"
            >
              Watch trailer <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
