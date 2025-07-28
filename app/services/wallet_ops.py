from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from models.wallet import ConsumerWallet, WalletTransaction, VendorWallet, VendorWalletTransaction
from models.user import UserProfile
from models import db

TWOPLACES = Decimal("0.01")

class InsufficientFunds(Exception):
    pass

def _to_money(value):
    d = Decimal(str(value))
    return d.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def adjust_consumer_balance(user_phone: str, delta, *, reference: str, type: str, source: str = None, status: str = "success"):
    """
    Atomically adjust a consumer wallet by 'delta' (Decimal/str/number).
    Creates a WalletTransaction row in the same DB transaction.
    Prevents negative balances. Returns new Decimal balance.
    Does NOT commit; caller is responsible for commit/rollback.
    """
    amount = _to_money(delta)
    wallet = ConsumerWallet.query.filter_by(user_phone=user_phone).with_for_update(of=ConsumerWallet).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user_phone, balance=_to_money("0"))
        db.session.add(wallet)
        db.session.flush()

    new_balance = _to_money(wallet.balance) + amount
    if new_balance < _to_money("0"):
        raise InsufficientFunds("Insufficient balance")

    wallet.balance = new_balance

    txn = WalletTransaction(
        user_phone=user_phone,
        amount=abs(amount),
        type=type,
        reference=reference,
        status=status,
        source=source
    )
    db.session.add(txn)
    return new_balance

def adjust_vendor_balance(user_phone: str, delta, *, reference: str, type: str, source: str = None, status: str = "success"):
    """
    Atomically adjust a vendor wallet by 'delta'.
    Creates a VendorWalletTransaction row. Prevents negative balances.
    Returns new Decimal balance. Does NOT commit.
    """
    amount = _to_money(delta)

    wallet = VendorWallet.query.filter_by(user_phone=user_phone).with_for_update(of=VendorWallet).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user_phone, balance=_to_money("0"))
        db.session.add(wallet)
        db.session.flush()

    new_balance = _to_money(wallet.balance) + amount
    if new_balance < _to_money("0"):
        raise InsufficientFunds("Insufficient balance")

    wallet.balance = new_balance

    txn = VendorWalletTransaction(
        user_phone=user_phone,
        amount=abs(amount),
        type=type,
        reference=reference,
        status=status
    )
    db.session.add(txn)
    return new_balance
