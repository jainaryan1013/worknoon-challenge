"""add conversations.session_token

Per-conversation capability token (scope-1 hardening): acting on a conversation
via /api/chat requires presenting this server-minted token, so a leaked/guessed
conversation id alone can no longer drive a verified conversation.

Added NOT NULL with no default and no backfill: the DB volume is reset once on
deploy of this change (`make reset-db`), so the table is empty at upgrade time.

Revision ID: a1b2c3d4e5f6
Revises: 765ba2da5a11
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '765ba2da5a11'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('session_token', sa.Text(), nullable=False))
    op.create_unique_constraint(
        op.f('uq_conversations_session_token'), 'conversations', ['session_token']
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('uq_conversations_session_token'), 'conversations', type_='unique'
    )
    op.drop_column('conversations', 'session_token')
