# STL
from enum import StrEnum, auto
from logging import Logger, LoggerAdapter
import time
import uuid
import json
import traceback

# Third-Party
from fastapi import Request, Response
from starlette.middleware.base import (
    RequestResponseEndpoint,
    BaseHTTPMiddleware,
    DispatchFunction,
)
from starlette.types import ASGIApp

# Custom
from configs import get_logger, settings
from .logging_types import HttpResponseLog, HttpRequestLog, HttpErrorLog
from common.enums import RequestEnum


class EventEnum(StrEnum):
    REQUEST = auto()
    RESPONSE = auto()
    ERROR = auto()


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, *, dispatch: DispatchFunction | None = None
    ):
        super().__init__(app, dispatch)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        client_ip = self._get_client_ip(request=request)

        body = await self._read_body_once(request=request)
        body_json = self._parse_and_scrub_body(body=body)

        start_time = time.perf_counter()
        logger: LoggerAdapter[Logger] | Logger = get_logger(
            request_id=request_id
        )

        self._log_request(
            logger=logger,
            request=request,
            client_ip=client_ip,
            body_json=body_json,
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self._log_response(
                logger=logger,
                response=response,
                duration_ms=duration_ms,
                request_id=request_id,
            )
            return response
        except Exception as exe:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self._log_error(
                logger=logger,
                duration_ms=duration_ms,
                exe=exe,
                request_id=request_id,
            )
            raise

    @staticmethod
    def _set_request_id_header(response: Response, request_id: str) -> None:
        """assign request_id to header"""
        if "X-Request-ID" in response.headers:
            return
        response.headers["X-Request-ID"] = request_id

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Get Client ip address based on the forwarded list"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return request.client.host if request.client else "Empty IP address"

    def _scrub_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {
            k: "***" if k.lower() in settings.sensitive_headers else v
            for k, v in headers.items()
        }

    def _parse_and_scrub_body(self, body: bytes | str) -> dict | str:
        if not body:
            return "Empty Body"
        if isinstance(body, str):
            return body

        data = json.loads(body)
        if isinstance(data, dict):
            return {
                k: "***" if k.lower() in settings.sensitive_body_fields else v
                for k, v in data.items()
            }
        return data

    async def _read_body_once(self, request: Request) -> bytes | str:
        """Read body only once and cache it safely for later consumers."""
        if request.method not in RequestEnum:
            return "<Method does not exist>"
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return "<invalid type>"

        body = await request.body()
        if len(body) > settings.max_body_log_size:
            return "<body too large>"
        request._body = body
        return body

    def _log_request(
        self, logger, request: Request, client_ip: str, body_json: dict | str
    ) -> None:
        scrubbed_headers = self._scrub_headers(dict(request.headers))

        log_data = HttpRequestLog(
            msg="HTTP Request",
            event=EventEnum.REQUEST,
            method=request.method,
            url=str(request.url),
            query_params=dict(request.query_params),
            path_params=dict(request.path_params),
            headers=scrubbed_headers,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            body=body_json,
        )
        logger.info(log_data)

    def _log_response(
        self, logger, response: Response, duration_ms, request_id
    ) -> None:
        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request_id

        log_data = HttpResponseLog(
            msg="HTTP Response",
            event=EventEnum.RESPONSE,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        logger.info(log_data)

    def _log_error(
        self, logger, duration_ms: float, exe: Exception, request_id: str
    ) -> None:
        log_data = HttpErrorLog(
            msg="Request failed",
            event=EventEnum.ERROR,
            request_id=request_id,
            status_code=500,
            duration_ms=duration_ms,
            error=str(exe),
            traceback=traceback.format_exc(),
        )

        logger.exception(log_data)
