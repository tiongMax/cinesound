import { notFound } from "next/navigation";
import MovieCard from "@/components/MovieCard";
import MusicCard from "@/components/MusicCard";
import PairingNote from "@/components/PairingNote";
import { getShare } from "@/lib/share";

interface Props {
  params: Promise<{ code: string }>;
}

export default async function SharedPairingPage({ params }: Props) {
  const { code } = await params;
  let share;
  try {
    share = await getShare(code);
  } catch {
    notFound();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 px-6 py-10">
      <header className="mb-2">
        <a
          href="/"
          className="text-xl font-semibold tracking-tight hover:underline"
        >
          CineSound
        </a>
        <p className="text-xs text-muted-foreground">
          Shared pairing · mood:{" "}
          <span className="text-foreground">{share.mood}</span>
        </p>
      </header>

      <MovieCard movie={share.pairing.movie} />
      <MusicCard music={share.pairing.music} />
      <PairingNote note={share.pairing.pairing_note} mood={share.mood} />

      <footer className="mt-6 border-t border-border pt-4 text-xs text-muted-foreground">
        <a href="/" className="hover:text-foreground">
          → Get your own pairing on CineSound
        </a>
      </footer>
    </main>
  );
}
