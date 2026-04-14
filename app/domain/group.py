"""Pure-domain aggregates for the group service: payers, employers, subgroups,
plan visibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Payer:
    id: UUID
    name: str


@dataclass
class Employer:
    id: UUID
    payer_id: UUID
    name: str
    external_id: str | None = None


@dataclass
class Subgroup:
    id: UUID
    employer_id: UUID
    name: str


@dataclass
class PlanVisibility:
    employer_id: UUID
    plan_id: UUID


def new_id() -> UUID:
    return uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
