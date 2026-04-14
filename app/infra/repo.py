"""Repository — the only place that touches the DB for group aggregates."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.group import Employer, Payer, PlanVisibility, Subgroup


class GroupRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ---- Payer
    async def insert_payer(self, p: Payer) -> None:
        await self.s.execute(
            text("INSERT INTO payers (id, name) VALUES (:id, :n)"),
            {"id": str(p.id), "n": p.name},
        )

    async def get_payer(self, payer_id: UUID) -> Payer | None:
        r = (
            await self.s.execute(
                text("SELECT id, name FROM payers WHERE id = :id"),
                {"id": str(payer_id)},
            )
        ).first()
        return Payer(id=r.id, name=r.name) if r else None

    # ---- Employer
    async def upsert_employer(self, e: Employer) -> None:
        await self.s.execute(
            text(
                """
                INSERT INTO employers (id, payer_id, name, external_id)
                VALUES (:id, :p, :n, :x)
                ON CONFLICT (external_id) DO UPDATE SET
                  payer_id = EXCLUDED.payer_id,
                  name = EXCLUDED.name
                """
            ),
            {"id": str(e.id), "p": str(e.payer_id), "n": e.name, "x": e.external_id},
        )

    async def get_employer(self, employer_id: UUID) -> Employer | None:
        r = (
            await self.s.execute(
                text("SELECT id, payer_id, name, external_id FROM employers WHERE id = :id"),
                {"id": str(employer_id)},
            )
        ).first()
        return (
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            if r
            else None
        )

    async def find_employers_by_name(self, name: str) -> list[Employer]:
        rows = (
            await self.s.execute(
                text(
                    """
                    SELECT id, payer_id, name, external_id
                    FROM employers
                    WHERE name ILIKE :n OR external_id ILIKE :n
                    ORDER BY name ASC
                    """
                ),
                {"n": f"%{name}%"},
            )
        ).all()
        return [
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            for r in rows
        ]

    async def find_employer_by_external_id(self, external_id: str) -> Employer | None:
        """Match either exact, substring, or 834-sponsor-ref style (e.g. `ICICI_SWIGGY_POLICY`)."""
        r = (
            await self.s.execute(
                text(
                    """
                    SELECT id, payer_id, name, external_id
                    FROM employers
                    WHERE external_id = :x
                       OR external_id ILIKE :like
                       OR :x ILIKE '%' || external_id || '%'
                       OR :x ILIKE '%' || name || '%'
                    ORDER BY (external_id = :x) DESC
                    LIMIT 1
                    """
                ),
                {"x": external_id, "like": f"%{external_id}%"},
            )
        ).first()
        return (
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            if r
            else None
        )

    # ---- Subgroup
    async def insert_subgroup(self, sg: Subgroup) -> None:
        await self.s.execute(
            text(
                "INSERT INTO subgroups (id, employer_id, name) VALUES (:id, :e, :n)"
            ),
            {"id": str(sg.id), "e": str(sg.employer_id), "n": sg.name},
        )

    async def list_subgroups(self, employer_id: UUID) -> list[Subgroup]:
        rows = (
            await self.s.execute(
                text(
                    "SELECT id, employer_id, name FROM subgroups WHERE employer_id = :e"
                ),
                {"e": str(employer_id)},
            )
        ).all()
        return [Subgroup(id=r.id, employer_id=r.employer_id, name=r.name) for r in rows]

    # ---- Visibility
    async def add_visibility(self, v: PlanVisibility) -> bool:
        res = await self.s.execute(
            text(
                """
                INSERT INTO employer_plan_visibility (employer_id, plan_id)
                VALUES (:e, :p)
                ON CONFLICT DO NOTHING
                """
            ),
            {"e": str(v.employer_id), "p": str(v.plan_id)},
        )
        return (res.rowcount or 0) > 0

    async def remove_visibility(self, v: PlanVisibility) -> bool:
        res = await self.s.execute(
            text(
                """
                DELETE FROM employer_plan_visibility
                WHERE employer_id = :e AND plan_id = :p
                """
            ),
            {"e": str(v.employer_id), "p": str(v.plan_id)},
        )
        return (res.rowcount or 0) > 0

    async def list_plans_for_employer(self, employer_id: UUID) -> list[UUID]:
        rows = (
            await self.s.execute(
                text(
                    "SELECT plan_id FROM employer_plan_visibility WHERE employer_id = :e"
                ),
                {"e": str(employer_id)},
            )
        ).all()
        return [r.plan_id for r in rows]
