"""Apply SQL migrations against DATABASE_URL in order.

Usage:
    python -m scripts.migrate

Reads .env via pydantic-settings (same loader the app uses). Each migration
file is applied as a single transaction. A `_migrations` table tracks which
filenames have been applied so reruns are safe.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            filename   TEXT PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )


async def applied_set(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT filename FROM _migrations")
    return {r["filename"] for r in rows}


async def apply_migration(conn: asyncpg.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    async with conn.transaction():
        await conn.execute(sql)
        await conn.execute(
            "INSERT INTO _migrations (filename) VALUES ($1)", path.name
        )


async def main() -> int:
    if not settings.database_url:
        print("DATABASE_URL is not set in environment / .env", file=sys.stderr)
        return 1

    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("No migration files found.", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(settings.database_url)
    try:
        await ensure_migrations_table(conn)
        already = await applied_set(conn)
        pending = [p for p in files if p.name not in already]

        if not pending:
            print("All migrations already applied.")
            return 0

        for p in pending:
            print(f"Applying {p.name} ...")
            await apply_migration(conn, p)
            print(f"  done.")

        print(f"Applied {len(pending)} migration(s).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
