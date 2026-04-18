# External
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Custom
from database.make_db import Base, engine
from configs import settings, setup_logging
from middlewares import LoggingMiddleware
from api.auth import auth_router
from api.market import market_router
from api.backtests import backtest_router
from api.strategies import strategy_router
from app_common.exception_handlers import app_error_handler
from app_common.exceptions import AppError


def register_middleawre(app: FastAPI) -> None:
    # In dev mode allow any localhost port (Vite picks 5173/5174/5175/... depending
    # on what's free).  In production ALLOWED_ORIGIN env var locks it down to the
    # real domain; allow_origin_regex is left unset.
    origin_regex = r"http://localhost:\d+" if settings.debug else None

    app.add_middleware(
        middleware_class=CORSMiddleware,
        allow_origins=settings.allowed_origin,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
    )

    app.add_middleware(middleware_class=LoggingMiddleware)

    # app.add_middleware(HTTPSRedirectMiddleware)

    # add more middleware here


def register_routes(app: FastAPI) -> None:
    app.include_router(router=auth_router)
    app.include_router(router=market_router)
    app.include_router(router=backtest_router)
    app.include_router(router=strategy_router)


def register_exception_handler(app: FastAPI) -> None:
    app.add_exception_handler(
        exc_class_or_status_code=AppError,
        handler=app_error_handler,  # type: ignore
    )


def create_app() -> FastAPI:
    """the main function that create the server"""
    app = FastAPI(title="Trading Backend")

    register_middleawre(app=app)
    register_exception_handler(app=app)
    register_routes(app=app)

    return app


if __name__ == "__main__":
    """ starting the server here """
    setup_logging()

    Base.metadata.create_all(bind=engine)
    app: FastAPI = create_app()

    # In production (DEBUG=false) bind to all interfaces so the reverse proxy
    # (Railway / Fly / Render ingress) can reach the process.
    host = "0.0.0.0" if not settings.debug else settings.app_host
    uvicorn.run(app=app, host=host, port=settings.app_port)

    # run python server.py
