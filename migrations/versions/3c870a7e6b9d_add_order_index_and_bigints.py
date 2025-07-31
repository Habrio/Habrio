"""add order composite index and bigint keys

Revision ID: 3c870a7e6b9d
Revises: 055cb63f2358
Create Date: 2025-07-31 06:15:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3c870a7e6b9d'
down_revision = '055cb63f2358'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_order_shop_status', 'order', ['shop_id', 'status'])
    op.alter_column('order', 'id', type_=sa.BigInteger())
    op.alter_column('order', 'shop_id', type_=sa.BigInteger())
    op.alter_column('order_item', 'id', type_=sa.BigInteger())
    op.alter_column('order_item', 'order_id', type_=sa.BigInteger())
    op.alter_column('order_messages', 'id', type_=sa.BigInteger())
    op.alter_column('order_messages', 'order_id', type_=sa.BigInteger())
    op.alter_column('order_status_log', 'id', type_=sa.BigInteger())
    op.alter_column('order_status_log', 'order_id', type_=sa.BigInteger())
    op.alter_column('order_action_log', 'id', type_=sa.BigInteger())
    op.alter_column('order_action_log', 'order_id', type_=sa.BigInteger())
    op.alter_column('order_rating', 'id', type_=sa.BigInteger())
    op.alter_column('order_rating', 'order_id', type_=sa.BigInteger())
    op.alter_column('order_issue', 'id', type_=sa.BigInteger())
    op.alter_column('order_issue', 'order_id', type_=sa.BigInteger())
    op.alter_column('order_return', 'id', type_=sa.BigInteger())
    op.alter_column('order_return', 'order_id', type_=sa.BigInteger())


def downgrade():
    op.drop_index('ix_order_shop_status', table_name='order')
    op.alter_column('order_return', 'order_id', type_=sa.Integer())
    op.alter_column('order_return', 'id', type_=sa.Integer())
    op.alter_column('order_issue', 'order_id', type_=sa.Integer())
    op.alter_column('order_issue', 'id', type_=sa.Integer())
    op.alter_column('order_rating', 'order_id', type_=sa.Integer())
    op.alter_column('order_rating', 'id', type_=sa.Integer())
    op.alter_column('order_action_log', 'order_id', type_=sa.Integer())
    op.alter_column('order_action_log', 'id', type_=sa.Integer())
    op.alter_column('order_status_log', 'order_id', type_=sa.Integer())
    op.alter_column('order_status_log', 'id', type_=sa.Integer())
    op.alter_column('order_messages', 'order_id', type_=sa.Integer())
    op.alter_column('order_messages', 'id', type_=sa.Integer())
    op.alter_column('order_item', 'order_id', type_=sa.Integer())
    op.alter_column('order_item', 'id', type_=sa.Integer())
    op.alter_column('order', 'shop_id', type_=sa.Integer())
    op.alter_column('order', 'id', type_=sa.Integer())
