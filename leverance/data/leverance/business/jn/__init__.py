from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text
from sqlalchemy.orm import DeclarativeBase

metadata = MetaData(schema="jn")


class Base(DeclarativeBase):
    metadata = metadata


class Prompts(Base):
    __tablename__ = "prompts"

    prompt_id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(255))
    prompt = Column(Text)
    ordning = Column(String(255))
    er_evaluering = Column(Integer)
    api_version = Column(String(255))
    sekvens_nr = Column(String(50))
    load_time = Column(DateTime)


class Config(Base):
    __tablename__ = "config"

    kr_initialer = Column(String(50), primary_key=True)
    miljoe = Column(String(50))
    streamer_version = Column(String(255))
    transcriber_version = Column(String(255))
    chatgpt_version = Column(String(255))
    controller_version = Column(String(255))
    forretningsomraade = Column(String(255))
    load_time = Column(DateTime)


t_notat = Table(
    "notat",
    metadata,
    Column("call_id", String(255), primary_key=True),
    Column("genererings_prompt_id", Integer),
    Column("validerings_prompt_id", Integer),
    Column("queue", String(255)),
    Column("kr_initialer", String(50)),
    Column("forretningsomraade", String(255)),
    Column("notat", Text),
    Column("load_time", DateTime),
)


t_samtale = Table(
    "samtale",
    metadata,
    Column("call_id", String(255), primary_key=True),
    Column("queue", String(255)),
    Column("kr_initialer", String(50)),
    Column("tekststykke", Text),
    Column("rolle", String(50), primary_key=True),
    Column("sekvens_nr", Integer, primary_key=True),
    Column("load_time", DateTime),
)


t_notat_feedback = Table(
    "notat_feedback",
    metadata,
    Column("call_id", String(255), primary_key=True),
    Column("agent_id", String(50), primary_key=True),
    Column("feedback", Text),
    Column("rating", Integer),
    Column("benyttet", String(50)),
    Column("load_time", DateTime),
)

__all__ = [
    "Config",
    "Prompts",
    "t_notat",
    "t_notat_feedback",
    "t_samtale",
]
