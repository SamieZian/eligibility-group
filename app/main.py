from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from eligibility_common.app_factory import create_app
from eligibility_common.db import engine, session_scope
from eligibility_common.idempotency import IDEMPOTENCY_DDL_STATEMENTS
from eligibility_common.outbox import OUTBOX_DDL_STATEMENTS
from fastapi import FastAPI
from sqlalchemy import text

from app.interfaces.api import router
from app.settings import settings


_GROUP_DDL = [
    """
    CREATE TABLE IF NOT EXISTS payers (
      id UUID PRIMARY KEY,
      name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS employers (
      id UUID PRIMARY KEY,
      payer_id UUID NOT NULL REFERENCES payers(id),
      name TEXT NOT NULL,
      external_id TEXT UNIQUE
    )
    """,
    "CREATE INDEX IF NOT EXISTS employers_payer ON employers (payer_id)",
    "CREATE INDEX IF NOT EXISTS employers_name ON employers (name)",
    """
    CREATE TABLE IF NOT EXISTS subgroups (
      id UUID PRIMARY KEY,
      employer_id UUID NOT NULL REFERENCES employers(id),
      name TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS subgroups_employer ON subgroups (employer_id)",
    """
    CREATE TABLE IF NOT EXISTS employer_plan_visibility (
      employer_id UUID NOT NULL,
      plan_id UUID NOT NULL,
      PRIMARY KEY (employer_id, plan_id)
    )
    """,
]


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    async with engine().begin() as conn:
        for stmt in OUTBOX_DDL_STATEMENTS + IDEMPOTENCY_DDL_STATEMENTS + _GROUP_DDL:
            await conn.execute(text(stmt))
    yield


async def _ping_db() -> None:
    async with session_scope() as s:
        await s.execute(text("SELECT 1"))


app = create_app(
    service_name=settings.service_name,
    lifespan=lifespan,
    readiness={"db": _ping_db},
)
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
