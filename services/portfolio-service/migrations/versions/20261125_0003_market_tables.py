"""4.4: newest scan per asset and the virtual trades

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_scans",
        sa.Column("asset", sa.String(20), primary_key=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "virtual_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("stop", sa.Float(), nullable=False),
        sa.Column("target", sa.Float(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(8), nullable=True),
        sa.Column("result_r", sa.Float(), nullable=True),
    )
    op.create_index("ix_virtual_trades_asset_opened", "virtual_trades", ["asset", "opened_at"])


def downgrade() -> None:
    op.drop_index("ix_virtual_trades_asset_opened", table_name="virtual_trades")
    op.drop_table("virtual_trades")
    op.drop_table("market_scans")
