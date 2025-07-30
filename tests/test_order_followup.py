import pytest
from models.shop import Shop
from models.item import Item
from models.order import Order, OrderItem, OrderStatusLog, OrderActionLog, OrderMessage, OrderRating
from models.wallet import ConsumerWallet, VendorWallet, WalletTransaction, VendorWalletTransaction
from models import db
from app.version import API_PREFIX


def obtain_token(client, phone, role="consumer"):
    resp = client.post("/__auth/login_stub", json={"phone": phone, "role": role})
    return resp.get_json()["data"]["access"]


def onboard_consumer(client, token):
    basic = {'name': 'C', 'city': 'Town', 'society': 'Soc', 'role': 'consumer'}
    client.post(f"{API_PREFIX}/onboarding/basic", json=basic, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/consumer/onboarding", json={'flat_number': '1A'}, headers={'Authorization': f'Bearer {token}'})


def setup_vendor_with_items(client, app, phone):
    token = obtain_token(client, phone, role="vendor")
    client.post(f"{API_PREFIX}/onboarding/basic", json={'name': 'V', 'city': 'Town', 'society': 'Soc', 'role': 'vendor'}, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/vendor/profile", json={'business_type': 'retail', 'business_name': 'Shop', 'address': 'Addr'}, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/vendor/shop", json={'shop_name': 'MyShop', 'shop_type': 'grocery'}, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/item/add", json={'title': 'Item1', 'price': 20}, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/item/add", json={'title': 'Item2', 'price': 10}, headers={'Authorization': f'Bearer {token}'})
    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        items = Item.query.filter_by(shop_id=shop.id).all()
        item_ids = [i.id for i in items]
    return token, item_ids


def add_to_cart(client, token, item_id, qty):
    return client.post('/api/v1/consumer/cart/add', json={'item_id': item_id, 'quantity': qty}, headers={'Authorization': f'Bearer {token}'})


def load_wallet(client, token, amount):
    return client.post('/api/v1/consumer/wallet/load', json={'amount': amount}, headers={'Authorization': f'Bearer {token}'})


def place_order_with_two_items(client, app, suffix="1"):
    vendor_phone = f'900000000{suffix}'
    vendor_token, items = setup_vendor_with_items(client, app, vendor_phone)
    consumer_phone = f'910000000{suffix}'
    consumer_token = obtain_token(client, consumer_phone, role="consumer")
    onboard_consumer(client, consumer_token)
    add_to_cart(client, consumer_token, items[0], 1)
    add_to_cart(client, consumer_token, items[1], 1)
    load_wallet(client, consumer_token, 50)
    resp = client.post('/api/v1/consumer/order/confirm', json={'payment_mode': 'wallet'}, headers={'Authorization': f'Bearer {consumer_token}'})
    order_id = resp.get_json()['order_id']
    return {
        'order_id': order_id,
        'vendor_token': vendor_token,
        'consumer_token': consumer_token,
        'vendor_phone': vendor_phone,
        'consumer_phone': consumer_phone,
        'item_ids': items
    }


# ---------------- Confirm Modified Order ----------------

def test_confirm_modified_order_with_refund(client, app):
    ctx = place_order_with_two_items(client, app, "1")
    order_id = ctx['order_id']
    vendor_token = ctx['vendor_token']
    consumer_token = ctx['consumer_token']
    consumer_phone = ctx['consumer_phone']
    item_to_remove = ctx['item_ids'][1]

    # vendor modifies order - remove second item
    mod = {'modifications': [{'item_id': item_to_remove, 'quantity': 0}]}
    resp = client.post(f'/api/v1/vendor/orders/{order_id}/modify', json=mod, headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp.status_code == 200
    with app.app_context():
        order = Order.query.get(order_id)
        assert order.status == 'awaiting_consumer_confirmation'
        assert float(order.final_amount) == 20.0

    resp2 = client.post(f'/api/v1/consumer/order/confirm-modified/{order_id}', headers={'Authorization': f'Bearer {consumer_token}'})
    assert resp2.status_code == 200
    assert resp2.get_json()['refund'] == 10.0
    with app.app_context():
        order = Order.query.get(order_id)
        assert order.status == 'confirmed'
        wallet = ConsumerWallet.query.filter_by(user_phone=consumer_phone).first()
        assert float(wallet.balance) == 30.0
        assert OrderActionLog.query.filter_by(order_id=order_id, action_type='modification_confirmed').count() == 1

    # wrong state now
    resp_again = client.post(f'/api/v1/consumer/order/confirm-modified/{order_id}', headers={'Authorization': f'Bearer {consumer_token}'})
    assert resp_again.status_code == 400

    # unauthorized user
    other_token = obtain_token(client, '9100000002', role="consumer")
    onboard_consumer(client, other_token)
    resp_unauth = client.post(f'/api/v1/consumer/order/confirm-modified/{order_id}', headers={'Authorization': f'Bearer {other_token}'})
    assert resp_unauth.status_code == 403


# ---------------- Cancel Order Consumer ----------------

def test_cancel_order_consumer_with_wallet_refund(client, app):
    ctx = place_order_with_two_items(client, app, "2")
    order_id = ctx['order_id']
    consumer_token = ctx['consumer_token']
    consumer_phone = ctx['consumer_phone']

    resp = client.post(f'/api/v1/consumer/order/cancel/{order_id}', headers={'Authorization': consumer_token})
    assert resp.status_code == 200
    with app.app_context():
        order = Order.query.get(order_id)
        wallet = ConsumerWallet.query.filter_by(user_phone=consumer_phone).first()
        message = OrderMessage.query.filter_by(order_id=order_id).first()
        assert order.status == 'cancelled'
        assert float(wallet.balance) == 50.0
        assert message is not None
        assert OrderStatusLog.query.filter_by(order_id=order_id, status='cancelled').count() == 1

    resp_again = client.post(f'/api/v1/consumer/order/cancel/{order_id}', headers={'Authorization': f'Bearer {consumer_token}'})
    assert resp_again.status_code == 400

    other_token = obtain_token(client, '9100000003', role="consumer")
    onboard_consumer(client, other_token)
    resp_unauth = client.post(f'/api/v1/consumer/order/cancel/{order_id}', headers={'Authorization': f'Bearer {other_token}'})
    assert resp_unauth.status_code == 403


# ---------------- Vendor Modify Order ----------------

def test_vendor_modify_order_items(client, app):
    ctx = place_order_with_two_items(client, app, "3")
    order_id = ctx['order_id']
    vendor_token = ctx['vendor_token']
    vendor_phone = ctx['vendor_phone']
    item1, item2 = ctx['item_ids']

    mod_payload = {'modifications': [{'item_id': item1, 'quantity': 2}, {'item_id': item2, 'quantity': 0}]}
    resp = client.post(f'/api/v1/vendor/orders/{order_id}/modify', json=mod_payload, headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp.status_code == 200
    with app.app_context():
        order = Order.query.get(order_id)
        assert order.status == 'awaiting_consumer_confirmation'
        assert float(order.final_amount) == 40.0
        assert OrderItem.query.filter_by(order_id=order_id, item_id=item2).count() == 0
        oi = OrderItem.query.filter_by(order_id=order_id, item_id=item1).first()
        assert oi.quantity == 2
        assert OrderStatusLog.query.filter_by(order_id=order_id, status='awaiting_consumer_confirmation').count() == 1

    # unauthorized vendor
    other_vendor_token, _ = setup_vendor_with_items(client, app, '9000000002')
    resp_unauth = client.post(f'/api/v1/vendor/orders/{order_id}/modify', json=mod_payload, headers={'Authorization': f'Bearer {other_vendor_token}'})
    assert resp_unauth.status_code == 403

    # modify after cancelling should fail
    client.post(f'/api/v1/vendor/orders/{order_id}/cancel', headers={'Authorization': f'Bearer {vendor_token}'})
    resp_closed = client.post(f'/api/v1/vendor/orders/{order_id}/modify', json=mod_payload, headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp_closed.status_code == 400


# ---------------- Cancel Order Vendor ----------------

def test_cancel_order_vendor_refund(client, app):
    ctx = place_order_with_two_items(client, app, "4")
    order_id = ctx['order_id']
    vendor_token = ctx['vendor_token']
    consumer_phone = ctx['consumer_phone']

    resp = client.post(f'/api/v1/vendor/orders/{order_id}/cancel', headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp.status_code == 200
    with app.app_context():
        order = Order.query.get(order_id)
        wallet = ConsumerWallet.query.filter_by(user_phone=consumer_phone).first()
        assert order.status == 'cancelled'
        assert float(wallet.balance) == 50.0
        assert OrderMessage.query.filter_by(order_id=order_id).first() is not None

    resp_again = client.post(f'/api/v1/vendor/orders/{order_id}/cancel', headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp_again.status_code == 400

    other_vendor_token, _ = setup_vendor_with_items(client, app, '9000000003')
    resp_unauth = client.post(f'/api/v1/vendor/orders/{order_id}/cancel', headers={'Authorization': f'Bearer {other_vendor_token}'})
    assert resp_unauth.status_code == 403


# ---------------- Vendor Update Status ----------------

def test_vendor_update_status_and_payout(client, app):
    ctx = place_order_with_two_items(client, app, "5")
    order_id = ctx['order_id']
    vendor_token = ctx['vendor_token']
    vendor_phone = ctx['vendor_phone']

    resp = client.post(f'/api/v1/vendor/orders/{order_id}/status', json={'status': 'accepted'}, headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp.status_code == 200
    resp = client.post(f'/api/v1/vendor/orders/{order_id}/status', json={'status': 'delivered'}, headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp.status_code == 200
    with app.app_context():
        order = Order.query.get(order_id)
        v_wallet = VendorWallet.query.filter_by(user_phone=vendor_phone).first()
        assert order.status == 'delivered'
        assert float(v_wallet.balance) == 30.0
        assert VendorWalletTransaction.query.filter_by(user_phone=vendor_phone, reference=f'Order #{order_id} delivered').count() == 1

    # invalid status
    resp_bad = client.post(f'/api/v1/vendor/orders/{order_id}/status', json={'status': 'unknown'}, headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp_bad.status_code == 400

    other_vendor_token, _ = setup_vendor_with_items(client, app, '9000000004')
    resp_unauth = client.post(f'/api/v1/vendor/orders/{order_id}/status', json={'status': 'accepted'}, headers={'Authorization': f'Bearer {other_vendor_token}'})
    assert resp_unauth.status_code == 403


# ---------------- Messaging ----------------

def test_consumer_vendor_message_flow(client, app):
    ctx = place_order_with_two_items(client, app, "6")
    order_id = ctx['order_id']
    consumer_token = ctx['consumer_token']
    vendor_token = ctx['vendor_token']

    resp_missing = client.post(f'/api/v1/consumer/order/message/send/{order_id}', json={}, headers={'Authorization': consumer_token})
    assert resp_missing.status_code == 400

    resp = client.post(f'/api/v1/consumer/order/message/send/{order_id}', json={'message': 'Hello'}, headers={'Authorization': consumer_token})
    assert resp.status_code == 200

    resp2 = client.get(f'/api/v1/vendor/orders/{order_id}/messages', headers={'Authorization': f'Bearer {vendor_token}'})
    assert resp2.status_code == 200
    msgs = resp2.get_json()['messages']
    assert any(m['message'] == 'Hello' for m in msgs)


# ---------------- Rate Order ----------------

def test_rate_order_success_and_errors(client, app):
    ctx = place_order_with_two_items(client, app, "7")
    order_id = ctx['order_id']
    consumer_token = ctx['consumer_token']
    vendor_token = ctx['vendor_token']

    client.post(f'/api/v1/vendor/orders/{order_id}/status', json={'status': 'delivered'}, headers={'Authorization': f'Bearer {vendor_token}'})
    resp = client.post(f'/api/v1/consumer/order/rate/{order_id}', json={'rating': 5, 'review': 'Good'}, headers={'Authorization': consumer_token})
    assert resp.status_code == 200
    with app.app_context():
        assert OrderRating.query.filter_by(order_id=order_id).count() == 1

    resp_bad_range = client.post(f'/api/v1/consumer/order/rate/{order_id}', json={'rating': 6}, headers={'Authorization': consumer_token})
    assert resp_bad_range.status_code == 400

    ctx2 = place_order_with_two_items(client, app, "8")
    other_order = ctx2['order_id']
    resp_not_delivered = client.post(f'/api/v1/consumer/order/rate/{other_order}', json={'rating': 4}, headers={'Authorization': ctx2['consumer_token']})
    assert resp_not_delivered.status_code == 400

