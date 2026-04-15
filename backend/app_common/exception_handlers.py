# external
from fastapi.responses import JSONResponse
from fastapi import Request

# Custom
from .exceptions import AppError


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": str(exc),
            "type": exc.__class__.__name__,
            "error_code": exc.error_code,
        },
    )
