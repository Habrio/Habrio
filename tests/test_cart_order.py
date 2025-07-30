import pytest
from models.shop import Shop
from models.item import Item
from models.cart import CartItem
from models.order import Order, OrderItem
from models.wallet import ConsumerWallet, WalletTransaction
from models import db
from app.version import API_PREFIX


def obtain_token(client, phone, role="consumer"):
    resp = client.post("/__auth/login_stub", json={"phone": phone, "role": role})
    return resp.get_json()["data"]["access"]


def onboard_consumer(client, token):
    basic = {
        'name': 'C1',
        'city': 'Town',
        'society': 'Soc',
        'role': 'consumer'
    }
    client.post(f"{API_PREFIX}/onboarding/basic", json=basic, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/consumer/onboarding", json={'flat_number': '1A'}, headers={'Authorization': f'Bearer {token}'})


def create_item(app, price=10.0):
    with app.app_context():
        shop = Shop(shop_name='S1', shop_type='grocery', society='Soc', city='Town', phone='800')
        db.session.add(shop)
        db.session.flush()
        item = Item(shop_id=shop.id, title='Apple', price=price, mrp=price+2, unit='kg', pack_size='1kg', is_available=True, quantity_in_stock=100)
        db.session.add(item)
        db.session.commit()
        return item.id, shop.id


def add_to_cart_helper(client, token, item_id, qty):
    return client.post(f"{API_PREFIX}/consumer/cart/add", json={'item_id': item_id, 'quantity': qty}, headers={'Authorization': f'Bearer {token}'})


def load_wallet(client, token, amount):
    return client.post(f"{API_PREFIX}/consumer/wallet/load", json={'amount': amount}, headers={'Authorization': f'Bearer {token}'})


# -------------------- Cart Operations --------------------

def test_cart_add_view_update_remove_clear(client, app):
    phone = '9123400000'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    item_id, _ = create_item(app)

    # add to cart
    resp = add_to_cart_helper(client, token, item_id, 2)
    assert resp.status_code == 200
    with app.app_context():
        ci = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
        assert ci and ci.quantity == 2

    # view cart
    view = client.get('/api/v1/consumer/cart/view', headers={'Authorization': f'Bearer {token}'})
    data = view.get_json()
    assert view.status_code == 200
    assert len(data['cart']) == 1
    assert data['cart'][0]['quantity'] == 2
    assert data['cart'][0]['item_id'] == item_id

    # update quantity
    resp = client.post('/api/v1/consumer/cart/update', json={'item_id': item_id, 'quantity': 3}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    with app.app_context():
        assert CartItem.query.filter_by(user_phone=phone, item_id=item_id).first().quantity == 3

    # remove item
    resp = client.post('/api/v1/consumer/cart/remove', json={'item_id': item_id}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    with app.app_context():
        assert CartItem.query.filter_by(user_phone=phone).count() == 0

    # add again then clear
    add_to_cart_helper(client, token, item_id, 1)
    resp = client.post('/api/v1/consumer/cart/clear', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    view = client.get('/api/v1/consumer/cart/view', headers={'Authorization': f'Bearer {token}'})
    assert view.get_json()['cart'] == []


def test_cart_add_invalid_item(client, app):
    phone = '9123400001'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    # non existing item
    resp = add_to_cart_helper(client, token, 9999, 1)
    assert resp.status_code == 404


def test_cart_add_missing_fields(client, app):
    phone = '9123400004'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    item_id, _ = create_item(app)

    resp = client.post('/api/v1/consumer/cart/add', json={'quantity': 1}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 404

    resp = client.post('/api/v1/consumer/cart/add', json={'item_id': item_id, 'quantity': 0}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400


def test_update_cart_invalid_request(client, app):
    phone = '9123400005'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    item_id, _ = create_item(app)

    add_to_cart_helper(client, token, item_id, 1)

    resp = client.post('/api/v1/consumer/cart/update', json={'item_id': item_id, 'quantity': 0}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400

    resp = client.post('/api/v1/consumer/cart/update', json={'quantity': 2}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400

    resp = client.post('/api/v1/consumer/cart/update', json={'item_id': item_id + 1, 'quantity': 2}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 404


# -------------------- Order Placement --------------------

def test_confirm_order_wallet_and_cash(client, app):
    phone = '9123400002'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    item_id, _ = create_item(app, price=15)

    add_to_cart_helper(client, token, item_id, 2)  # total 30
    load_wallet(client, token, 50)
    resp = client.post('/api/v1/consumer/order/confirm', json={'payment_mode': 'wallet'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    order_id = resp.get_json()['order_id']
    with app.app_context():
        wallet = ConsumerWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 20.0
        order = Order.query.get(order_id)
        assert order.payment_mode == 'wallet'
        assert order.payment_status == 'paid'
        assert order.status == 'pending'
        assert OrderItem.query.filter_by(order_id=order_id).count() == 1
        assert WalletTransaction.query.filter_by(user_phone=phone, type='debit').count() == 1
        assert CartItem.query.filter_by(user_phone=phone).count() == 0
    assert client.get('/api/v1/consumer/cart/view', headers={'Authorization': f'Bearer {token}'}).get_json()['cart'] == []

    # cash mode
    add_to_cart_helper(client, token, item_id, 1)
    resp = client.post('/api/v1/consumer/order/confirm', json={'payment_mode': 'cash'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    order_id2 = resp.get_json()['order_id']
    with app.app_context():
        wallet = ConsumerWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 20.0  # unchanged
        order2 = Order.query.get(order_id2)
        assert order2.payment_mode == 'cash'
        assert order2.payment_status == 'unpaid'
        assert OrderItem.query.filter_by(order_id=order_id2).count() == 1


def test_confirm_order_errors(client, app):
    phone = '9123400003'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    item_id, _ = create_item(app, price=10)

    # empty cart
    resp = client.post('/api/v1/consumer/order/confirm', json={'payment_mode': 'cash'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400

    # insufficient wallet balance
    add_to_cart_helper(client, token, item_id, 5)  # total 50
    load_wallet(client, token, 20)
    resp = client.post('/api/v1/consumer/order/confirm', json={'payment_mode': 'wallet'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400
