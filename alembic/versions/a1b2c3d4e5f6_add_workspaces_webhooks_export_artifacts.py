"""add_workspaces_webhooks_export_artifacts

Revision ID: a1b2c3d4e5f6
Revises: 80ee58e4d2ee
Create Date: 2026-10-14 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '80ee58e4d2ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add workspaces, workspace_members, webhooks, export_artifacts, and workspace_id columns."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. workspaces table
    if 'workspaces' not in existing_tables:
        op.create_table(
            'workspaces',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('slug', sa.String(length=100), nullable=False),
            sa.Column('owner_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_workspaces_id'), 'workspaces', ['id'], unique=False)
        op.create_index(op.f('ix_workspaces_slug'), 'workspaces', ['slug'], unique=True)
        op.create_index(op.f('ix_workspaces_owner_id'), 'workspaces', ['owner_id'], unique=False)

    # 2. workspace_members table
    if 'workspace_members' not in existing_tables:
        op.create_table(
            'workspace_members',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role', sa.String(length=50), nullable=True, server_default='member'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_member')
        )
        op.create_index(op.f('ix_workspace_members_id'), 'workspace_members', ['id'], unique=False)
        op.create_index(op.f('ix_workspace_members_workspace_id'), 'workspace_members', ['workspace_id'], unique=False)
        op.create_index(op.f('ix_workspace_members_user_id'), 'workspace_members', ['user_id'], unique=False)

    # 3. webhooks table
    if 'webhooks' not in existing_tables:
        op.create_table(
            'webhooks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=True),
            sa.Column('url', sa.String(length=500), nullable=False),
            sa.Column('secret', sa.String(length=100), nullable=False),
            sa.Column('events', sa.String(length=255), nullable=True, server_default='job.completed,job.failed'),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
            sa.Column('failure_count', sa.Integer(), nullable=True, server_default='0'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_webhooks_id'), 'webhooks', ['id'], unique=False)
        op.create_index(op.f('ix_webhooks_user_id'), 'webhooks', ['user_id'], unique=False)
        op.create_index(op.f('ix_webhooks_workspace_id'), 'webhooks', ['workspace_id'], unique=False)

    # 4. export_artifacts table
    if 'export_artifacts' not in existing_tables:
        op.create_table(
            'export_artifacts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=True),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('storage_path', sa.String(length=500), nullable=False),
            sa.Column('storage_backend', sa.String(length=50), nullable=True, server_default='local'),
            sa.Column('format', sa.String(length=20), nullable=False),
            sa.Column('file_size', sa.BigInteger(), nullable=True, server_default='0'),
            sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
            sa.Column('download_token', sa.String(length=64), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_export_artifacts_id'), 'export_artifacts', ['id'], unique=False)
        op.create_index(op.f('ix_export_artifacts_user_id'), 'export_artifacts', ['user_id'], unique=False)
        op.create_index(op.f('ix_export_artifacts_download_token'), 'export_artifacts', ['download_token'], unique=True)

    # 5. Add workspace_id columns to existing tables
    for tbl in ('repositories', 'crawl_jobs', 'api_keys'):
        cols = [c['name'] for c in inspector.get_columns(tbl)]
        with op.batch_alter_table(tbl, schema=None) as batch_op:
            if 'workspace_id' not in cols:
                batch_op.add_column(sa.Column('workspace_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(f'fk_{tbl}_workspace_id', 'workspaces', ['workspace_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for tbl in ('repositories', 'crawl_jobs', 'api_keys'):
        cols = [c['name'] for c in inspector.get_columns(tbl)]
        with op.batch_alter_table(tbl, schema=None) as batch_op:
            if 'workspace_id' in cols:
                batch_op.drop_column('workspace_id')

    existing_tables = inspector.get_table_names()
    if 'export_artifacts' in existing_tables:
        op.drop_table('export_artifacts')
    if 'webhooks' in existing_tables:
        op.drop_table('webhooks')
    if 'workspace_members' in existing_tables:
        op.drop_table('workspace_members')
    if 'workspaces' in existing_tables:
        op.drop_table('workspaces')
