import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.schemas.common import ErrorEnvelope, SafeError


class PublicError(Exception):
    def __init__(self, status: int, code: str, message: str, retryable: bool = False):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable


def install_errors(app: FastAPI) -> None:
    def response(request: Request, error: PublicError):
        body = ErrorEnvelope(error=SafeError(code=error.code, message=error.message,
            retryable=error.retryable, correlation_id=request.state.correlation_id))
        return JSONResponse(body.model_dump(), status_code=error.status)

    @app.middleware("http")
    async def safe_headers(request: Request, call_next):
        request.state.correlation_id = uuid.uuid4().hex
        result = await call_next(request)
        result.headers["X-Correlation-ID"] = request.state.correlation_id
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["X-Frame-Options"] = "DENY"
        result.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.path.startswith("/v1/"):
            result.headers["Cache-Control"] = "no-store"
        return result

    @app.exception_handler(PublicError)
    async def public_error(request: Request, error: PublicError):
        return response(request, error)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        # Validation errors may contain submitted passwords or source text.
        return response(request, PublicError(422, "INVALID_REQUEST", "Invalid request."))

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(request: Request, _error: SQLAlchemyError):
        return response(request, PublicError(503, "STORE_UNAVAILABLE", "Storage is unavailable.", True))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = "RESOURCE_NOT_FOUND" if error.status_code == 404 else "INVALID_REQUEST"
        message = "Resource not found." if error.status_code == 404 else "Request rejected."
        return response(request, PublicError(error.status_code, code, message))
