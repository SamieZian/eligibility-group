from __future__ import annotations

from uuid import uuid4

from app.domain.group import Employer, PlanVisibility, Subgroup, new_id


def test_new_id_produces_unique_uuids() -> None:
    a = new_id()
    b = new_id()
    assert a != b


def test_employer_dataclass_roundtrip() -> None:
    pid = uuid4()
    e = Employer(id=new_id(), payer_id=pid, name="Acme Corp", external_id="ACME-1")
    assert e.payer_id == pid
    assert e.name == "Acme Corp"
    assert e.external_id == "ACME-1"


def test_plan_visibility_equality_by_keys() -> None:
    eid, pid = uuid4(), uuid4()
    v1 = PlanVisibility(employer_id=eid, plan_id=pid)
    v2 = PlanVisibility(employer_id=eid, plan_id=pid)
    assert v1 == v2


def test_subgroup_links_employer() -> None:
    eid = uuid4()
    sg = Subgroup(id=new_id(), employer_id=eid, name="East")
    assert sg.employer_id == eid
