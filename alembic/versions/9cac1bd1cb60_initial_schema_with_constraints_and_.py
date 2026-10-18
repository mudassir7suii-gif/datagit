"""initial_schema_with_constraints_and_audit

Revision ID: 9cac1bd1cb60
Revises: 
Create Date: 2026-10-12 23:59:46.970554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cac1bd1cb60'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create initial core tables or apply constraints if already present."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. users
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
            sa.Column('plan', sa.String(length=50), nullable=True, server_default='free'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. repositories
    if 'repositories' not in existing_tables:
        op.create_table(
            'repositories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('github_id', sa.BigInteger(), nullable=True),
            sa.Column('owner', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('full_name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('url', sa.String(length=255), nullable=False),
            sa.Column('language', sa.String(length=100), nullable=True),
            sa.Column('stars', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('forks', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('open_issues', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('default_branch', sa.String(length=100), nullable=True, server_default='main'),
            sa.Column('is_fork', sa.Boolean(), nullable=True, server_default='0'),
            sa.Column('is_private', sa.Boolean(), nullable=True, server_default='0'),
            sa.Column('is_archived', sa.Boolean(), nullable=True, server_default='0'),
            sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default='0'),
            sa.Column('repo_created_at', sa.DateTime(), nullable=True),
            sa.Column('repo_updated_at', sa.DateTime(), nullable=True),
            sa.Column('repo_pushed_at', sa.DateTime(), nullable=True),
            sa.Column('crawled_at', sa.DateTime(), nullable=True),
            sa.Column('content_hash', sa.String(length=64), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_repositories_id'), 'repositories', ['id'], unique=False)
        op.create_index(op.f('ix_repositories_full_name'), 'repositories', ['full_name'], unique=True)
        op.create_index(op.f('ix_repositories_github_id'), 'repositories', ['github_id'], unique=True)
        op.create_index(op.f('ix_repositories_owner'), 'repositories', ['owner'], unique=False)
        op.create_index(op.f('ix_repositories_name'), 'repositories', ['name'], unique=False)
        op.create_index(op.f('ix_repositories_language'), 'repositories', ['language'], unique=False)
        op.create_index(op.f('ix_repositories_stars'), 'repositories', ['stars'], unique=False)
        op.create_index(op.f('ix_repositories_crawled_at'), 'repositories', ['crawled_at'], unique=False)
        op.create_index(op.f('ix_repositories_is_deleted'), 'repositories', ['is_deleted'], unique=False)
    else:
        repo_cols = [c['name'] for c in inspector.get_columns('repositories')]
        with op.batch_alter_table('repositories', schema=None) as batch_op:
            if 'is_archived' not in repo_cols:
                batch_op.add_column(sa.Column('is_archived', sa.Boolean(), nullable=True, server_default='0'))
            if 'is_deleted' not in repo_cols:
                batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default='0'))
                batch_op.create_index(batch_op.f('ix_repositories_is_deleted'), ['is_deleted'], unique=False)

    # 3. commits
    if 'commits' not in existing_tables:
        op.create_table(
            'commits',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('repo_id', sa.Integer(), nullable=False),
            sa.Column('sha', sa.String(length=40), nullable=False),
            sa.Column('author_name', sa.String(length=150), nullable=True),
            sa.Column('author_email', sa.String(length=255), nullable=True),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('committed_at', sa.DateTime(), nullable=True),
            sa.Column('url', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('repo_id', 'sha', name='uq_commit_repo_sha')
        )
        op.create_index(op.f('ix_commits_id'), 'commits', ['id'], unique=False)
        op.create_index(op.f('ix_commits_repo_id'), 'commits', ['repo_id'], unique=False)
        op.create_index(op.f('ix_commits_sha'), 'commits', ['sha'], unique=False)
    else:
        with op.batch_alter_table('commits', schema=None) as batch_op:
            try:
                batch_op.create_unique_constraint('uq_commit_repo_sha', ['repo_id', 'sha'])
            except Exception:
                pass

    # 4. issues
    if 'issues' not in existing_tables:
        op.create_table(
            'issues',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('repo_id', sa.Integer(), nullable=False),
            sa.Column('github_number', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('state', sa.String(length=50), nullable=True, server_default='open'),
            sa.Column('author', sa.String(length=100), nullable=True),
            sa.Column('comments_count', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('is_pull_request', sa.Boolean(), nullable=True, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.Column('url', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('repo_id', 'github_number', name='uq_issue_repo_number')
        )
        op.create_index(op.f('ix_issues_id'), 'issues', ['id'], unique=False)
        op.create_index(op.f('ix_issues_repo_id'), 'issues', ['repo_id'], unique=False)
        op.create_index(op.f('ix_issues_github_number'), 'issues', ['github_number'], unique=False)
        op.create_index(op.f('ix_issues_state'), 'issues', ['state'], unique=False)
    else:
        with op.batch_alter_table('issues', schema=None) as batch_op:
            try:
                batch_op.create_unique_constraint('uq_issue_repo_number', ['repo_id', 'github_number'])
            except Exception:
                pass

    # 5. crawl_jobs
    if 'crawl_jobs' not in existing_tables:
        op.create_table(
            'crawl_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('target', sa.String(length=255), nullable=False),
            sa.Column('target_type', sa.String(length=50), nullable=True, server_default='org'),
            sa.Column('depth', sa.String(length=50), nullable=True, server_default='metadata'),
            sa.Column('status', sa.String(length=50), nullable=True, server_default='queued'),
            sa.Column('total_found', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('items_crawled', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_crawl_jobs_id'), 'crawl_jobs', ['id'], unique=False)
        op.create_index(op.f('ix_crawl_jobs_target'), 'crawl_jobs', ['target'], unique=False)
        op.create_index(op.f('ix_crawl_jobs_status'), 'crawl_jobs', ['status'], unique=False)
    else:
        with op.batch_alter_table('crawl_jobs', schema=None) as batch_op:
            try:
                batch_op.create_index(batch_op.f('ix_crawl_jobs_status'), ['status'], unique=False)
            except Exception:
                pass

    # 6. rate_limit_states
    if 'rate_limit_states' not in existing_tables:
        op.create_table(
            'rate_limit_states',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('token_masked', sa.String(length=50), nullable=False),
            sa.Column('limit', sa.Integer(), nullable=True, server_default='5000'),
            sa.Column('remaining', sa.Integer(), nullable=True, server_default='5000'),
            sa.Column('reset_timestamp', sa.Float(), nullable=True, server_default='0.0'),
            sa.Column('last_used', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_rate_limit_states_id'), 'rate_limit_states', ['id'], unique=False)
        op.create_index(op.f('ix_rate_limit_states_token_masked'), 'rate_limit_states', ['token_masked'], unique=True)

    # 7. audit_logs
    if 'audit_logs' not in existing_tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_email', sa.String(length=255), nullable=False),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('target', sa.String(length=255), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
        op.create_index(op.f('ix_audit_logs_user_email'), 'audit_logs', ['user_email'], unique=False)
        op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)

    # 8. api_keys
    if 'api_keys' not in existing_tables:
        op.create_table(
            'api_keys',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('key_prefix', sa.String(length=16), nullable=False),
            sa.Column('key_hash', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('is_revoked', sa.Boolean(), nullable=True, server_default='0'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
        op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)
        op.create_index(op.f('ix_api_keys_key_prefix'), 'api_keys', ['key_prefix'], unique=False)
        op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)
        op.create_index(op.f('ix_api_keys_is_revoked'), 'api_keys', ['is_revoked'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    for tbl in ('api_keys', 'audit_logs', 'rate_limit_states', 'issues', 'commits', 'crawl_jobs', 'repositories', 'users'):
        if tbl in existing_tables:
            op.drop_table(tbl)

