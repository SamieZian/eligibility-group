"""Use-cases for the group service."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from eligibility_common.events import Topics
from eligibility_common.outbox import emit
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.group import Employer, PlanVisibility
from app.infra.repo import GroupRepo


async def upsert_employer(
    s: AsyncSession, repo: GroupRepo, e: Employer, tenant_id: str
) -> Employer:
    await repo.upsert_employer(e)
    await emit(
        s,
        aggregate="employer",
        aggregate_id=e.id,
        event_type="EmployerUpserted",
        payload={
            "employer_id": str(e.id),
            "payer_id": str(e.payer_id),
            "name": e.name,
            "external_id": e.external_id,
        },
        headers={"topic": Topics.GROUP, "tenant_id": tenant_id},
    )
    return e


async def change_visibility(
    s: AsyncSession,
    repo: GroupRepo,
    v: PlanVisibility,
    *,
    action: Literal["attach", "detach"],
    tenant_id: str,
) -> bool:
    if action == "attach":
        changed = await repo.add_visibility(v)
    else:
        changed = await repo.remove_visibility(v)
    await emit(
        s,
        aggregate="employer_plan_visibility",
        aggregate_id=v.employer_id,
        event_type="PlanVisibilityChanged",
        payload={
            "employer_id": str(v.employer_id),
            "plan_id": str(v.plan_id),
            "action": action,
            "changed": changed,
        },
        headers={"topic": Topics.GROUP, "tenant_id": tenant_id},
    )
    return changed
