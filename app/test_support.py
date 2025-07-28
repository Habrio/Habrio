from flask import Blueprint
from app.utils.responses import ok


test_support_bp = Blueprint("test_support_bp", __name__)


@test_support_bp.route("/__ok", methods=["GET"])
def __ok():
    return ok({"ping": "pong"})


@test_support_bp.route("/__boom", methods=["GET"])
def __boom():
    raise RuntimeError("boom")
