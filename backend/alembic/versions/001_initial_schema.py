"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projects table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            gitlab_id INTEGER UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            path_with_namespace VARCHAR(500) NOT NULL,
            description TEXT,
            default_branch VARCHAR(100) DEFAULT 'main',
            http_url_to_repo VARCHAR(500),
            is_indexed BOOLEAN DEFAULT FALSE,
            is_selected BOOLEAN DEFAULT FALSE,
            last_indexed_at TIMESTAMP WITH TIME ZONE,
            indexing_status VARCHAR(50) DEFAULT 'pending',
            indexing_error TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """
    )

    # Conversations table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(500),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """
    )

    # Messages table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            extra_data JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """
    )

    # Indexed items tracking
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS indexed_items (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            item_type VARCHAR(50) NOT NULL,
            item_id INTEGER NOT NULL,
            item_iid INTEGER,
            qdrant_point_ids TEXT[],
            last_updated_at TIMESTAMP WITH TIME ZONE,
            indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(project_id, item_type, item_id)
        )
    """
    )

    # Create indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_indexed_items_project ON indexed_items(project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_indexed_items_type ON indexed_items(item_type)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_gitlab_id ON projects(gitlab_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_selected ON projects(is_selected) WHERE is_selected = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS indexed_items")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS projects")
