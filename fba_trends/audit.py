"""Login audit and per-user session epochs in PostgreSQL (DATABASE_URL).

Best effort: if the database is down the dashboard keeps working (login is not blocked),
events are just not recorded and every session epoch reads as 0.
"""
import functools
import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger("weavers.audit")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS auth_events (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        username TEXT NOT NULL,
        event TEXT NOT NULL,
        ip TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS ix_auth_events_at ON auth_events (at DESC)",
    """CREATE TABLE IF NOT EXISTS auth_epochs (
        username TEXT PRIMARY KEY,
        epoch INTEGER NOT NULL DEFAULT 0)""",
]


@functools.lru_cache(maxsize=1)
def _engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2,
                           connect_args={"connect_timeout": 3})  # never hang a login on a dead DB
    with engine.begin() as c:
        for stmt in SCHEMA:
            c.execute(text(stmt))
    return engine


def _run(sql: str, params: dict, fetch: bool = False):
    try:
        engine = _engine()
        if engine is None:
            return None
        with engine.begin() as c:
            res = c.execute(text(sql), params)
            return res.scalar() if fetch else None
    except SQLAlchemyError as e:
        _engine.cache_clear()  # retry the connection next time
        log.warning("audit db unavailable: %s", type(e).__name__)
        return None


def record(username: str, event: str, ip: str = "") -> None:
    _run("INSERT INTO auth_events (username, event, ip) VALUES (:u, :e, :ip)",
         {"u": username[:200], "e": event, "ip": ip[:64]})


def epoch(username: str) -> int:
    return int(_run("SELECT epoch FROM auth_epochs WHERE username = :u", {"u": username}, fetch=True) or 0)


def bump_epoch(username: str) -> None:
    """Invalidate every existing session cookie of this user."""
    _run("""INSERT INTO auth_epochs (username, epoch) VALUES (:u, 1)
            ON CONFLICT (username) DO UPDATE SET epoch = auth_epochs.epoch + 1""", {"u": username})


def recent(limit: int = 50) -> list[dict]:
    try:
        engine = _engine()
        if engine is None:
            return []
        with engine.connect() as c:
            rows = c.execute(text("SELECT at, username, event, ip FROM auth_events ORDER BY at DESC LIMIT :n"),
                             {"n": max(1, min(int(limit), 500))}).mappings()
            return [dict(r) for r in rows]
    except SQLAlchemyError:
        return []
