# CineSound Backend

FastAPI service for the CineSound multi-agent recommendation system.

## Quickstart

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -e ".[dev]"
cp .env.example .env           # then fill in keys
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/health` → `{"status":"ok","env":"dev"}`

## Layout

```
backend/
  app/
    __init__.py
    main.py           # FastAPI app + /health
    config.py         # pydantic-settings env loader
  pyproject.toml
  .env.example
```

Further modules (clients, agents, routes, migrations) land in subsequent tasks per PLAN.md.
