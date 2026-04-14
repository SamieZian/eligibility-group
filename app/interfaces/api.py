from __future__ import annotations

from typing import Literal
from uuid import UUID

from eligibility_common.db import session_scope
from eligibility_common.errors import Codes, NotFoundError
from eligibility_common.settings import CommonSettings
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.application.commands import change_visibility, upsert_employer
from app.domain.group import (
    Employer,
    Payer,
    PlanVisibility,
    Subgroup,
    new_id,
)
from app.infra.repo import GroupRepo

router = APIRouter(prefix="", tags=["group"])
_settings = CommonSettings()


def _tenant() -> str:
    return _settings.tenant_default


# ---------- Payer CRUD ----------
class PayerIn(BaseModel):
    name: str


class PayerOut(BaseModel):
    id: UUID
    name: str


@router.post("/payers", response_model=PayerOut, status_code=201)
async def post_payer(body: PayerIn) -> PayerOut:
    async with session_scope(tenant_id=_tenant()) as s:
        repo = GroupRepo(s)
        p = Payer(id=new_id(), name=body.name)
        await repo.insert_payer(p)
        return PayerOut(id=p.id, name=p.name)


@router.get("/payers/{payer_id}", response_model=PayerOut)
async def get_payer(payer_id: UUID) -> PayerOut:
    async with session_scope() as s:
        repo = GroupRepo(s)
        p = await repo.get_payer(payer_id)
        if p is None:
            raise NotFoundError(Codes.MEMBER_NOT_FOUND, f"Payer {payer_id} not found")
        return PayerOut(id=p.id, name=p.name)


# ---------- Employer CRUD ----------
class EmployerIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    payer_id: UUID
    name: str
    external_id: str | None = None


class EmployerOut(BaseModel):
    id: UUID
    payer_id: UUID
    name: str
    external_id: str | None


@router.post("/employers", response_model=EmployerOut, status_code=200)
async def post_employer(body: EmployerIn) -> EmployerOut:
    async with session_scope(tenant_id=_tenant()) as s:
        repo = GroupRepo(s)
        e = Employer(
            id=new_id(), payer_id=body.payer_id, name=body.name, external_id=body.external_id
        )
        e = await upsert_employer(s, repo, e, tenant_id=_tenant())
        return EmployerOut(id=e.id, payer_id=e.payer_id, name=e.name, external_id=e.external_id)


@router.get("/employers/{employer_id}", response_model=EmployerOut)
async def get_employer(employer_id: UUID) -> EmployerOut:
    async with session_scope() as s:
        repo = GroupRepo(s)
        e = await repo.get_employer(employer_id)
        if e is None:
            raise NotFoundError(Codes.MEMBER_NOT_FOUND, f"Employer {employer_id} not found")
        return EmployerOut(id=e.id, payer_id=e.payer_id, name=e.name, external_id=e.external_id)


@router.get("/employers", response_model=list[EmployerOut])
async def find_employers(
    name: str | None = Query(None),
    external_id: str | None = Query(None),
) -> list[EmployerOut]:
    async with session_scope() as s:
        repo = GroupRepo(s)
        if external_id:
            e = await repo.find_employer_by_external_id(external_id)
            return (
                [EmployerOut(id=e.id, payer_id=e.payer_id, name=e.name, external_id=e.external_id)]
                if e
                else []
            )
        if not name:
            return []
        matches = await repo.find_employers_by_name(name)
        return [
            EmployerOut(id=e.id, payer_id=e.payer_id, name=e.name, external_id=e.external_id)
            for e in matches
        ]


# ---------- Subgroup CRUD ----------
class SubgroupIn(BaseModel):
    employer_id: UUID
    name: str


class SubgroupOut(BaseModel):
    id: UUID
    employer_id: UUID
    name: str


@router.post("/subgroups", response_model=SubgroupOut, status_code=201)
async def post_subgroup(body: SubgroupIn) -> SubgroupOut:
    async with session_scope(tenant_id=_tenant()) as s:
        repo = GroupRepo(s)
        sg = Subgroup(id=new_id(), employer_id=body.employer_id, name=body.name)
        await repo.insert_subgroup(sg)
        return SubgroupOut(id=sg.id, employer_id=sg.employer_id, name=sg.name)


@router.get("/employers/{employer_id}/subgroups", response_model=list[SubgroupOut])
async def list_subgroups(employer_id: UUID) -> list[SubgroupOut]:
    async with session_scope() as s:
        repo = GroupRepo(s)
        return [
            SubgroupOut(id=sg.id, employer_id=sg.employer_id, name=sg.name)
            for sg in await repo.list_subgroups(employer_id)
        ]


# ---------- Plan visibility ----------
class VisibilityIn(BaseModel):
    employer_id: UUID
    plan_id: UUID
    action: Literal["attach", "detach"] = "attach"


class VisibilityOut(BaseModel):
    employer_id: UUID
    plan_id: UUID
    action: Literal["attach", "detach"]
    changed: bool


@router.post("/visibility", response_model=VisibilityOut, status_code=200)
async def post_visibility(body: VisibilityIn) -> VisibilityOut:
    async with session_scope(tenant_id=_tenant()) as s:
        repo = GroupRepo(s)
        changed = await change_visibility(
            s,
            repo,
            PlanVisibility(employer_id=body.employer_id, plan_id=body.plan_id),
            action=body.action,
            tenant_id=_tenant(),
        )
        return VisibilityOut(
            employer_id=body.employer_id,
            plan_id=body.plan_id,
            action=body.action,
            changed=changed,
        )


class PlansOut(BaseModel):
    employer_id: UUID
    plan_ids: list[UUID]


@router.get("/employers/{employer_id}/plans", response_model=PlansOut)
async def get_employer_plans(employer_id: UUID) -> PlansOut:
    async with session_scope() as s:
        repo = GroupRepo(s)
        plan_ids = await repo.list_plans_for_employer(employer_id)
        return PlansOut(employer_id=employer_id, plan_ids=plan_ids)
