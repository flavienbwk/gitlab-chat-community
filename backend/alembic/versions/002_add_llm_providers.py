"""Add LLM providers table

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # LLM providers table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_providers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            provider_type VARCHAR(50) NOT NULL,
            api_key VARCHAR(500) NOT NULL,
            base_url VARCHAR(500),
            model_id VARCHAR(100) NOT NULL,
            host_country VARCHAR(100),
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """
    )

    # Create index for default provider lookup
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_providers_default ON llm_providers(is_default) WHERE is_default = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_providers")
