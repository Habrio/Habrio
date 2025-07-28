from app.version import API_PREFIX


def _join_prefix(*parts):
    s = "/".join(p.strip("/") for p in parts if p is not None and p != "")
    return "/" + s if not s.startswith("/") else s


def register_api_v1(app):
    """Register business endpoints under the API version prefix."""
    # Import here to avoid circular dependencies
    from services import (
        auth as auth_services,
        user as user_services,
        vendor as vendor_services,
        shop as shop_services,
        item as item_services,
        cart as cart_services,
        wallet as wallet_services,
        consumerorder as consumer_order_services,
        vendororder as vendor_order_services,
    )

    def j(path: str) -> str:
        return _join_prefix(API_PREFIX, path)

    add = app.add_url_rule

    # JWT auth refresh
    app.register_blueprint(auth_services.auth_bp, url_prefix=_join_prefix(API_PREFIX, "auth"))

    # Auth and onboarding
    add(j("/send-otp"), view_func=auth_services.send_otp_handler, methods=["POST"])
    add(j("/verify-otp"), view_func=auth_services.verify_otp_handler, methods=["POST"])
    add(j("/logout"), view_func=auth_services.logout_handler, methods=["POST"])
    add(j("/onboarding/basic"), view_func=user_services.basic_onboarding, methods=["POST"])

    # Consumer routes
    add(j("/onboarding/consumer"), view_func=user_services.consumer_onboarding, methods=["POST"])

    add(j("/profile/me"), view_func=user_services.get_consumer_profile, methods=["GET"])
    add(j("/profile/edit"), view_func=user_services.edit_consumer_profile, methods=["POST"])

    # Wallet
    add(j("/wallet"), view_func=wallet_services.get_or_create_wallet, methods=["GET"])
    add(j("/wallet/history"), view_func=wallet_services.wallet_transaction_history, methods=["GET"])
    add(j("/wallet/load"), view_func=wallet_services.load_wallet, methods=["POST"])
    add(j("/wallet/debit"), view_func=wallet_services.debit_wallet, methods=["POST"])
    add(j("/wallet/refund"), view_func=wallet_services.refund_wallet, methods=["POST"])

    # Shops & Items
    add(j("/shops"), view_func=shop_services.list_shops, methods=["GET"])
    add(j("/shops/search"), view_func=shop_services.search_shops, methods=["GET"])
    add(j("/items/shop/<int:shop_id>"), view_func=item_services.view_items_by_shop, methods=["GET"])

    # Cart
    add(j("/cart/add"), view_func=cart_services.add_to_cart, methods=["POST"])
    add(j("/cart/view"), view_func=cart_services.view_cart, methods=["GET"])
    add(j("/cart/update"), view_func=cart_services.update_cart_quantity, methods=["POST"])
    add(j("/cart/remove"), view_func=cart_services.remove_item, methods=["POST"])
    add(j("/cart/clear"), view_func=cart_services.clear_cart, methods=["POST"])

    # Consumer Orders
    add(j("/order/confirm"), view_func=consumer_order_services.confirm_order, methods=["POST"])
    add(j("/order/history"), view_func=consumer_order_services.get_order_history, methods=["GET"])
    add(j("/order/consumer/confirm-modified/<int:order_id>"), view_func=consumer_order_services.confirm_modified_order, methods=["POST"])
    add(j("/order/consumer/cancel/<int:order_id>"), view_func=consumer_order_services.cancel_order_consumer, methods=["POST"])
    add(j("/order/consumer/message/send/<int:order_id>"), view_func=consumer_order_services.send_order_message_consumer, methods=["POST"])
    add(j("/order/consumer/messages/<int:order_id>"), view_func=consumer_order_services.get_order_messages_consumer, methods=["GET"])
    add(j("/order/rate/<int:order_id>"), view_func=consumer_order_services.rate_order, methods=["POST"])
    add(j("/order/issue/<int:order_id>"), view_func=consumer_order_services.raise_order_issue, methods=["POST"])
    add(j("/order/return/raise/<int:order_id>"), view_func=consumer_order_services.request_return, methods=["POST"])

    # Vendor routes - onboarding and shop setup
    add(j("/vendor/profile"), view_func=vendor_services.vendor_profile_setup, methods=["POST"])
    add(j("/vendor/upload-document"), view_func=vendor_services.upload_vendor_document, methods=["POST"])
    add(j("/vendor/create-shop"), view_func=shop_services.create_shop, methods=["POST"])
    add(j("/vendor/payout/setup"), view_func=vendor_services.setup_payout_bank, methods=["POST"])

    # Shop management
    add(j("/shop/update-hours"), view_func=shop_services.update_shop_hours, methods=["POST"])
    add(j("/shop/edit"), view_func=shop_services.edit_shop, methods=["POST"])
    add(j("/shop/my"), view_func=shop_services.get_my_shop, methods=["GET"])
    add(j("/vendor/shop/toggle_status"), view_func=shop_services.toggle_shop_status, methods=["POST"])

    # Items
    add(j("/item/add"), view_func=item_services.add_item, methods=["POST"])
    add(j("/item/bulk-upload"), view_func=item_services.bulk_upload_items, methods=["POST"])
    add(j("/item/<int:item_id>/toggle"), view_func=item_services.toggle_item_availability, methods=["POST"])
    add(j("/item/update/<int:item_id>"), view_func=item_services.update_item, methods=["POST"])
    add(j("/item/my"), view_func=item_services.get_items, methods=["GET"])

    # Vendor Wallet
    add(j("/vendor/wallet"), view_func=wallet_services.get_vendor_wallet, methods=["GET"])
    add(j("/vendor/wallet/history"), view_func=wallet_services.get_vendor_wallet_history, methods=["GET"])
    add(j("/vendor/wallet/credit"), view_func=wallet_services.credit_vendor_wallet, methods=["POST"])
    add(j("/vendor/wallet/debit"), view_func=wallet_services.debit_vendor_wallet, methods=["POST"])
    add(j("/vendor/wallet/withdraw"), view_func=wallet_services.withdraw_vendor_wallet, methods=["POST"])

    # Vendor Orders
    add(j("/order/vendor"), view_func=vendor_order_services.get_shop_orders, methods=["GET"])
    add(j("/order/vendor/status/<int:order_id>"), view_func=vendor_order_services.update_order_status, methods=["POST"])
    add(j("/order/vendor/modify/<int:order_id>"), view_func=vendor_order_services.modify_order_item, methods=["POST"])
    add(j("/order/vendor/cancel/<int:order_id>"), view_func=vendor_order_services.cancel_order_vendor, methods=["POST"])
    add(j("/order/vendor/message/send/<int:order_id>"), view_func=vendor_order_services.send_order_message_vendor, methods=["POST"])
    add(j("/order/vendor/messages/<int:order_id>"), view_func=vendor_order_services.get_order_messages_vendor, methods=["GET"])
    add(j("/order/vendor/issues"), view_func=vendor_order_services.get_issues_for_order, methods=["GET"])
    add(j("/order/return/vendor/accept/<int:order_id>"), view_func=vendor_order_services.accept_return, methods=["POST"])
    add(j("/order/return/complete/<int:order_id>"), view_func=vendor_order_services.complete_return, methods=["POST"])
    add(j("/order/return/vendor/initiate/<int:order_id>"), view_func=vendor_order_services.vendor_initiate_return, methods=["POST"])

