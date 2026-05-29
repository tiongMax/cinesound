"use client";

import { Sparkles } from "lucide-react";

interface Props {
  note: string;
  mood: string;
}

export default function PairingNote({ note, mood }: Props) {
  return (
    <div className="rounded-2xl border border-border bg-gradient-to-br from-accent/40 to-muted/10 p-4">
      <div className="mb-1 flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5" />
        <span>The pairing</span>
        <span className="ml-auto text-[10px] normal-case tracking-normal">{mood}</span>
      </div>
      <p className="text-sm leading-relaxed">{note}</p>
    </div>
  );
}
