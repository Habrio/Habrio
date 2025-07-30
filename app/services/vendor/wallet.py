from decimal import Decimal, ROUND_HALF_UP
from models.wallet import VendorWallet, VendorWalletTransaction
from models import db

TWOPLACES = Decimal("0.01")

class InsufficientFunds(Exception):
    pass


def _to_money(value):
    d = Decimal(str(value))
    return d.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def adjust_vendor_balance(user_phone: str, delta, *, reference: str, type: str, source: str = None, status: str = "success"):
    """Adjust a vendor wallet atomically and record a transaction."""
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
        status=status,
    )
    db.session.add(txn)
    return new_balance
