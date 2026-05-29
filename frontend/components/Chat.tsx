"use client";

import { useEffect, useRef, useState } from "react";
import { getOrCreateSessionId } from "@/lib/session";

type Message =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string }; // placeholder until T26 wires real recs

export default function Chat() {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSessionId(getOrCreateSessionId());
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || submitting) return;
    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    setInput("");
    setSubmitting(true);
    // TODO(T26): call /query and stream events; for now echo placeholder
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "(recommendations stream here — wired in T26)" },
      ]);
      setSubmitting(false);
    }, 200);
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold tracking-tight">CineSound</h1>
          <div className="text-xs text-muted-foreground">
            {sessionId ? `device · ${sessionId.slice(0, 16)}…` : ""}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {messages.length === 0 && (
            <div className="rounded-lg border border-border bg-muted/30 p-6 text-center text-muted-foreground">
              <p className="mb-2 text-sm">Try:</p>
              <ul className="space-y-1 text-sm">
                <li>&ldquo;I just finished Interstellar, feeling reflective&rdquo;</li>
                <li>&ldquo;Something fun and upbeat for a Friday night&rdquo;</li>
                <li>&ldquo;I love Kendrick Lamar, what should I watch?&rdquo;</li>
              </ul>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[80%] rounded-2xl bg-accent px-4 py-2 text-accent-foreground"
                  : "max-w-[80%] rounded-2xl bg-muted px-4 py-2 text-muted-foreground"
              }
            >
              {m.text}
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
