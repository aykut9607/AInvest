"""portfolio preferences and proposals (4.1-4.3)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_preferences",
        sa.Column("user_id", sa.String(100), primary_key=True),
        sa.Column("choice", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "portfolio_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_portfolio_proposals_user_created", "portfolio_proposals", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_proposals_user_created", table_name="portfolio_proposals")
    op.drop_table("portfolio_proposals")
    op.drop_table("portfolio_preferences")
