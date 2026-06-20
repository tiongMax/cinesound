"use client";

import Image from "next/image";
import { ExternalLink, ListMusic, Music } from "lucide-react";
import { motion } from "framer-motion";
import type { Playlist } from "@/lib/types";
import PreviewPlayer from "./PreviewPlayer";

export default function PlaylistBlock({ playlist }: { playlist: Playlist }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-2xl border border-border bg-gradient-to-br from-accent/30 to-muted/10 p-4"
    >
      <div className="mb-3 flex items-center gap-2">
        <ListMusic className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs uppercase tracking-wider text-muted-foreground">
          Playlist
        </span>
      </div>
      <h3 className="mb-1 text-lg font-semibold">{playlist.title}</h3>
      <p className="mb-4 text-sm text-muted-foreground">{playlist.intro}</p>
      <ol className="space-y-2">
        {playlist.tracks.map((t, i) => (
          <li
            key={t.spotify_uri}
            className="flex items-center gap-3 rounded-lg bg-background/40 p-2"
          >
            <span className="w-5 shrink-0 text-center text-xs tabular-nums text-muted-foreground">
              {i + 1}
            </span>
            <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded bg-muted">
              {t.album_art_url ? (
                <Image
                  src={t.album_art_url}
                  alt={t.album ?? t.track}
                  fill
                  sizes="40px"
                  className="object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <Music className="h-4 w-4 text-muted-foreground" />
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{t.track}</div>
              <div className="truncate text-xs text-muted-foreground">
                {t.artist}
                {" · "}
                <span className="italic">{t.reason}</span>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {t.preview_url && <PreviewPlayer url={t.preview_url} label={t.track} />}
              <a
                href={t.spotify_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                aria-label="Open track"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          </li>
        ))}
      </ol>
    </motion.div>
  );
}
