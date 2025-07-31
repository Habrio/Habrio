import logging
import json
import os
from typing import Any, Dict
from opentelemetry.trace import get_current_span


SENSITIVE_KEYS = {"otp", "password", "token", "email", "phone_number", "phone"}


def current_request_id() -> str:
    try:
        from flask import g
        rid = getattr(g, "request_id", None)
        return rid or "n/a"
    except Exception:
        return "n/a"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = current_request_id()
        except Exception:
            record.request_id = "n/a"
        return True


def current_trace_ids():
    try:
        span = get_current_span()
        ctx = span.get_span_context() if span else None
        if not ctx or not ctx.is_valid:
            return "n/a", "n/a"
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        return "n/a", "n/a"


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        trace_id, span_id = current_trace_ids()
        record.trace_id = trace_id
        record.span_id = span_id
        return True


def _mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: ("[REDACTED]" if key in SENSITIVE_KEYS else value)
        for key, value in data.items()
    }


class MaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        env = os.getenv("APP_ENV", "development").lower()
        if isinstance(record.msg, dict):
            if not (record.levelno == logging.DEBUG and env != "production"):
                record.msg = _mask_dict(record.msg)
        if isinstance(record.args, dict):
            if not (record.levelno == logging.DEBUG and env != "production"):
                record.args = _mask_dict(record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "request_id": getattr(record, "request_id", "n/a"),
            "trace_id": getattr(record, "trace_id", "n/a"),
            "span_id": getattr(record, "span_id", "n/a"),
        }
        if isinstance(record.msg, dict):
            data = record.msg
            base.update(data)
            message = None
        else:
            message = record.getMessage()
        if message:
            base["message"] = message
        return json.dumps(base)


def configure_logging(app) -> None:
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(datefmt=datefmt))
    handler.addFilter(RequestIdFilter())
    handler.addFilter(TraceIdFilter())
    handler.addFilter(MaskingFilter())

    app.logger.handlers.clear()
    app.logger.addHandler(handler)

    level_name = os.getenv("LOG_LEVEL")
    if level_name:
        level = getattr(logging, level_name.upper(), logging.INFO)
    else:
        level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    app.logger.setLevel(level)

    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(level)

    wl = logging.getLogger("werkzeug")
    wl.setLevel(level)
    wl.handlers.clear()
    wl.addHandler(handler)
