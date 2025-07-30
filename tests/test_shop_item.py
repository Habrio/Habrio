import io
import pandas as pd
import pytest
from models.shop import Shop
from models.vendor import VendorProfile
from models.item import Item
from models import db
from app.version import API_PREFIX


def obtain_token(client, phone, *args):
    resp = client.post("/__auth/login_stub", json={"phone": phone, "role": "vendor"})
    return resp.get_json()["data"]["access"]


def do_basic_onboarding(client, token, role='vendor'):
    payload = {
        'name': 'Vendor',
        'city': 'City',
        'society': 'Society',
        'role': role
    }
    return client.post(f"{API_PREFIX}/onboarding/basic", json=payload, headers={'Authorization': f'Bearer {token}'})


def setup_vendor_with_profile(client, app, phone):
    token = obtain_token(client, phone)
    do_basic_onboarding(client, token, role='vendor')
    profile_payload = {
        'business_type': 'retail',
        'business_name': f'Shop{phone[-2:]}',
        'address': 'Addr'
    }
    client.post(f"{API_PREFIX}/vendor/profile", json=profile_payload, headers={'Authorization': f'Bearer {token}'})
    return token


def create_shop_for_vendor(client, token, name='MyShop'):
    payload = {'shop_name': name, 'shop_type': 'grocery'}
    return client.post(f"{API_PREFIX}/vendor/shop", json=payload, headers={'Authorization': f'Bearer {token}'})


def add_item_for_vendor(client, token, title='Item', price=1.0):
    payload = {'title': title, 'price': price}
    return client.post(f"{API_PREFIX}/vendor/item/add", json=payload, headers={'Authorization': f'Bearer {token}'})


def test_create_shop_success_and_duplicate(client, app):
    phone = '8100000001'
    token = setup_vendor_with_profile(client, app, phone)

    resp = create_shop_for_vendor(client, token, 'TestShop')
    assert resp.status_code == 200

    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        profile = VendorProfile.query.filter_by(user_phone=phone).first()
        assert shop is not None
        assert shop.shop_name == 'TestShop'
        assert profile.shop_id == shop.id

    resp_dup = create_shop_for_vendor(client, token, 'Another')
    assert resp_dup.status_code == 400
    assert resp_dup.get_json()['message'] == 'Shop already exists for this vendor'

    phone2 = '8100000002'
    token2 = obtain_token(client, phone2)
    do_basic_onboarding(client, token2, role='vendor')
    resp_no_profile = create_shop_for_vendor(client, token2, 'NoProfile')
    assert resp_no_profile.status_code == 400
    assert 'Vendor profile not found' in resp_no_profile.get_json()['message']


def test_edit_shop_success_and_not_found(client, app):
    phone = '8100000003'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'EditShop')

    resp = client.post('/api/v1/vendor/shop/edit', json={'description': 'New', 'is_open': False}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        assert shop.description == 'New'
        assert shop.is_open is False

    phone2 = '8100000004'
    token2 = setup_vendor_with_profile(client, app, phone2)
    resp_nf = client.post('/api/v1/vendor/shop/edit', json={'description': 'X'}, headers={'Authorization': f'Bearer {token2}'})
    assert resp_nf.status_code == 404
    assert resp_nf.get_json()['message'] == 'Shop not found'


def test_toggle_shop_status(client, app):
    phone = '8100000005'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'ToggleShop')

    resp_close = client.post('/api/v1/vendor/shop/toggle-status', json={'is_open': False}, headers={'Authorization': f'Bearer {token}'})
    assert resp_close.status_code == 200
    with app.app_context():
        assert Shop.query.filter_by(phone=phone).first().is_open is False

    resp_open = client.post('/api/v1/vendor/shop/toggle-status', json={'is_open': True}, headers={'Authorization': f'Bearer {token}'})
    assert resp_open.status_code == 200
    with app.app_context():
        assert Shop.query.filter_by(phone=phone).first().is_open is True

    resp_invalid = client.post('/api/v1/vendor/shop/toggle-status', json={'is_open': 'yes'}, headers={'Authorization': f'Bearer {token}'})
    assert resp_invalid.status_code == 400
    assert resp_invalid.get_json()['message'] == 'Invalid is_open value'


def test_add_item_success_and_errors(client, app):
    phone = '8100000006'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'ItemShop')

    resp = add_item_for_vendor(client, token, 'Item1', 10)
    assert resp.status_code == 200
    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        item = Item.query.filter_by(shop_id=shop.id).first()
        assert item.title == 'Item1'

    resp_missing = client.post('/api/v1/vendor/item/add', json={'title': 'NoPrice'}, headers={'Authorization': f'Bearer {token}'})
    assert resp_missing.status_code == 400

    phone2 = '8100000007'
    token2 = setup_vendor_with_profile(client, app, phone2)
    resp_no_shop = add_item_for_vendor(client, token2, 'ItemX', 5)
    assert resp_no_shop.status_code == 404
    assert resp_no_shop.get_json()['message'] == 'Shop not found'


