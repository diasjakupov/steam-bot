from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appid: Mapped[int]
    market_hash_name: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    currency_id: Mapped[int] = mapped_column(Integer, default=1)
    rules: Mapped[Dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    snapshots: Mapped[list["ListingSnapshot"]] = relationship(back_populates="watchlist", cascade="all, delete-orphan")


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlist.id", ondelete="CASCADE"))
    listing_key: Mapped[Optional[str]] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    parsed: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    inspected: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)

    watchlist: Mapped[Watchlist] = relationship(back_populates="snapshots")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("listing_snapshot.id", ondelete="CASCADE"))
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    snapshot: Mapped[ListingSnapshot] = relationship(back_populates="alerts")


class InspectHistory(Base):
    __tablename__ = "inspect_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inspect_url: Mapped[str] = mapped_column(Text, unique=True)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON)
    last_inspected: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    watchlist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("watchlist.id", ondelete="CASCADE"), nullable=True)

    watchlist: Mapped[Optional[Watchlist]] = relationship()


class WorkerSettings(Base):
    __tablename__ = "worker_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
