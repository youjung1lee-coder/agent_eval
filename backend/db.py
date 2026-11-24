import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, event, select
from fastapi import HTTPException

url = os.getenv("DATABASE_URL", "sqlite:///gaia.db")
engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def configure(db, _):
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid4().hex


def add(c, t, **values):
    key = values.pop("id", None) or uid()
    c.execute(t.insert().values(id=key, **values))
    return key


def rows(c, t, *filters):
    return [dict(r) for r in c.execute(select(t).where(*filters)).mappings()]


def one(c, t, key):
    row = c.execute(select(t).where(t.c.id == key)).mappings().first()
    if row is None:
        raise HTTPException(404, f"{t.name} 항목을 찾을 수 없습니다")
    return dict(row)
