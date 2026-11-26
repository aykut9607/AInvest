from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class PortfolioPreference(Base):
    __tablename__ = "portfolio_preferences"

    user_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    choice: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PortfolioProposal(Base):
    """Append-only: a new proposal never changes an older one."""

    __tablename__ = "portfolio_proposals"
    __table_args__ = (Index("ix_portfolio_proposals_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)


class MarketScan(Base):
    """The newest scan of each asset (4.4): replaced at every 15m close."""

    __tablename__ = "market_scans"

    asset: Mapped[str] = mapped_column(String(20), primary_key=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)


class VirtualAccount(Base):
    """Paper money the virtual trades are paid from; every new trade is sized from the balance of that moment (compounding)."""

    __tablename__ = "virtual_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    iq_score: Mapped[int] = mapped_column(Integer)
    start_balance: Mapped[float] = mapped_column(Float)
    balance: Mapped[float] = mapped_column(Float)          # realised: the open part of a position is not in it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VirtualTrade(Base):
    """A plan of the 4.4 engine followed on paper. No order is ever sent anywhere."""

    __tablename__ = "virtual_trades"
    __table_args__ = (Index("ix_virtual_trades_asset_opened", "asset", "opened_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(5))
    kind: Mapped[str] = mapped_column(String(12))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    target: Mapped[float] = mapped_column(Float)              # the last one; all of them are in plan.steps
    plan: Mapped[dict] = mapped_column(JSON)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(24), nullable=True)          # kind of the last event
    result_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("virtual_accounts.id"))
    leverage: Mapped[int] = mapped_column(Integer)
    margin_usd: Mapped[float] = mapped_column(Float)
    notional_usd: Mapped[float] = mapped_column(Float)
    balance_before: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_usd: Mapped[float] = mapped_column(Float)              # realised so far, fees included
    net_percent: Mapped[float] = mapped_column(Float)          # the same in % of the position
    stop_now: Mapped[float] = mapped_column(Float)
    units_left: Mapped[float] = mapped_column(Float)
    best_price: Mapped[float] = mapped_column(Float)
    worst_price: Mapped[float] = mapped_column(Float)
    last_price: Mapped[float] = mapped_column(Float)
    followed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VirtualMissedTrade(Base):
    """Every condition was met while the engine was not running: noted afterwards, never opened, never paid from the account. It is still
    followed, so the note also says what would have happened."""

    __tablename__ = "virtual_missed_trades"
    __table_args__ = (Index("ix_virtual_missed_trades_asset_at", "asset", "at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(5))
    kind: Mapped[str] = mapped_column(String(12))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    noted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(16))          # ENGINE_OFF
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    plan: Mapped[dict] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON)                # the position as it would stand
    followed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(24), nullable=True)
    result_r: Mapped[float | None] = mapped_column(Float, nullable=True)


class VirtualTradeEvent(Base):
    """Append-only: the opening, every partial close and the end of a virtual trade."""

    __tablename__ = "virtual_trade_events"
    __table_args__ = (Index("ix_virtual_trade_events_trade", "trade_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trade_id: Mapped[str] = mapped_column(String(36), ForeignKey("virtual_trades.id"))
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(24))          # OPEN, HALF..., SCALP_TP, TP1 ... MARKET_SELL, TREND_..., STOP, ENTRY_STOP
    price: Mapped[float] = mapped_column(Float)
    units: Mapped[float] = mapped_column(Float)            # of the 100 units of the position
    units_left: Mapped[float] = mapped_column(Float)
    pnl_usd: Mapped[float] = mapped_column(Float)          # after the fee
    balance_after: Mapped[float] = mapped_column(Float)
