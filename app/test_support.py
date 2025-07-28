from flask import Blueprint
from app.utils.responses import ok
import logging


test_support_bp = Blueprint("test_support_bp", __name__)


@test_support_bp.route("/__ok", methods=["GET"])
def __ok():
    return ok({"ping": "pong"})


@test_support_bp.route("/__boom", methods=["GET"])
def __boom():
    raise RuntimeError("boom")


@test_support_bp.route("/__log", methods=["GET"])
def __log():
    logging.getLogger(__name__).info("test log line")
    from app.utils.responses import ok
    return ok({"logged": True})
