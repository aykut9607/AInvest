"""4.4: trades that met every condition while the engine was off (noted, never paid from the account)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIME = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "virtual_missed_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("at", TIME, nullable=False),
        sa.Column("noted_at", TIME, nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("stop", sa.Float(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("followed_until", TIME, nullable=False),
        sa.Column("closed_at", TIME, nullable=True),
        sa.Column("exit_reason", sa.String(24), nullable=True),
        sa.Column("result_r", sa.Float(), nullable=True),
    )
    op.create_index("ix_virtual_missed_trades_asset_at", "virtual_missed_trades", ["asset", "at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_virtual_missed_trades_asset_at", table_name="virtual_missed_trades")
    op.drop_table("virtual_missed_trades")
