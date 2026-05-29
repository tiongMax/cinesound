"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { postFeedback } from "@/lib/feedback";
import { streamQuery } from "@/lib/queryClient";
import { getOrCreateSessionId } from "@/lib/session";
import type { Recommendation, Vote } from "@/lib/types";
import RecommendationBlock from "./RecommendationBlock";
import SignInButton from "./SignInButton";

type Turn = {
  id: string;
  query: string;
  status: "thinking" | "profiling" | "searching" | "ranking" | "final" | "error";
  rec?: Recommendation;
  error?: string;
};

const NODE_LABEL: Record<string, Turn["status"]> = {
  load_memory: "thinking",
  profile: "profiling",
  search: "searching",
  rank_and_pair: "ranking",
  save_memory: "final",
};

const STATUS_TEXT: Record<Turn["status"], string> = {
  thinking: "Reading your taste profile…",
  profiling: "Pinning the mood…",
  searching: "Searching films and tracks…",
  ranking: "Picking the pairing…",
  final: "",
  error: "",
};

export default function Chat() {
  const [sessionId, setSessionId] = useState<string>("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSessionId(getOrCreateSessionId());
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const updateTurn = (id: string, patch: Partial<Turn>) => {
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  };

  const handleVote = useCallback(
    async (target: { tmdb_id?: number; spotify_uri?: string }, vote: Vote) => {
      if (!sessionId) return;
      await postFeedback({ session_id: sessionId, vote, ...target });
    },
    [sessionId],
  );

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || submitting || !sessionId) return;
    setInput("");
    setSubmitting(true);
    const id = crypto.randomUUID();
    setTurns((ts) => [...ts, { id, query: q, status: "thinking" }]);

    try {
      await streamQuery(q, sessionId, {
        onNode: (node) => {
          const label = NODE_LABEL[node];
          if (label) updateTurn(id, { status: label });
        },
        onFinal: (rec) => {
          updateTurn(id, { status: "final", rec });
        },
        onError: (message) => {
          updateTurn(id, { status: "error", error: message });
        },
      });
    } catch (err) {
      updateTurn(id, {
        status: "error",
        error: err instanceof Error ? err.message : "unknown error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-xl font-semibold tracking-tight">CineSound</h1>
          <div className="flex items-center gap-4">
            {sessionId && (
              <div className="text-xs text-muted-foreground">
                device · {sessionId.slice(0, 16)}…
              </div>
            )}
            <SignInButton />
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {turns.length === 0 && (
            <div className="rounded-lg border border-border bg-muted/30 p-6 text-center text-muted-foreground">
              <p className="mb-2 text-sm">Try:</p>
              <ul className="space-y-1 text-sm">
                <li>&ldquo;I just finished Interstellar, feeling reflective&rdquo;</li>
                <li>&ldquo;Something fun and upbeat for a Friday night&rdquo;</li>
                <li>&ldquo;I love Kendrick Lamar, what should I watch?&rdquo;</li>
              </ul>
            </div>
          )}

          {turns.map((t) => (
            <div key={t.id} className="space-y-3">
              <div className="ml-auto max-w-[80%] rounded-2xl bg-accent px-4 py-2 text-accent-foreground">
                {t.query}
              </div>

              <AnimatePresence mode="wait">
                {t.status !== "final" && t.status !== "error" && (
                  <motion.div
                    key={t.status}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="flex items-center gap-2 text-sm text-muted-foreground"
                  >
                    <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-foreground" />
                    {STATUS_TEXT[t.status]}
                  </motion.div>
                )}
              </AnimatePresence>

              {t.status === "final" && t.rec && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <RecommendationBlock rec={t.rec} onVote={handleVote} />
                </motion.div>
              )}

              {t.status === "error" && (
                <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">
                  Something went wrong: {t.error ?? "unknown"}
                </div>
              )}
            </div>
          ))}

          <div ref={scrollRef} />
        </div>
      </main>

      <form
        onSubmit={onSubmit}
        className="border-t border-border bg-background px-6 py-4"
      >
        <div className="mx-auto flex max-w-2xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What's the vibe?"
            className="flex-1 rounded-lg border border-border bg-background px-4 py-2 outline-none focus:border-foreground"
            disabled={submitting}
            aria-label="Query"
          />
          <button
            type="submit"
            disabled={submitting || !input.trim()}
            className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background disabled:opacity-50"
          >
            {submitting ? "…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
