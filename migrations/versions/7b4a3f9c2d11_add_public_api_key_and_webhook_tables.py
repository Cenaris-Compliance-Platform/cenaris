"""add public api key and webhook tables

Revision ID: 7b4a3f9c2d11
Revises: n3o4p5q6r7s8
Create Date: 2026-03-06 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b4a3f9c2d11'
down_revision = 'n3o4p5q6r7s8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash', name='uq_api_keys_hash'),
    )
    op.create_index('ix_api_keys_org_active', 'api_keys', ['organization_id', 'is_active'], unique=False)
    op.create_index('ix_api_keys_prefix', 'api_keys', ['key_prefix'], unique=False)

    op.create_table(
        'webhook_endpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('target_url', sa.String(length=500), nullable=False),
        sa.Column('events_csv', sa.Text(), nullable=False, server_default='*'),
        sa.Column('secret', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_endpoints_org_active', 'webhook_endpoints', ['organization_id', 'is_active'], unique=False)

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('webhook_endpoint_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_excerpt', sa.String(length=500), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['webhook_endpoint_id'], ['webhook_endpoints.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_deliveries_endpoint_attempted_at', 'webhook_deliveries', ['webhook_endpoint_id', 'attempted_at'], unique=False)
    op.create_index('ix_webhook_deliveries_event_attempted_at', 'webhook_deliveries', ['event_type', 'attempted_at'], unique=False)


def downgrade():
    op.drop_index('ix_webhook_deliveries_event_attempted_at', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_endpoint_attempted_at', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')

    op.drop_index('ix_webhook_endpoints_org_active', table_name='webhook_endpoints')
    op.drop_table('webhook_endpoints')

    op.drop_index('ix_api_keys_prefix', table_name='api_keys')
    op.drop_index('ix_api_keys_org_active', table_name='api_keys')
    op.drop_table('api_keys')
