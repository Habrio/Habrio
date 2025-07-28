"""
Central registry of allowed actions per role.
"""
ROLE_SCOPES = {
    "consumer": {"confirm_order", "cancel_order", "rate_order", "wallet_debit"},
    "vendor":   {"modify_order", "deliver_order", "cancel_order_vendor", "wallet_credit"},
    "admin":    {"*"},
}

def role_has_scope(role: str, action: str) -> bool:
    scopes = ROLE_SCOPES.get(role, set())
    return "*" in scopes or action in scopes
