from __future__ import annotations

from sqlalchemy import Column, DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(schema="map")


class Borger(Base):
    __tablename__ = "Borger"

    cpr = Column(String(32), primary_key=True)
    load_time = Column(DateTime)
