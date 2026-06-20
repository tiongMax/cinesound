"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface Props {
  url: string;
  /** Optional label for screen readers, e.g., the track name. */
  label?: string;
}

/** Minimal 30s-preview play/pause button backed by a single <audio> element. */
export default function PreviewPlayer({ url, label }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onEnded = () => setPlaying(false);
    a.addEventListener("ended", onEnded);
    return () => a.removeEventListener("ended", onEnded);
  }, []);

  const toggle = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
      setPlaying(false);
    } else {
      a.currentTime = 0;
      a.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={playing ? `Pause preview${label ? ` of ${label}` : ""}` : `Play preview${label ? ` of ${label}` : ""}`}
      className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-background hover:opacity-90"
    >
      {playing ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3 translate-x-[1px]" />}
      <audio ref={audioRef} src={url} preload="none" />
    </button>
  );
}
