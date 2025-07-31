import pytest
from sqlalchemy import text, inspect
from models import db
from models.order import Order


def test_order_shop_status_index_used(app):
    with app.app_context():
        db.create_all()
        insp = inspect(db.engine)
        assert any(ix['name'] == 'ix_order_shop_status' for ix in insp.get_indexes('order'))
        db.session.add(Order(user_phone='u', shop_id=1, status='pending', payment_mode='cash', payment_status='unpaid', total_amount=1))
        db.session.commit()
        plan_rows = db.session.execute(text("EXPLAIN QUERY PLAN SELECT * FROM 'order' WHERE shop_id=1 AND status='pending'"))
        plan = " ".join(r[3] for r in plan_rows)
        assert 'USING INDEX ix_order_shop_status' in plan
