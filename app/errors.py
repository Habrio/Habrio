import logging
from flask import Blueprint
from werkzeug.exceptions import HTTPException
from app.utils.responses import error

errors_bp = Blueprint("errors_bp", __name__)

@errors_bp.app_errorhandler(HTTPException)
def handle_http_exception(e):
    msg = e.description or getattr(e, "name", "HTTP Error")
    return error(msg, status=e.code, code=e.code)

@errors_bp.app_errorhandler(Exception)
def handle_unexpected_exception(e):
    logging.exception("Unhandled exception")
    return error(
        "An unexpected error occurred. Please try again later.",
        status=500,
        code=500,
    )
