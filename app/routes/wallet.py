from flask import Blueprint
# services/wallet.py

from flask import request, jsonify
from models import db
from models.wallet import (
    ConsumerWallet,
    WalletTransaction,
    VendorWallet,
    VendorWalletTransaction,

)
from models.vendor import VendorPayoutBank
wallet_bp = Blueprint("wallet", __name__, url_prefix="/api/v1")
from app.utils import auth_required
from app.utils import role_required
from decimal import Decimal
import logging
from app.utils import internal_error_response
from app.services.wallet_ops import (
    adjust_consumer_balance,
    adjust_vendor_balance,
    InsufficientFunds,
)


# ------------------- Get or Create Consumer Wallet -------------------
@wallet_bp.route("/wallet", methods=["GET"])
@auth_required
@role_required(["consumer"])
def get_or_create_wallet():
    """Return the consumer wallet for the authenticated user, creating one if needed."""
    user = request.user
    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error("Failed to create wallet: %s", e, exc_info=True)
            return internal_error_response()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Consumer Wallet Transactions -------------------
@wallet_bp.route("/wallet/history", methods=["GET"])
@auth_required
@role_required(["consumer"])
def wallet_transaction_history():
    txns = WalletTransaction.query.filter_by(user_phone=request.phone)\
        .order_by(WalletTransaction.created_at.desc()).limit(50).all()
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


@wallet_bp.route("/wallet/load", methods=["POST"])
# ------------------- Load Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def load_wallet():
    """Add funds to the authenticated consumer's wallet."""
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        if amount <= 0:
            return jsonify({"status": "error", "message": "Invalid amount"}), 400

        new_bal = adjust_consumer_balance(
            user.phone,
            amount,
            reference=data.get("reference", "manual-load"),
            type="recharge",
            source="api",
        )
        db.session.commit()
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to load wallet: %s", e, exc_info=True)
        return internal_error_response()

@wallet_bp.route("/wallet/debit", methods=["POST"])

# ------------------- Debit Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def debit_wallet():
    """Deduct funds from the authenticated consumer's wallet."""
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-debit")

        new_bal = adjust_consumer_balance(
            user.phone,
            -amount,
            reference=reference,
            type="debit",
            source="api",
        )
        db.session.commit()
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to debit wallet: %s", e, exc_info=True)
        return internal_error_response()


# ------------------- Refund to Consumer Wallet -------------------
@wallet_bp.route("/wallet/refund", methods=["POST"])
@auth_required
@role_required(["consumer"])
def refund_wallet():
    """Refund an amount back to the consumer's wallet, creating it if needed."""
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-refund")

        new_bal = adjust_consumer_balance(
            user.phone,
            amount,
            reference=reference,
            type="refund",
            source="api",
        )
        db.session.commit()
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to refund wallet: %s", e, exc_info=True)
        return internal_error_response()


# ------------------- Get or Create Vendor Wallet -------------------
@auth_required
@wallet_bp.route("/vendor/wallet", methods=["GET"])
@auth_required
@role_required(["vendor"])
def get_vendor_wallet():
    """Return or create the vendor wallet for the authenticated vendor."""
    user = request.user
    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error("Failed to create vendor wallet: %s", e, exc_info=True)
            return internal_error_response()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Vendor Wallet Transactions -------------------
@wallet_bp.route("/vendor/wallet/history", methods=["GET"])
@auth_required
@role_required(["vendor"])
def get_vendor_wallet_history():
    txns = VendorWalletTransaction.query.filter_by(user_phone=request.phone)\
        .order_by(VendorWalletTransaction.created_at.desc()).limit(50).all()
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


# ------------------- Credit Vendor Wallet -------------------
@wallet_bp.route("/vendor/wallet/credit", methods=["POST"])
@auth_required
@role_required(["vendor"])
def credit_vendor_wallet():
    """Credit the vendor's wallet with the provided amount."""
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-credit")

        if amount <= 0:
            return jsonify({"status": "error", "message": "Invalid credit amount"}), 400

        new_bal = adjust_vendor_balance(
            user.phone,
            amount,
            reference=reference,
            type="credit",
            source="api",
        )
        db.session.commit()
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to credit vendor wallet: %s", e, exc_info=True)
        return internal_error_response()


# ------------------- Debit Vendor Wallet -------------------
@wallet_bp.route("/vendor/wallet/debit", methods=["POST"])
@auth_required
@role_required(["vendor"])
def debit_vendor_wallet():
    """Debit the vendor's wallet if sufficient balance exists."""
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-debit")

        new_bal = adjust_vendor_balance(
            user.phone,
            -amount,
            reference=reference,
            type="debit",
            source="api",
        )
        db.session.commit()
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to debit vendor wallet: %s", e, exc_info=True)
        return internal_error_response()


# ------------------- Withdraw Vendor Wallet to Bank -------------------
@wallet_bp.route("/vendor/wallet/withdraw", methods=["POST"])
@auth_required
@role_required(["vendor"])
def withdraw_vendor_wallet():
    """Withdraw from the vendor wallet to the configured payout bank."""
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))

        if amount <= 0:
            return jsonify({"status": "error", "message": "Invalid withdrawal amount"}), 400

        wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
        bank = VendorPayoutBank.query.filter_by(user_phone=user.phone).first()
        if not bank:
            return jsonify({"status": "error", "message": "No payout bank setup found"}), 400

        new_bal = adjust_vendor_balance(
            user.phone,
            -amount,
            reference=f"Withdraw to {bank.account_number}",
            type="withdrawal",
            source="api",
        )
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "Withdrawal initiated",
            "bank_account": bank.account_number,
            "balance": float(new_bal)
        }), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to withdraw vendor wallet: %s", e, exc_info=True)
        return internal_error_response()
