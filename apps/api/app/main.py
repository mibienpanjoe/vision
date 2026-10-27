import os
from contextlib import asynccontextmanager

from app.api.v1.auth import router as auth_router
from app.api.v1.entities import router as entities_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.render import router as render_router
from app.api.v1.visualizations import router as visualizations_router
from app.api.v1.works import router as works_router
from app.core.errors import install_errors
from app.core.security import LoginLimiter
from app.core.storage import PrivateSources, private_renders, restore_marker
from app.db.session import configured_engine
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # https://fastapi.tiangolo.com/advanced/events/
    app.state.engine = configured_engine()
    app.state.login_limiter = LoginLimiter()
    try:
        yield
    finally:
        if app.state.engine is not None:
            app.state.engine.dispose()


def storage_ready() -> bool:
    """Private original and render roots exist, are owner-only and writable. Redis is not required: a failed
    enqueue stays visibly pending in SQL until dispatch."""
    if restore_marker().exists():
        return False
    try:
        roots = [PrivateSources().root, private_renders().root]
    except (OSError, ValueError):
        return False
    return all(os.access(root, os.W_OK | os.X_OK) for root in roots)


def create_app() -> FastAPI:
    app = FastAPI(title="Vision API", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    # Loopback by default; the packaged compose stack adds its private `api` service name (T45).
    hosts = os.environ.get("VISION_TRUSTED_HOSTS", "127.0.0.1,localhost").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host.strip() for host in hosts if host.strip()])
    install_errors(app)
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(works_router)
    app.include_router(evidence_router)
    app.include_router(entities_router)
    app.include_router(visualizations_router)
    app.include_router(render_router)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready(request: Request):
        engine = request.app.state.engine
        if engine is not None:
            try:
                with engine.connect() as connection:
                    has_vector = connection.scalar(text(
                        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                    ))
                    if has_vector and storage_ready():
                        return {"status": "ready"}
            except SQLAlchemyError:
                pass  # Public health responses never disclose connection details.
        return JSONResponse({"status": "unready"}, status_code=503)

    return app


app = create_app()
