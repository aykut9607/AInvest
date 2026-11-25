from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, String, func
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
    target: Mapped[float] = mapped_column(Float)
    plan: Mapped[dict] = mapped_column(JSON)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)          # TARGET / STOP / EXPIRED
    result_r: Mapped[float | None] = mapped_column(Float, nullable=True)