def test_update_item(client, app):
    phone = '8100000008'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'UpShop')
    add_item_for_vendor(client, token, 'UpItem', 5)
    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        item_id = Item.query.filter_by(shop_id=shop.id).first().id

    resp = client.post(f'/api/v1/vendor/item/update/{item_id}', json={'price': 8, 'quantity_in_stock': 10}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    with app.app_context():
        item = Item.query.get(item_id)
        assert item.price == 8
        assert item.quantity_in_stock == 10

    resp_bad = client.post(f'/api/v1/vendor/item/update/{item_id + 999}', json={'price': 9}, headers={'Authorization': f'Bearer {token}'})
    assert resp_bad.status_code == 404

    phone2 = '8100000009'
    token2 = setup_vendor_with_profile(client, app, phone2)
    create_shop_for_vendor(client, token2, 'OtherShop')
    resp_unauth = client.post(f'/api/v1/vendor/item/update/{item_id}', json={'price': 7}, headers={'Authorization': f'Bearer {token2}'})
    assert resp_unauth.status_code == 404


def test_toggle_item_availability(client, app):
    phone = '8100000010'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'ToggleItemShop')
    add_item_for_vendor(client, token, 'TItem', 2)
    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        item_id = Item.query.filter_by(shop_id=shop.id).first().id
        assert Item.query.get(item_id).is_available is True

    resp1 = client.post(f'/api/v1/vendor/item/{item_id}/toggle', headers={'Authorization': f'Bearer {token}'})
    assert resp1.status_code == 200
    with app.app_context():
        assert Item.query.get(item_id).is_available is False

    resp2 = client.post(f'/api/v1/vendor/item/{item_id}/toggle', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    with app.app_context():
        assert Item.query.get(item_id).is_available is True

    phone2 = '8100000011'
    token2 = setup_vendor_with_profile(client, app, phone2)
    create_shop_for_vendor(client, token2, 'Shop2')
    resp_unauth = client.post(f'/api/v1/vendor/item/{item_id}/toggle', headers={'Authorization': f'Bearer {token2}'})
    assert resp_unauth.status_code == 404


def test_get_items(client, app):
    phone = '8100000012'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'ListShop')
    add_item_for_vendor(client, token, 'L1', 1)
    add_item_for_vendor(client, token, 'L2', 2)

    resp = client.get('/api/v1/vendor/item/my', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert len(data) == 2
    titles = {i['title'] for i in data}
    assert titles == {'L1', 'L2'}

    phone2 = '8100000013'
    token2 = setup_vendor_with_profile(client, app, phone2)
    resp_no_shop = client.get('/api/v1/vendor/item/my', headers={'Authorization': f'Bearer {token2}'})
    assert resp_no_shop.status_code == 404
    assert resp_no_shop.get_json()['message'] == 'Shop not found'


def test_bulk_upload_items(client, app):
    phone = '8100000014'
    token = setup_vendor_with_profile(client, app, phone)
    create_shop_for_vendor(client, token, 'BulkShop')

    df = pd.DataFrame([{'title': 'B1', 'price': 1}, {'title': 'B2', 'price': 2}])
    csv_io = io.BytesIO()
    csv_io.write(df.to_csv(index=False).encode())
    csv_io.seek(0)
    resp = client.post('/api/v1/vendor/item/bulk-upload', data={'file': (csv_io, 'items.csv')}, headers={'Authorization': f'Bearer {token}'}, content_type='multipart/form-data')
    assert resp.status_code == 200
    assert '2 items uploaded' in resp.get_json()['message']
    with app.app_context():
        shop = Shop.query.filter_by(phone=phone).first()
        assert Item.query.filter_by(shop_id=shop.id).count() == 2

    resp_ext = client.post('/api/v1/vendor/item/bulk-upload', data={'file': (io.BytesIO(b'abc'), 'items.txt')}, headers={'Authorization': f'Bearer {token}'}, content_type='multipart/form-data')
    assert resp_ext.status_code == 400
    assert resp_ext.get_json()['message'] == 'Unsupported file type'

    df2 = pd.DataFrame([{'title': 'OnlyTitle'}])
    csv_io2 = io.BytesIO()
    csv_io2.write(df2.to_csv(index=False).encode())
    csv_io2.seek(0)
    resp_missing = client.post('/api/v1/vendor/item/bulk-upload', data={'file': (csv_io2, 'bad.csv')}, headers={'Authorization': f'Bearer {token}'}, content_type='multipart/form-data')
    assert resp_missing.status_code == 400
    assert 'Missing columns' in resp_missing.get_json()['message']

