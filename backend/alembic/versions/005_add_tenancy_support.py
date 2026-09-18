"""Add tenancy support with Tenant model and tenant_id columns

Revision ID: 005
Revises: 004
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create tenants table
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('subdomain', sa.String(100), nullable=False),
        sa.Column('schema_name', sa.String(100), nullable=False),
        sa.Column('plan', sa.String(50), server_default='starter', nullable=False),
        sa.Column('max_users', sa.Integer(), server_default='5', nullable=False),
        sa.Column('max_storage_gb', sa.Integer(), server_default='10', nullable=False),
        sa.Column('subscription_start', sa.Date(), nullable=False),
        sa.Column('subscription_end', sa.Date(), nullable=False),
        sa.Column('timezone', sa.String(50), server_default='UTC', nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD', nullable=False),
        sa.Column('locale', sa.String(10), server_default='en_US', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenants_subdomain'), 'tenants', ['subdomain'], unique=True)
    op.create_index(op.f('ix_tenants_schema_name'), 'tenants', ['schema_name'], unique=True)
    
    # Add tenant_id to users table
    op.add_column('users', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_tenant', 'users', 'tenants', ['tenant_id'], ['id'])
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    
    # Create vendors table
    op.create_table('vendors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('tax_id', sa.String(100), nullable=True),
        sa.Column('payment_terms', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_vendors_tenant_id', 'vendors', ['tenant_id'])
    
    # Create purchase_orders table
    op.create_table('purchase_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('po_number', sa.String(50), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), nullable=True),
        sa.Column('subtotal', sa.Numeric(15, 2), server_default='0', nullable=False),
        sa.Column('tax_amount', sa.Numeric(15, 2), server_default='0', nullable=False),
        sa.Column('total_amount', sa.Numeric(15, 2), server_default='0', nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD', nullable=False),
        sa.Column('status', sa.String(50), server_default='draft', nullable=False),
        sa.Column('approval_level', sa.Integer(), server_default='0', nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ordered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expected_delivery_date', sa.Date(), nullable=True),
        sa.Column('actual_delivery_date', sa.Date(), nullable=True),
        sa.Column('shipping_address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id']),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_purchase_orders_po_number', 'purchase_orders', ['po_number'], unique=True)
    op.create_index('ix_purchase_orders_status', 'purchase_orders', ['status'])
    op.create_index('ix_purchase_orders_vendor_id', 'purchase_orders', ['vendor_id'])
    op.create_index('ix_purchase_orders_tenant_id', 'purchase_orders', ['tenant_id'])
    
    # Create purchase_order_items table
    op.create_table('purchase_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 2), nullable=False),
        sa.Column('unit_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('total_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('received_quantity', sa.Numeric(10, 2), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create po_approvals table
    op.create_table('po_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), server_default='pending', nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create transaction_logs table
    op.create_table('transaction_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), server_default='completed', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transaction_logs_transaction_id', 'transaction_logs', ['transaction_id'], unique=True)
    op.create_index('ix_transaction_logs_entity', 'transaction_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_transaction_logs_tenant_id', 'transaction_logs', ['tenant_id'])


def downgrade():
    op.drop_table('transaction_logs')
    op.drop_table('po_approvals')
    op.drop_table('purchase_order_items')
    op.drop_table('purchase_orders')
    op.drop_table('vendors')
    
    op.drop_index('ix_users_tenant_id', table_name='users')
    op.drop_constraint('fk_users_tenant', 'users', type_='foreignkey')
    op.drop_column('users', 'tenant_id')
    
    op.drop_index('ix_tenants_schema_name', table_name='tenants')
    op.drop_index('ix_tenants_subdomain', table_name='tenants')
    op.drop_table('tenants')
