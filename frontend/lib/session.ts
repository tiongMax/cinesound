// Client-side session_id management.
// We generate a UUID on first visit and persist it in a cookie (1 year),
// which the backend reads to scope memory per device. Signed-in users
// migrate this anonymous session via /signin.

const COOKIE_NAME = "session_id";
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  document.cookie =
    `${name}=${encodeURIComponent(value)}; ` +
    `Max-Age=${ONE_YEAR_SECONDS}; Path=/; SameSite=Lax`;
}

export function getOrCreateSessionId(): string {
  let id = readCookie(COOKIE_NAME);
  if (!id) {
    id = `session:${crypto.randomUUID()}`;
    writeCookie(COOKIE_NAME, id);
  }
  return id;
}
