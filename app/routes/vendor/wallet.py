from flask import request, jsonify
from decimal import Decimal
import logging
from models import db
from models.wallet import VendorWallet, VendorWalletTransaction
from models.vendor import VendorPayoutBank
from app.services.vendor.wallet import adjust_vendor_balance, InsufficientFunds
from app.utils import auth_required, role_required, transactional, error, internal_error_response
from . import vendor_bp


@vendor_bp.route("/wallet", methods=["GET"])
@auth_required
@role_required(["vendor"])
def get_vendor_wallet():
    user = request.user
    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
        try:
            with transactional("Failed to create vendor wallet"):
                db.session.add(wallet)
        except Exception:
            return internal_error_response()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


@vendor_bp.route("/wallet/history", methods=["GET"])
@auth_required
@role_required(["vendor"])
def get_vendor_wallet_history():
    txns = (
        VendorWalletTransaction.query.filter_by(user_phone=request.phone)
        .order_by(VendorWalletTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


@vendor_bp.route("/wallet/credit", methods=["POST"])
@auth_required
@role_required(["vendor"])
def credit_vendor_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-credit")
        if amount <= 0:
            return error("Invalid credit amount", status=400)
        with transactional("Failed to credit vendor wallet"):
            new_bal = adjust_vendor_balance(
                user.phone,
                amount,
                reference=reference,
                type="credit",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        logging.error("Failed to credit vendor wallet: %s", e, exc_info=True)
        return internal_error_response()


@vendor_bp.route("/wallet/debit", methods=["POST"])
@auth_required
@role_required(["vendor"])
def debit_vendor_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-debit")
        with transactional("Failed to debit vendor wallet"):
            new_bal = adjust_vendor_balance(
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
        logging.error("Failed to debit vendor wallet: %s", e, exc_info=True)
        return internal_error_response()


@vendor_bp.route("/wallet/withdraw", methods=["POST"])
@auth_required
@role_required(["vendor"])
def withdraw_vendor_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        if amount <= 0:
            return error("Invalid withdrawal amount", status=400)
        wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
        bank = VendorPayoutBank.query.filter_by(user_phone=user.phone).first()
        if not bank:
            return error("No payout bank setup found", status=400)
        with transactional("Failed to withdraw vendor wallet"):
            new_bal = adjust_vendor_balance(
                user.phone,
                -amount,
                reference=f"Withdraw to {bank.account_number}",
                type="withdrawal",
                source="api",
            )
        return jsonify({
            "status": "success",
            "message": "Withdrawal initiated",
            "bank_account": bank.account_number,
            "balance": float(new_bal),
        }), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        logging.error("Failed to withdraw vendor wallet: %s", e, exc_info=True)
        return internal_error_response()
