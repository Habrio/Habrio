from flask import request, jsonify, current_app
from decimal import Decimal
from models import db
from models.wallet import ConsumerWallet, WalletTransaction
from app.services.wallet_ops import adjust_consumer_balance, InsufficientFunds
from app.utils import auth_required, role_required, transactional, error, internal_error_response
from . import consumer_bp


@consumer_bp.route("/wallet", methods=["GET"])
@auth_required
@role_required(["consumer"])
def get_or_create_wallet():
    user = request.user
    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        try:
            with transactional("Failed to create wallet"):
                db.session.add(wallet)
        except Exception:
            return internal_error_response()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


@consumer_bp.route("/wallet/history", methods=["GET"])
@auth_required
@role_required(["consumer"])
def wallet_transaction_history():
    txns = (
        WalletTransaction.query.filter_by(user_phone=request.phone)
        .order_by(WalletTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


@consumer_bp.route("/wallet/load", methods=["POST"])
@auth_required
@role_required(["consumer"])
def load_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        if amount <= 0:
            return error("Invalid amount", status=400)
        with transactional("Failed to load wallet"):
            new_bal = adjust_consumer_balance(
                user.phone,
                amount,
                reference=data.get("reference", "manual-load"),
                type="recharge",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        current_app.logger.error("Failed to load wallet: %s", e, exc_info=True)
        return internal_error_response()


@consumer_bp.route("/wallet/debit", methods=["POST"])
@auth_required
@role_required(["consumer"])
def debit_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-debit")
        with transactional("Failed to debit wallet"):
            new_bal = adjust_consumer_balance(
                user.phone,
                -amount,
                reference=reference,
                type="debit",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        current_app.logger.error("Failed to debit wallet: %s", e, exc_info=True)
        return internal_error_response()


@consumer_bp.route("/wallet/refund", methods=["POST"])
@auth_required
@role_required(["consumer"])
def refund_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-refund")
        with transactional("Failed to refund wallet"):
            new_bal = adjust_consumer_balance(
                user.phone,
                amount,
                reference=reference,
                type="refund",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        current_app.logger.error("Failed to refund wallet: %s", e, exc_info=True)
        return internal_error_response()
