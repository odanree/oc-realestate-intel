"""SQLAlchemy models for the cached parcel + sales tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Parcel(Base):
    __tablename__ = "parcels"

    apn: Mapped[str] = mapped_column(String(32), primary_key=True)
    address: Mapped[str] = mapped_column(String(255), index=True)
    city: Mapped[str] = mapped_column(String(64), index=True)
    zip: Mapped[str] = mapped_column(String(10), index=True)
    owner: Mapped[str | None] = mapped_column(String(255), index=True)
    owner_kind: Mapped[str | None] = mapped_column(String(32))  # person | trust | llc | other
    use_code: Mapped[str | None] = mapped_column(String(16))
    legal_description: Mapped[str | None] = mapped_column(Text)
    last_sale_date: Mapped[datetime | None] = mapped_column(DateTime)
    last_sale_price: Mapped[float | None] = mapped_column(Float)
    assessed_value: Mapped[float | None] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)


class TitleTransfer(Base):
    __tablename__ = "title_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    apn: Mapped[str] = mapped_column(String(32), index=True)
    transfer_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    doc_number: Mapped[str] = mapped_column(String(64))
    grantor: Mapped[str] = mapped_column(String(255))
    grantee: Mapped[str] = mapped_column(String(255))
    price: Mapped[float | None] = mapped_column(Float)
