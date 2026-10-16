"""PostgreSQL-backed append-only market research snapshots (opt-in).

Creates only the tables owned by this module; no destructive migrations.
Use SQLAlchemy's pooled engine and parameterized SQL.
"""
import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id TEXT NOT NULL,
    actor_email TEXT NOT NULL,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_snapshots_org_time
ON market_snapshots (organization_id, collected_at DESC);
"""


class SnapshotStore:
    def __init__(self, database_url=None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL no está configurado")
        self.engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)

    def initialize(self):
        with self.engine.begin() as connection:
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    connection.execute(text(statement))

    def save(self, *, organization_id, actor_email, source, query, payload):
        if not all((organization_id, actor_email, source, query)):
            raise ValueError("Faltan campos de auditoría")
        with self.engine.begin() as connection:
            return connection.execute(
                text("""INSERT INTO market_snapshots
                    (organization_id, actor_email, source, query, payload)
                    VALUES (:org, :actor, :source, :query, CAST(:payload AS JSONB))
                    RETURNING id"""),
                {"org":organization_id, "actor":actor_email, "source":source,
                 "query":query, "payload":json.dumps(payload)},
            ).scalar_one()

    def recent(self, organization_id, limit=25):
        if not organization_id:
            raise ValueError("organization_id requerido")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text("""SELECT id, actor_email, source, query, collected_at
                    FROM market_snapshots WHERE organization_id = :org
                    ORDER BY collected_at DESC LIMIT :limit"""),
                {"org":organization_id, "limit":max(1, min(int(limit), 100))},
            ).mappings()
            return [dict(r) for r in rows]
