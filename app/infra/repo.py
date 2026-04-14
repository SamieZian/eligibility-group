"""Repository — the only place that touches the DB for group aggregates."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.group import Employer, Payer, PlanVisibility, Subgroup
from app.infra.models import Employer as EmployerORM
from app.infra.models import EmployerPlanVisibility as EmployerPlanVisibilityORM
from app.infra.models import Payer as PayerORM
from app.infra.models import Subgroup as SubgroupORM


class GroupRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ---- Payer
    async def insert_payer(self, p: Payer) -> None:
        self.s.add(PayerORM(id=p.id, name=p.name))
        await self.s.flush()

    async def list_payers(self) -> list[Payer]:
        stmt = select(PayerORM).order_by(PayerORM.name)
        rows = (await self.s.execute(stmt)).scalars().all()
        return [Payer(id=r.id, name=r.name) for r in rows]

    async def list_employers(self) -> list[Employer]:
        stmt = select(EmployerORM).order_by(EmployerORM.name)
        rows = (await self.s.execute(stmt)).scalars().all()
        return [
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            for r in rows
        ]

    async def delete_subgroup(self, subgroup_id: UUID) -> bool:
        stmt = delete(SubgroupORM).where(SubgroupORM.id == subgroup_id)
        res = await self.s.execute(stmt)
        return (res.rowcount or 0) > 0

    async def delete_employer(self, employer_id: UUID) -> bool:
        # caller is responsible for cascading subgroups/visibility first
        stmt = delete(EmployerORM).where(EmployerORM.id == employer_id)
        res = await self.s.execute(stmt)
        return (res.rowcount or 0) > 0

    async def get_payer(self, payer_id: UUID) -> Payer | None:
        stmt = select(PayerORM).where(PayerORM.id == payer_id)
        r = (await self.s.execute(stmt)).scalar_one_or_none()
        return Payer(id=r.id, name=r.name) if r else None

    # ---- Employer
    async def upsert_employer(self, e: Employer) -> None:
        stmt = pg_insert(EmployerORM).values(
            id=e.id,
            payer_id=e.payer_id,
            name=e.name,
            external_id=e.external_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[EmployerORM.external_id],
            set_={
                "payer_id": stmt.excluded.payer_id,
                "name": stmt.excluded.name,
            },
        )
        await self.s.execute(stmt)

    async def get_employer(self, employer_id: UUID) -> Employer | None:
        stmt = select(EmployerORM).where(EmployerORM.id == employer_id)
        r = (await self.s.execute(stmt)).scalar_one_or_none()
        return (
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            if r
            else None
        )

    async def find_employers_by_name(self, name: str) -> list[Employer]:
        like = f"%{name}%"
        stmt = (
            select(EmployerORM)
            .where(
                or_(
                    EmployerORM.name.ilike(like),
                    EmployerORM.external_id.ilike(like),
                )
            )
            .order_by(EmployerORM.name.asc())
        )
        rows = (await self.s.execute(stmt)).scalars().all()
        return [
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            for r in rows
        ]

    async def find_employer_by_external_id(self, external_id: str) -> Employer | None:
        """Match either exact, substring, or 834-sponsor-ref style (e.g. `ICICI_SWIGGY_POLICY`)."""
        like = f"%{external_id}%"
        # The previous query also matched when the target string contained the
        # stored external_id / name as a substring (``:x ILIKE '%' || col || '%'``).
        # Express that predicate via ``func``-style string concatenation.
        from sqlalchemy import func, literal

        target = literal(external_id)
        stmt = (
            select(EmployerORM)
            .where(
                or_(
                    EmployerORM.external_id == external_id,
                    EmployerORM.external_id.ilike(like),
                    target.ilike(func.concat("%", EmployerORM.external_id, "%")),
                    target.ilike(func.concat("%", EmployerORM.name, "%")),
                )
            )
            .order_by((EmployerORM.external_id == external_id).desc())
            .limit(1)
        )
        r = (await self.s.execute(stmt)).scalar_one_or_none()
        return (
            Employer(id=r.id, payer_id=r.payer_id, name=r.name, external_id=r.external_id)
            if r
            else None
        )

    # ---- Subgroup
    async def insert_subgroup(self, sg: Subgroup) -> None:
        self.s.add(SubgroupORM(id=sg.id, employer_id=sg.employer_id, name=sg.name))
        await self.s.flush()

    async def list_subgroups(self, employer_id: UUID) -> list[Subgroup]:
        stmt = select(SubgroupORM).where(SubgroupORM.employer_id == employer_id)
        rows = (await self.s.execute(stmt)).scalars().all()
        return [Subgroup(id=r.id, employer_id=r.employer_id, name=r.name) for r in rows]

    # ---- Visibility
    async def add_visibility(self, v: PlanVisibility) -> bool:
        stmt = pg_insert(EmployerPlanVisibilityORM).values(
            employer_id=v.employer_id,
            plan_id=v.plan_id,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                EmployerPlanVisibilityORM.employer_id,
                EmployerPlanVisibilityORM.plan_id,
            ]
        )
        res = await self.s.execute(stmt)
        return (res.rowcount or 0) > 0

    async def remove_visibility(self, v: PlanVisibility) -> bool:
        stmt = delete(EmployerPlanVisibilityORM).where(
            EmployerPlanVisibilityORM.employer_id == v.employer_id,
            EmployerPlanVisibilityORM.plan_id == v.plan_id,
        )
        res = await self.s.execute(stmt)
        return (res.rowcount or 0) > 0

    async def list_plans_for_employer(self, employer_id: UUID) -> list[UUID]:
        stmt = select(EmployerPlanVisibilityORM.plan_id).where(
            EmployerPlanVisibilityORM.employer_id == employer_id
        )
        rows = (await self.s.execute(stmt)).all()
        return [r.plan_id for r in rows]
