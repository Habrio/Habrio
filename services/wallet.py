# services/wallet.py

from flask import request, jsonify
from models import db
from models.user import UserProfile
from models.wallet import (
    ConsumerWallet,
    WalletTransaction,
    VendorWallet,
    VendorWalletTransaction,
)
from models.vendor import VendorPayoutBank
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from decimal import Decimal


# ------------------- Get or Create Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def get_or_create_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Consumer Wallet Transactions -------------------
@auth_required
@role_required(["consumer"])
def wallet_transaction_history():
    txns = WalletTransaction.query.filter_by(user_phone=request.phone)\
        .order_by(WalletTransaction.created_at.desc()).limit(50).all()
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


# ------------------- Load Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def load_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-load")

    if amount <= 0:
        return jsonify({"status": "error", "message": "Invalid amount"}), 400

    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.flush()

    wallet.balance += amount
    db.session.add(WalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="recharge",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Debit Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def debit_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-debit")

    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"}), 400

    wallet.balance -= amount
    db.session.add(WalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="debit",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Refund to Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def refund_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-refund")

    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.flush()

    wallet.balance += amount
    db.session.add(WalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="refund",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Get or Create Vendor Wallet -------------------
@auth_required
@role_required(["vendor"])
def get_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Vendor Wallet Transactions -------------------
@auth_required
@role_required(["vendor"])
def get_vendor_wallet_history():
    txns = VendorWalletTransaction.query.filter_by(user_phone=request.phone)\
        .order_by(VendorWalletTransaction.created_at.desc()).limit(50).all()
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


# ------------------- Credit Vendor Wallet -------------------
@auth_required
@role_required(["vendor"])
def credit_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-credit")

    if amount <= 0:
        return jsonify({"status": "error", "message": "Invalid credit amount"}), 400

    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.flush()

    wallet.balance += amount
    db.session.add(VendorWalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="credit",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Debit Vendor Wallet -------------------
@auth_required
@role_required(["vendor"])
def debit_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-debit")

    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"}), 400

    wallet.balance -= amount
    db.session.add(VendorWalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="debit",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Withdraw Vendor Wallet to Bank -------------------
@auth_required
@role_required(["vendor"])
def withdraw_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Invalid withdrawal amount"}), 400

    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"}), 400

    bank = VendorPayoutBank.query.filter_by(user_phone=user.phone).first()
    if not bank:
        return jsonify({"status": "error", "message": "No payout bank setup found"}), 400

    wallet.balance -= amount
    db.session.add(VendorWalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="withdrawal",
        reference=f"Withdraw to {bank.account_number}",
        status="success"
    ))
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Withdrawal initiated",
        "bank_account": bank.account_number,
        "balance": float(wallet.balance)
    }), 200
