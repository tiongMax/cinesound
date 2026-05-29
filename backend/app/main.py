from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        app.state.db_pool = await init_pool()
    else:
        app.state.db_pool = None
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(
    title="CineSound API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "env": settings.app_env,
        "db": app.state.db_pool is not None,
    }


@app.get("/health/db")
async def health_db() -> dict[str, str | int]:
    pool = app.state.db_pool
    if pool is None:
        return {"status": "disabled"}
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    return {"status": "ok", "select_1": result}
