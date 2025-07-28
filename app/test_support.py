from flask import Blueprint, request
from app.utils.responses import ok, error
import logging
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds
from models import db


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


@test_support_bp.route("/__wallet/consumer/adjust", methods=["POST"])
def __wallet_consumer_adjust():
    """Adjust consumer wallet for testing."""
    payload = request.get_json() or {}
    try:
        bal = adjust_consumer_balance(
            payload.get("phone"),
            payload.get("delta", 0),
            reference=payload.get("reference", "test"),
            type=payload.get("type", "recharge"),
            source="test",
        )
        db.session.commit()
        return ok({"balance": float(bal)})
    except InsufficientFunds as e:
        db.session.rollback()
        return error(str(e), status=400)
    except Exception:
        db.session.rollback()
        return error("wallet op failed", status=500)


@test_support_bp.route("/__wallet/vendor/adjust", methods=["POST"])
def __wallet_vendor_adjust():
    payload = request.get_json() or {}
    try:
        bal = adjust_vendor_balance(
            payload.get("phone"),
            payload.get("delta", 0),
            reference=payload.get("reference", "test"),
            type=payload.get("type", "credit"),
        )
        db.session.commit()
        return ok({"balance": float(bal)})
    except InsufficientFunds as e:
        db.session.rollback()
        return error(str(e), status=400)
    except Exception:
        db.session.rollback()
        return error("wallet op failed", status=500)
