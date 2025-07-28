import logging


def current_request_id():
    try:
        from flask import g
        rid = getattr(g, "request_id", None)
        return rid or "n/a"
    except Exception:
        return "n/a"


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = current_request_id()
        except Exception:
            record.request_id = "n/a"
        return True


def configure_logging(app):
    fmt = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    handler.addFilter(RequestIdFilter())

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(logging.INFO)

    wl = logging.getLogger("werkzeug")
    wl.setLevel(logging.INFO)
    wl.handlers.clear()
    wl.addHandler(handler)

