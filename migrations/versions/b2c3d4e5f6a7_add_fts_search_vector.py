"""add FTS search_vector column to chunks

Revision ID: b2c3d4e5f6a7
Revises: 1b1de1ba0245
Create Date: 2026-05-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "1b1de1ba0245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tsvector column
    op.add_column("chunks", sa.Column("search_vector", TSVECTOR, nullable=True))

    # Backfill existing rows
    op.execute("UPDATE chunks SET search_vector = to_tsvector('english', text)")

    # GIN index for fast FTS queries
    op.execute("CREATE INDEX chunks_search_vector_idx ON chunks USING GIN(search_vector)")

    # Trigger function — auto-populate search_vector on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION chunks_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector = to_tsvector('english', NEW.text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER chunks_search_vector_trigger
        BEFORE INSERT OR UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS chunks_search_vector_trigger ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_search_vector_update")
    op.execute("DROP INDEX IF EXISTS chunks_search_vector_idx")
    op.drop_column("chunks", "search_vector")
