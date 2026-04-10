"""add stripe billing foundation

Revision ID: c1f4e8b9a2d1
Revises: d9d1774a26cb
Create Date: 2026-01-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1f4e8b9a2d1'
down_revision = 'd9d1774a26cb'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('billing_plan_code', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('billing_status', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('stripe_subscription_id', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('billing_current_period_start', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('billing_current_period_end', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('billing_trial_ends_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('billing_cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('billing_internal_override', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('billing_override_reason', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('billing_demo_override_until', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('billing_last_event_id', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('billing_last_event_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.create_index('ix_organizations_billing_status', ['billing_status'], unique=False)
        batch_op.create_index('ix_organizations_stripe_customer_id', ['stripe_customer_id'], unique=False)

    op.create_table(
        'stripe_billing_webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=80), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', name='uq_stripe_billing_webhook_event_id'),
    )
    op.create_index(
        'ix_stripe_billing_webhook_events_org_processed',
        'stripe_billing_webhook_events',
        ['organization_id', 'processed_at'],
        unique=False,
    )

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.alter_column('billing_cancel_at_period_end', server_default=None)
        batch_op.alter_column('billing_internal_override', server_default=None)


def downgrade():
    op.drop_index('ix_stripe_billing_webhook_events_org_processed', table_name='stripe_billing_webhook_events')
    op.drop_table('stripe_billing_webhook_events')

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_index('ix_organizations_stripe_customer_id')
        batch_op.drop_index('ix_organizations_billing_status')
        batch_op.drop_column('billing_last_event_at')
        batch_op.drop_column('billing_last_event_id')
        batch_op.drop_column('billing_demo_override_until')
        batch_op.drop_column('billing_override_reason')
        batch_op.drop_column('billing_internal_override')
        batch_op.drop_column('billing_cancel_at_period_end')
        batch_op.drop_column('billing_trial_ends_at')
        batch_op.drop_column('billing_current_period_end')
        batch_op.drop_column('billing_current_period_start')
        batch_op.drop_column('stripe_subscription_id')
        batch_op.drop_column('stripe_customer_id')
        batch_op.drop_column('billing_status')
        batch_op.drop_column('billing_plan_code')
