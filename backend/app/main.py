"""Main application entry point for Cindercrest 2.0."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.auth import router as auth_router
from backend.app.api.conversation import router as conversation_router
from backend.app.api.health import router as health_router
from backend.app.api.memory import router as memory_router
from backend.app.api.personality import router as personality_router
from backend.app.api.tasks import router as tasks_router
from backend.app.api.voice import router as voice_router
from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.app.core.logging import logger, setup_logging
from backend.app.store.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager: initialize resources on startup and clean up on shutdown."""
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)

    logger.info("Initializing Cindercrest 2.0 backend on %s:%d", settings.HOST, settings.PORT)
    init_db()

    # Inform the developer of the session token for localhost client connection
    # Note: Secret redactor in logging protects production logs, so we display via direct print on local startup
    print("\n==================================================================")
    print("CINDERCREST 2.0 READY")
    print(f"Listening on: http://{settings.HOST}:{settings.PORT}")
    print(f"Session Token: {settings.SESSION_TOKEN}")
    print("==================================================================\n")

    yield

    logger.info("Cindercrest 2.0 backend shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="Cindercrest 2.0",
        description="Personal AI Operator for Windows 11",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url=None,
    )

    # CORS configuration (strictly localhost origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Centralized exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register API routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(voice_router)
    app.include_router(conversation_router)
    app.include_router(tasks_router)
    app.include_router(memory_router)
    app.include_router(personality_router)

    return app


app = create_app()
