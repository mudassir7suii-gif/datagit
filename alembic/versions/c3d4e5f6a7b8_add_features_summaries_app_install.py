"""add_features_summaries_app_install

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-18 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Add github_app_installation_id to workspaces
    if 'workspaces' in existing_tables:
        ws_cols = [c['name'] for c in inspector.get_columns('workspaces')]
        if 'github_app_installation_id' not in ws_cols:
            op.add_column('workspaces', sa.Column('github_app_installation_id', sa.String(length=100), nullable=True))

    # Add ai_summary to repositories
    if 'repositories' in existing_tables:
        repo_cols = [c['name'] for c in inspector.get_columns('repositories')]
        if 'ai_summary' not in repo_cols:
            op.add_column('repositories', sa.Column('ai_summary', sa.Text(), nullable=True))

    # Create feature_flags table
    if 'feature_flags' not in existing_tables:
        op.create_table(
            'feature_flags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_feature_flags_id'), 'feature_flags', ['id'], unique=False)
        op.create_index(op.f('ix_feature_flags_name'), 'feature_flags', ['name'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'feature_flags' in existing_tables:
        op.drop_index(op.f('ix_feature_flags_name'), table_name='feature_flags')
        op.drop_index(op.f('ix_feature_flags_id'), table_name='feature_flags')
        op.drop_table('feature_flags')

    if 'repositories' in existing_tables:
        repo_cols = [c['name'] for c in inspector.get_columns('repositories')]
        if 'ai_summary' in repo_cols:
            with op.batch_alter_table('repositories', schema=None) as batch_op:
                batch_op.drop_column('ai_summary')

    if 'workspaces' in existing_tables:
        ws_cols = [c['name'] for c in inspector.get_columns('workspaces')]
        if 'github_app_installation_id' in ws_cols:
            with op.batch_alter_table('workspaces', schema=None) as batch_op:
                batch_op.drop_column('github_app_installation_id')
