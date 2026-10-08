"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from audioapp.api.routes import router
from audioapp.config import get_settings
from audioapp.core.logging_setup import setup_logging
from audioapp.core.queueing import LocalThreadQueue
from audioapp.core.retention import start_sweeper
from audioapp.core.state import AppState
from audioapp.core.store import SQLiteJobStore
from audioapp.models.registry import MODELS, get_adapter

log = logging.getLogger(__name__)


def build_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    data_dir = settings.data_dir
    uploads_dir = data_dir / "uploads"
    jobs_dir = data_dir / "jobs"
    for d in (uploads_dir, jobs_dir):
        d.mkdir(parents=True, exist_ok=True)

    store = SQLiteJobStore(data_dir / "jobs.db")
    queue = LocalThreadQueue(max_workers=settings.separator_workers)

    def _get_adapter(model_id: str):
        if model_id not in MODELS:
            raise ValueError(f"unknown model: {model_id}")
        from audioapp.models.demucs_adapter import DemucsAdapter
        return DemucsAdapter(model_id=model_id, device=settings.device)

    state = AppState(
        settings=settings, store=store, queue=queue,
        jobs_dir=jobs_dir, uploads_dir=uploads_dir,
        get_adapter=_get_adapter,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = start_sweeper(store, jobs_dir, uploads_dir, settings.retention_sweep_s)
        log.info("started: data_dir=%s workers=%d model=%s",
                 data_dir, settings.separator_workers, settings.demucs_model)
        yield
        stop.set()
        queue.shutdown()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.app_state = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)
    return app


app = build_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("audioapp.main:app", host="0.0.0.0", port=8000)
