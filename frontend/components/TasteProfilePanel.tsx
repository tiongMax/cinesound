"use client";

import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw, Sparkles, User, X } from "lucide-react";
import { useEffect, useState } from "react";
import { clearMe, fetchMe, type MeSnapshot } from "@/lib/me";

interface Props {
  sessionId: string;
  /** Bump this number from the parent to force a refetch (e.g. after a query). */
  refreshKey?: number;
  /** Notify parent (e.g. Chat) when history was wiped so it can clear UI state. */
  onCleared?: () => void;
}

export default function TasteProfilePanel({
  sessionId,
  refreshKey = 0,
  onCleared,
}: Props) {
  const [open, setOpen] = useState(false);
  const [snap, setSnap] = useState<MeSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);

  const handleClear = async () => {
    if (!sessionId) return;
    setClearing(true);
    try {
      await clearMe(sessionId);
      setSnap(null);
      setConfirmClear(false);
      onCleared?.();
      // Reload from server (now empty)
      const fresh = await fetchMe(sessionId);
      setSnap(fresh);
    } catch {
      // best-effort; leave the panel as-is
    } finally {
      setClearing(false);
    }
  };

  useEffect(() => {
    if (!open || !sessionId) return;
    let cancelled = false;
    setLoading(true);
    fetchMe(sessionId)
      .then((s) => !cancelled && setSnap(s))
      .catch(() => !cancelled && setSnap(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, sessionId, refreshKey]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
        aria-label="Open taste profile"
      >
        <User className="h-3.5 w-3.5" />
        Profile
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          >
            <motion.aside
              initial={{ x: 380 }}
              animate={{ x: 0 }}
              exit={{ x: 380 }}
              transition={{ type: "spring", damping: 25 }}
              className="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto border-l border-border bg-background p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <header className="mb-6 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  What CineSound thinks about you
                </h2>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-md p-1 text-muted-foreground hover:bg-accent"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </header>

              {loading && (
                <p className="text-sm text-muted-foreground">Loading…</p>
              )}

              {!loading && !snap && (
                <p className="text-sm text-red-400">Couldn&apos;t load profile.</p>
              )}

              {!loading && snap && (
                <div className="space-y-6 text-sm">
                  <CountsRow snap={snap} />
                  <GenreList title="Genres you've liked" items={snap.top_liked_genres} />
                  <GenreList
                    title="Genres you've passed on"
                    items={snap.top_disliked_genres}
                    muted
                  />
                  <MoodList moods={snap.recent_moods} />
                  {Object.keys(snap.content_prefs).length > 0 && (
                    <ContentPrefs prefs={snap.content_prefs} />
                  )}

                  <div className="border-t border-border pt-4">
                    {!confirmClear ? (
                      <button
                        type="button"
                        onClick={() => setConfirmClear(true)}
                        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-red-400"
                      >
                        <RotateCcw className="h-3 w-3" />
                        Reset taste profile…
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-xs text-muted-foreground">
                          This wipes watch history, liked/disliked genres, and recent moods for this device. Can&apos;t be undone.
                        </p>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={handleClear}
                            disabled={clearing}
                            className="rounded-md bg-red-500/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50"
                          >
                            {clearing ? "Resetting…" : "Yes, reset everything"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmClear(false)}
                            className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function CountsRow({ snap }: { snap: MeSnapshot }) {
  return (
    <div className="grid grid-cols-3 gap-2 rounded-xl border border-border bg-muted/20 p-3">
      <Stat label="Watched" value={snap.counts.watched_movies} />
      <Stat label="Heard" value={snap.counts.heard_tracks} />
      <Stat label="Moods" value={snap.counts.queries_with_mood} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
    </div>
  );
}

function GenreList({
  title,
  items,
  muted,
}: {
  title: string;
  items: Array<{ genre: string; count: number }>;
  muted?: boolean;
}) {
  if (items.length === 0) {
    return (
      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
        <p className="text-xs text-muted-foreground">Nothing yet — give some thumbs.</p>
      </section>
    );
  }
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {items.map((g) => (
          <span
            key={g.genre}
            className={
              muted
                ? "rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground line-through"
                : "rounded-full bg-accent px-2.5 py-1 text-xs text-accent-foreground"
            }
          >
            {g.genre}
            <span className="ml-1 text-[10px] opacity-60">×{g.count}</span>
          </span>
        ))}
      </div>
    </section>
  );
}

function MoodList({ moods }: { moods: string[] }) {
  if (moods.length === 0) return null;
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Recent moods
      </h3>
      <ol className="space-y-1 text-xs text-muted-foreground">
        {moods.map((m, i) => (
          <li key={`${i}-${m}`} className="font-mono">
            {m}
          </li>
        ))}
      </ol>
    </section>
  );
}

function ContentPrefs({ prefs }: { prefs: Record<string, boolean> }) {
  const flags = Object.entries(prefs).filter(([, v]) => v);
  if (flags.length === 0) return null;
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Content preferences
      </h3>
      <ul className="text-xs text-muted-foreground">
        {flags.map(([k]) => (
          <li key={k}>• {k.replace(/_/g, " ")}</li>
        ))}
      </ul>
    </section>
  );
}
