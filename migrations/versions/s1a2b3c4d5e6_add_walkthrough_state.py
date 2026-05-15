"""Add walkthrough_state and walkthrough_stages tables for guided onboarding experience.

Revision ID: s1a2b3c4d5e6
Revises: r4s5t6u7v8w9
Create Date: 2026-05-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's1a2b3c4d5e6'
down_revision = 'r4s5t6u7v8w9'
branch_labels = None
depends_on = None


def upgrade():
    # Create walkthrough_states table
    op.create_table(
        'walkthrough_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('walkthrough_key', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False, server_default='not_started'),
        sa.Column('current_stage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('eligible', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('auto_triggered', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('manual_triggered', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('dismissed_until', sa.DateTime(), nullable=True),
        sa.Column('permanently_dismissed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('first_started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_interacted_at', sa.DateTime(), nullable=True),
        sa.Column('completion_percentage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stages_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_stages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('walkthrough_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', 'walkthrough_key', name='uq_walkthrough_state_org_user_key'),
    )
    op.create_index('ix_walkthrough_state_org_user', 'walkthrough_states', ['organization_id', 'user_id'])
    op.create_index('ix_walkthrough_state_org_state', 'walkthrough_states', ['organization_id', 'state'])
    op.create_index('ix_walkthrough_state_user_eligible', 'walkthrough_states', ['user_id', 'eligible'])

    # Create walkthrough_stages table
    op.create_table(
        'walkthrough_stages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('walkthrough_state_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('target_element', sa.String(length=500), nullable=True),
        sa.Column('stage_order', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('cta_text', sa.String(length=100), nullable=True),
        sa.Column('cta_action', sa.String(length=200), nullable=True),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('completion_criteria', sa.String(length=200), nullable=True),
        sa.Column('auto_advance_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['walkthrough_state_id'], ['walkthrough_states.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_walkthrough_stage_state_order', 'walkthrough_stages', ['walkthrough_state_id', 'stage_order'])


def downgrade():
    op.drop_index('ix_walkthrough_stage_state_order', 'walkthrough_stages')
    op.drop_table('walkthrough_stages')
    op.drop_index('ix_walkthrough_state_user_eligible', 'walkthrough_states')
    op.drop_index('ix_walkthrough_state_org_state', 'walkthrough_states')
    op.drop_index('ix_walkthrough_state_org_user', 'walkthrough_states')
    op.drop_table('walkthrough_states')

