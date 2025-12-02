"""Add fields for incremental indexing.

Revision ID: 003
Revises: 002
Create Date: 2025-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add last_indexed_commit column to projects for tracking code changes
    op.add_column(
        "projects",
        sa.Column("last_indexed_commit", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "last_indexed_commit")
