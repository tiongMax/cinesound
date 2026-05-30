"use client";

import { motion } from "framer-motion";

interface Props {
  /** Submit a refinement query — uses the conversational follow-up flow */
  onRefine: (modifier: string) => void;
  disabled?: boolean;
}

const AXES = [
  {
    label: "tone",
    left: { word: "darker", icon: "🌑" },
    right: { word: "brighter", icon: "☀️" },
  },
  {
    label: "energy",
    left: { word: "slower", icon: "🐢" },
    right: { word: "more upbeat", icon: "⚡" },
  },
  {
    label: "feel",
    left: { word: "more nostalgic", icon: "📼" },
    right: { word: "more modern", icon: "🔮" },
  },
] as const;

export default function MoodSpectrum({ onRefine, disabled }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.2 }}
      className="rounded-2xl border border-border bg-muted/10 p-3"
    >
      <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
        Nudge the vibe
      </div>
      <div className="space-y-2">
        {AXES.map((a) => (
          <div key={a.label} className="flex items-center gap-2">
            <button
              type="button"
              disabled={disabled}
              onClick={() => onRefine(a.left.word)}
              className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground hover:bg-accent disabled:opacity-50"
            >
              <span className="mr-1.5">{a.left.icon}</span>
              {a.left.word}
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onRefine(a.right.word)}
              className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground hover:bg-accent disabled:opacity-50"
            >
              <span className="mr-1.5">{a.right.icon}</span>
              {a.right.word}
            </button>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
