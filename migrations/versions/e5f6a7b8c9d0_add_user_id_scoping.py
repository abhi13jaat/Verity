"""add user_id scoping to documents + conversation_history; per-user file_hash uniqueness

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # documents.user_id (nullable FK for now; tightened after backfill/reset)
    op.add_column("documents", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_foreign_key(
        "fk_documents_user_id", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    # Per-user dedup: drop the global file_hash unique, add composite (user_id, file_hash).
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_file_hash_key")
    op.create_unique_constraint("uq_documents_user_file", "documents", ["user_id", "file_hash"])

    # conversation_history.user_id
    op.add_column("conversation_history", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_conversation_history_user_id", "conversation_history", ["user_id"])
    op.create_foreign_key(
        "fk_conversation_history_user_id", "conversation_history", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversation_history_user_id", "conversation_history", type_="foreignkey")
    op.drop_index("ix_conversation_history_user_id", table_name="conversation_history")
    op.drop_column("conversation_history", "user_id")

    op.drop_constraint("uq_documents_user_file", "documents", type_="unique")
    op.create_unique_constraint("documents_file_hash_key", "documents", ["file_hash"])
    op.drop_constraint("fk_documents_user_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_column("documents", "user_id")
