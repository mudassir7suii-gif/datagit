"""add_auth_lockout_columns

Revision ID: 80ee58e4d2ee
Revises: 9cac1bd1cb60
Create Date: 2026-10-14 03:29:52.629410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80ee58e4d2ee'
down_revision: Union[str, Sequence[str], None] = '9cac1bd1cb60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('users')]
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'failed_login_attempts' not in existing_cols:
            batch_op.add_column(sa.Column('failed_login_attempts', sa.Integer(), nullable=True, server_default='0'))
        if 'locked_until' not in existing_cols:
            batch_op.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('users')]
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'locked_until' in existing_cols:
            batch_op.drop_column('locked_until')
        if 'failed_login_attempts' in existing_cols:
            batch_op.drop_column('failed_login_attempts')
