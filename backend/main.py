from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers.analysis import router as analysis_router
from backend.api.routers.health import router as health_router
from backend.api.routers.stocks import router as stocks_router
from backend.db.session import create_all_tables


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Helpful for local dev before migrations are wired into deployment scripts.
    if os.getenv("AUTO_CREATE_SCHEMA", "0") == "1":
        await create_all_tables()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Personal Stock Market Analyst API",
        version="0.1.0",
        description="Multi-agent stock analysis backend with write-isolated agent reports.",
        lifespan=lifespan,
    )
    cors_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).strip()
    if cors_origins:
        allow_origins = ["*"] if cors_origins == "*" else [item.strip() for item in cors_origins.split(",")]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(stocks_router)
    app.include_router(analysis_router)
    return app


app = create_app()
