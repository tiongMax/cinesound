"use client";

import Image from "next/image";
import { ExternalLink, Music } from "lucide-react";
import type { MusicRec } from "@/lib/types";

interface Props {
  music: MusicRec;
  onVote?: (vote: "up" | "down") => void;
}

export default function MusicCard({ music }: Props) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-muted/20">
      <div className="flex gap-4 p-4">
        <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-md bg-background">
          {music.album_art_url ? (
            <Image
              src={music.album_art_url}
              alt={music.album ?? music.track}
              fill
              sizes="96px"
              className="object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <Music className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-lg font-semibold">{music.track}</h3>
          <p className="truncate text-sm text-muted-foreground">{music.artist}</p>
          {music.album && (
            <p className="truncate text-xs text-muted-foreground">{music.album}</p>
          )}
          <div className="mb-2 mt-1">
            <span className="rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground">
              {music.mood_tag}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{music.reason}</p>
          <a
            href={music.spotify_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-foreground hover:underline"
          >
            Open in Spotify <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
