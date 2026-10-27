"""Run from App: uvicorn backend.main:app --reload."""

from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from backend.config import load_settings
from backend.db.session import create_db_engine
from backend.api.routes import health, locations, tournaments

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_db_engine()
    app.state.session_factory = sessionmaker(bind=engine)
    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    load_settings()
    app = FastAPI(
        title="Fishing Tournament Analytics API", version="0.1.0",
        description="Read-only access to imported tournament standings and catches.",
        lifespan=lifespan,
    )
    origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        # SQLAlchemy exceptions can contain SQL parameters. Do not expose them.
        logger.error("Database operation failed for %s (%s)", request.url.path, type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

    app.include_router(health.router)
    app.include_router(tournaments.router)
    app.include_router(locations.router)
    return app


app = create_app()
