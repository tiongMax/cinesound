"use client";

import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import type { Vote } from "@/lib/types";

interface Props {
  onVote: (vote: Vote) => Promise<void> | void;
}

/** Optimistic thumbs widget — disables both buttons after a vote lands. */
export default function VoteButtons({ onVote }: Props) {
  const [voted, setVoted] = useState<Vote | null>(null);
  const [pending, setPending] = useState(false);

  const handle = async (v: Vote) => {
    if (voted || pending) return;
    setPending(true);
    setVoted(v); // optimistic
    try {
      await onVote(v);
    } catch {
      setVoted(null); // roll back on failure
    } finally {
      setPending(false);
    }
  };

  if (voted) {
    return (
      <div className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Check className="h-3 w-3" />
        <span>thanks</span>
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={() => handle("up")}
        disabled={pending}
        className="rounded-full p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
        aria-label="thumbs up"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={() => handle("down")}
        disabled={pending}
        className="rounded-full p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
        aria-label="thumbs down"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
