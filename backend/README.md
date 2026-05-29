# CineSound Backend

FastAPI service for the CineSound multi-agent recommendation system. Managed with [uv](https://docs.astral.sh/uv/).

## Quickstart

```powershell
# install uv once (Windows)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# from repo root: bring up local Postgres + pgvector
docker compose up -d

cd backend
uv sync                          # creates .venv, installs runtime + dev deps
Copy-Item .env.example .env      # then fill in keys
                                 # default DATABASE_URL for the docker DB:
                                 # postgres://cinesound:cinesound@localhost:15432/cinesound

uv run python -m scripts.migrate # apply schema
uv run uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/health` → `{"status":"ok","env":"dev","db":true}`

## Common commands

| Action | Command |
|---|---|
| Install / sync deps | `uv sync` |
| Add a runtime dep | `uv add <pkg>` |
| Add a dev dep | `uv add --dev <pkg>` |
| Remove a dep | `uv remove <pkg>` |
| Run a script | `uv run python -m scripts.migrate` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |

`uv run` activates the project venv automatically — no `activate` step needed.

The `uv.lock` file is committed to the repo; reproducible installs come from `uv sync --frozen`.

## Layout

```
backend/
  app/
    __init__.py
    main.py           # FastAPI app + /health
    config.py         # pydantic-settings env loader
  migrations/
    001_init.sql      # initial schema (see PRD §7)
  scripts/
    migrate.py        # SQL migration runner
  pyproject.toml
  .python-version     # pinned to 3.11 for uv
  .env.example
```

Further modules (clients, agents, routes) land in subsequent tasks per PLAN.md.
