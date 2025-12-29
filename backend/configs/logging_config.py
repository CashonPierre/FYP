# STL
import logging
import json
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Custom
from typing import NotRequired, TypedDict


class LoggingType(TypedDict):
    timestamp: str
    level: str
    logger: str
    module: str
    function: str
    line: int
    message: str
    exception: NotRequired[str]


# Custom formatter that outputs JSON
class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_object = LoggingType(
            timestamp=self.formatTime(
                record=record, datefmt="%Y-%m-%dT%H:%M:%SZ"
            ),
            level=record.levelname,
            logger=record.name,
            module=record.module,
            function=record.funcName,
            line=record.lineno,
            message=record.getMessage(),
        )

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_object, ensure_ascii=False)


# Configure root logger
def setup_logging():
    """Json formatter setup"""
    Path("logs").mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        filename="logs/app.jsonl",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    formatter = JSONLogFormatter()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


# Helper to get logger with request_id
def get_logger(
    request_id: str | None = None,
) -> logging.Logger | logging.LoggerAdapter:
    """Use this for all the printing"""
    logger = logging.getLogger()
    if request_id:
        logger = logging.LoggerAdapter(
            logger=logger, extra={"request_id": request_id}
        )
    return logger
