# Contributing to CineSound

CineSound uses a strict **one-task-one-branch-one-squash-merge** workflow.
All checks must pass before merge. No exceptions for "small" changes.

## Dev environment setup

### Prereqs

- Docker Desktop (for the local Postgres+pgvector container)
- Python 3.11 (pinned via `backend/.python-version`)
- [uv](https://docs.astral.sh/uv/) 0.11+
- Node.js 20+ and npm 10+

### First-time setup

```bash
# 1. Local DB
docker compose up -d

# 2. Backend
cd backend
uv sync                              # installs runtime + dev deps
cp .env.example .env                 # fill in API keys
uv run python -m scripts.migrate     # applies migrations/*.sql

# 3. Frontend
cd ../frontend
npm install
cp .env.local.example .env.local
```

### Run both servers

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

## Branch naming

Format: `<type>/<short-kebab-description>`

| Type | When to use | Example |
|---|---|---|
| `feat/` | New user-facing feature | `feat/playlist-generation` |
| `fix/` | Bugfix | `fix/spotify-token-refresh-race` |
| `chore/` | Tooling, deps, config | `chore/bump-next` |
| `docs/` | Docs only | `docs/api-reference` |
| `refactor/` | Internal restructure, no behavior change | `refactor/extract-cache-decorator` |

Always branch from `main`. Never from another feature branch — see the
"squash-merge gotcha" note in commit `e066327` for why.

## Commit messages

Squash commits on `main` use this format:

```
<type>: <one-line summary in present tense, no trailing period>

[optional body — what changed and why, wrapped at 80 cols]
```

Examples from `git log`:

- `feat: LLM tool calling at ranker — get_movie_details + get_artist_top_tracks`
- `feat: 3 pairings per query — new Pairing schema, ranker returns N, frontend renders`
- `chore: ruff autofix + format (no behaviour change)`
- `T10: memory CRUD — get/set/append/migrate over user_memory JSONB`

Task-numbered prefixes (T01, T19, etc.) are used for milestones tracked in
`PLAN.md`. For ad-hoc work, use `feat:`/`fix:`/`chore:` instead.

## Running tests

### Backend

```bash
cd backend
uv run pytest                  # full suite (121 tests, ~3s)
uv run pytest tests/test_ranker.py -v
uv run pytest -k "tool"        # tests matching keyword
```

Backend uses `pytest-asyncio` in **auto mode** (configured in `pyproject.toml`).
Async tests are written as plain `async def test_...` — no decorator needed.

### Lint and format

```bash
cd backend
uv run ruff check .            # MUST pass before commit
uv run ruff check . --fix      # autofix what's fixable
uv run ruff format .           # apply formatter
```

Lint config lives in `backend/pyproject.toml` under `[tool.ruff]` —
line length 100, rules `E F I UP B SIM`.

### Frontend

```bash
cd frontend
npx tsc --noEmit               # type-check (must pass)
npx next build                 # production build (must succeed)
```

> ⚠️ Assumption: No frontend test runner is configured. If adding one,
> Vitest + React Testing Library is the natural fit for the App Router stack.

### Evals (optional, but expected for changes touching agents/prompts)

If you modify `app/agents/profiler.py` or `app/agents/ranker.py`, run the
eval harness against a local backend and commit the resulting JSON:

```bash
cd backend
uv run python ../evals/run.py --label feature-name
git add evals/runs/<timestamp>-feature-name.json
```

Compare aggregate metrics against the most recent run on `main` to catch
regressions in mood detection or genre overlap rates.

## PR review process

1. **Pre-PR self-check** — locally run all three: `uv run pytest`,
   `uv run ruff check .`, `npx tsc --noEmit`. All green or the PR is not ready.

2. **Open the PR against `main`.** Title = the planned squash commit message.
   Body should answer:
   - **What changed?** (one paragraph)
   - **Why?** (link to issue/PRD section if applicable)
   - **How tested?** (which tests added/modified, any manual verification)
   - **Anything reviewers should look at first?**

3. **One reviewer + green CI** is the merge bar for non-trivial changes.
   Tooling/docs changes can be self-merged if CI is green.

4. **Squash-merge only.** Never merge-commit or rebase-merge. Branch is
   deleted automatically after merge.

5. **Schema changes** (anything touching `app/schemas.py` or `migrations/`)
   require an extra review pass. Bump the PRD version in `PRD.md` header
   if the public API contract shifts.

## What not to do

- Don't commit `backend/.env` or `frontend/.env.local` — they're gitignored.
- Don't commit `evals/runs/` JSON unless it's a labeled milestone snapshot.
- Don't push directly to `main` — branch protection is the intent even if
  not yet enforced server-side.
- Don't re-open a PR from a squash-merged feature branch. The branch's
  commits are not on `main`; merging again will overwrite later work.
  See the discussion in `prd-fixes.md` and the README of `main`'s history.
