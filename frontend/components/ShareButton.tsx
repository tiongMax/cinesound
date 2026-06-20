"use client";

import { Check, Link as LinkIcon, Share2 } from "lucide-react";
import { useState } from "react";
import { createShare } from "@/lib/share";
import type { Pairing } from "@/lib/types";

interface Props {
  pairing: Pairing;
  mood: string;
}

export default function ShareButton({ pairing, mood }: Props) {
  const [state, setState] = useState<"idle" | "creating" | "copied" | "error">(
    "idle",
  );
  const [url, setUrl] = useState<string | null>(null);

  const onClick = async () => {
    if (state === "creating") return;
    setState("creating");
    try {
      const share = await createShare(pairing, mood);
      const shareUrl = `${window.location.origin}/p/${share.short_code}`;
      setUrl(shareUrl);
      try {
        await navigator.clipboard.writeText(shareUrl);
        setState("copied");
        setTimeout(() => setState("idle"), 2500);
      } catch {
        // Clipboard blocked — leave URL visible for the user to copy
        setState("idle");
      }
    } catch {
      setState("error");
    }
  };

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={state === "creating"}
        className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
      >
        {state === "copied" ? (
          <>
            <Check className="h-3 w-3" /> Link copied
          </>
        ) : state === "creating" ? (
          <>Creating…</>
        ) : (
          <>
            <Share2 className="h-3 w-3" /> Share
          </>
        )}
      </button>
      {url && state !== "copied" && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <LinkIcon className="h-3 w-3" /> open
        </a>
      )}
      {state === "error" && (
        <span className="text-xs text-red-400">share failed</span>
      )}
    </div>
  );
}
