from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import configured_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # https://fastapi.tiangolo.com/advanced/events/
    app.state.engine = configured_engine()
    try:
        yield
    finally:
        if app.state.engine is not None:
            app.state.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Vision API", version="0.1.0", lifespan=lifespan)

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
                    if has_vector:
                        return {"status": "ready"}
            except SQLAlchemyError:
                pass  # Public health responses never disclose connection details.
        return JSONResponse({"status": "unready"}, status_code=503)

    return app


app = create_app()
