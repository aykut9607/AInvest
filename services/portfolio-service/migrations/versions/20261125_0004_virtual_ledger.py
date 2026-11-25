"""4.4: paper account, size and state of every virtual trade, append-only events

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIME = sa.DateTime(timezone=True)


def _trades(exit_reason: int, ledger: bool) -> None:
    columns = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("opened_at", TIME, nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("stop", sa.Float(), nullable=False),
        sa.Column("target", sa.Float(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("closed_at", TIME, nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(exit_reason), nullable=True),
        sa.Column("result_r", sa.Float(), nullable=True),
    ]
    if ledger:
        columns += [
            sa.Column("account_id", sa.String(36), sa.ForeignKey("virtual_accounts.id"), nullable=False),
            sa.Column("leverage", sa.Integer(), nullable=False),
            *(sa.Column(n, sa.Float(), nullable=False) for n in ("margin_usd", "notional_usd", "balance_before")),
            sa.Column("balance_after", sa.Float(), nullable=True),
            *(sa.Column(n, sa.Float(), nullable=False) for n in ("pnl_usd", "net_percent", "stop_now", "units_left", "best_price", "worst_price", "last_price")),
            sa.Column("followed_until", TIME, nullable=False),
        ]
    op.create_table("virtual_trades", *columns)
    op.create_index("ix_virtual_trades_asset_opened", "virtual_trades", ["asset", "opened_at"])


def _drop_trades() -> None:
    # a trade of the other format has no account and no size, so it cannot be carried over: the table must be empty
    if not context.is_offline_mode() and op.get_bind().execute(sa.text("SELECT count(*) FROM virtual_trades")).scalar():
        raise RuntimeError("virtual_trades is not empty: these trades belong to the other rules, move them away first.")
    op.drop_index("ix_virtual_trades_asset_opened", table_name="virtual_trades")
    op.drop_table("virtual_trades")


def upgrade() -> None:
    _drop_trades()
    op.create_table(
        "virtual_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("iq_score", sa.Integer(), nullable=False),
        sa.Column("start_balance", sa.Float(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("created_at", TIME, server_default=sa.func.now(), nullable=False),
    )
    _trades(24, True)
    op.create_table(
        "virtual_trade_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trade_id", sa.String(36), sa.ForeignKey("virtual_trades.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("at", TIME, nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        *(sa.Column(n, sa.Float(), nullable=False) for n in ("price", "units", "units_left", "pnl_usd", "balance_after")),
    )
    op.create_index("ix_virtual_trade_events_trade", "virtual_trade_events", ["trade_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_virtual_trade_events_trade", table_name="virtual_trade_events")
    op.drop_table("virtual_trade_events")
    _drop_trades()
    op.drop_table("virtual_accounts")
    _trades(8, False)
