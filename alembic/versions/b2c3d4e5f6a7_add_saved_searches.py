"""add_saved_searches

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-14 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'saved_searches' not in existing_tables:
        op.create_table(
            'saved_searches',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('query_params', sa.Text(), nullable=False),
            sa.Column('notify_on_new', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('last_checked_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_saved_searches_id'), 'saved_searches', ['id'], unique=False)
        op.create_index(op.f('ix_saved_searches_user_id'), 'saved_searches', ['user_id'], unique=False)
        op.create_index(op.f('ix_saved_searches_workspace_id'), 'saved_searches', ['workspace_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'saved_searches' in existing_tables:
        op.drop_index(op.f('ix_saved_searches_workspace_id'), table_name='saved_searches')
        op.drop_index(op.f('ix_saved_searches_user_id'), table_name='saved_searches')
        op.drop_index(op.f('ix_saved_searches_id'), table_name='saved_searches')
        op.drop_table('saved_searches')
