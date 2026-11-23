"""What the Release 12 sample projects hold (R12.7; D879: "samples named for their type"), laptop only, with the sample
data. Each sample is made by eax/seed/sample_projects.py as the wizard makes it; here it is filled, once, through the
same functions the screens use (so the samples follow the rules a person would meet):

* every sample: a project plan (RACI per phase or per deliverable, an approval gate where it fits, the phases planned,
  milestones and a status report);
* Agile sprints: requirements, an epic and a feature in its model, the backlog drawn from them, the priority rule and
  Sprint zero planned;
* Risk and security: two risks (Assessments of kind Risk with their likelihood, impact, treatment and residual risk),
  the controls that reduce them and the application they bear on, both logged in the Governance log (the risk register);
* Data governance: a data domain with its steward, the information in it with its system of record, and a quality rule;
* Digital transformation: building blocks chosen for the target;
* EA capability, and Government services (Ridgeview): the plan only (their models start from the templates' structure).

All names are invented. Run after the samples are made; a sample that already holds content is left alone.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

AGILE = "Agile sprints: Fynbos claims app (sample)"
RISK = "Risk and security architecture: Karoo Re (sample)"
DATA = "Data governance: Fynbos master data (sample)"
DIGITAL = "Digital transformation: Fynbos Mutual customer journeys (sample)"
EACAP = "EA capability setup: Protea Insurance (sample)"
RIDGEVIEW = "Government services: Ridgeview City Council (sample)"

# (project, RACI, gates)
PLANS = [(AGILE, "phase", []), (RISK, "phase", ["G"]), (DATA, "deliverable", []), (DIGITAL, "phase", ["B"]),
         (EACAP, "deliverable", ["P"]), (RIDGEVIEW, "phase", [])]


def _ent(core, model: str, actor: str, kind: str, name: str, desc: str = "", **values) -> str:
    from .. import content as ct
    return ct.create_entity(core, model, {"entity_type": kind, "name": name, "description": desc, "values": values}, actor,
                            light=True)["id"]


def _rel(core, model: str, actor: str, src: str, rel: str, tgt: str) -> None:
    from .. import content as ct
    ct.add_relationship(core, model, {"source": src, "target": tgt, "relationship_type": rel}, actor)


def _plan(conn, p: dict, user, raci: str, gates: list[str]) -> None:
    """The project's plan: its settings, its phases over the months ahead, two milestones and a status report."""
    from .. import pm
    pm.set_settings(conn, p["guid"], user, {"raci": raci, "gates": gates})
    start = date.today().replace(day=1)
    phases = [ph["code"] for ph in pm.overview(conn, p["guid"], user)["phases"]]
    for i, code in enumerate(phases[:6]):
        s = start + timedelta(days=28 * i)
        pm.set_phase_plan(conn, p["guid"], user, code, {"starts_on": s.isoformat(), "ends_on": (s + timedelta(days=27)).isoformat()})
    pm.add_milestone(conn, p["guid"], user, {"name": "Architecture vision agreed", "due_on": (start + timedelta(days=27)).isoformat(),
                                             "phase": phases[0] if phases else ""})
    pm.add_milestone(conn, p["guid"], user, {"name": "Target architecture signed off", "due_on": (start + timedelta(days=110)).isoformat()})
    pm.add_status(conn, p["guid"], user, {"rag": "green", "summary": "Started: the stakeholders are agreed and the vision is under way.",
                                          "next_steps": "Close the vision with the sponsor"})


def _agile(conn, core, p: dict, model: str, user, actor: str) -> None:
    from .. import agile as ag
    r1 = _ent(core, model, actor, "Requirement", "Claims lodged online in five minutes", RequirementKind="Functional")
    r2 = _ent(core, model, actor, "Requirement", "Claimant data encrypted at rest", RequirementKind="Security",
              SecurityProperty="Confidentiality")
    epic = _ent(core, model, actor, "WorkPackage", "Online claims", BacklogLevel="Epic")
    feat = _ent(core, model, actor, "WorkPackage", "Photo upload of the damage", BacklogLevel="Feature",
                AcceptanceCriteria="A claimant adds up to ten photos from a phone; each is checked for size and type.")
    _rel(core, model, actor, epic, "Aggregation", feat)
    ag.set_priority_rule(conn, p["guid"], user, "value")
    added = ag.add_to_backlog(conn, p["guid"], user, {"entities": [r1, r2, epic, feat]})["added"]
    ag.add_to_backlog(conn, p["guid"], user, {"title": "Agree the claims capability map", "priority": 5})
    ag.plan(conn, p["guid"], user, {"zero": True, "goal": "Agree the claims app's architecture vision and its first increments",
                                    "phases": ["A", "B"], "accepter": user.username, "items": [a["id"] for a in added[:2]]})


def _risk(conn, core, p: dict, model: str, user, actor: str) -> None:
    from .. import risk_register as rr
    a1 = _ent(core, model, actor, "Assessment", "Treaty data seen by the wrong broker", "Brokers see each other's treaty data in the portal.",
              AssessmentKind="Risk", Likelihood=4, Impact=4, InherentRisk="High", RiskTreatment="Mitigate", ResidualRisk="Medium",
              Owner="Chief Information Security Officer")
    a2 = _ent(core, model, actor, "Assessment", "Underwriters phished", "An underwriter's sign-in is stolen by a fake email.",
              AssessmentKind="Risk", Likelihood=3, Impact=4, InherentRisk="High", RiskTreatment="Mitigate", ResidualRisk="Low",
              Owner="Head of Underwriting")
    c1 = _ent(core, model, actor, "Control", "Broker access reviewed every quarter")
    c2 = _ent(core, model, actor, "Control", "Phishing training and mail filtering")
    app = _ent(core, model, actor, "ApplicationComponent", "Broker portal")
    _rel(core, model, actor, c1, "Influence", a1)
    _rel(core, model, actor, c2, "Influence", a2)
    _rel(core, model, actor, a1, "Association", app)
    for a in (a1, a2):
        rr.log(conn, p["guid"], user, {"model": model, "element": a})


def _data(conn, core, p: dict, model: str, user, actor: str) -> None:
    dom = _ent(core, model, actor, "Grouping", "Customer data domain", DataSteward="Thandi Mokoena")
    bo = _ent(core, model, actor, "BusinessObject", "Customer", DataSteward="Thandi Mokoena", SystemOfRecord="Policy administration system")
    do = _ent(core, model, actor, "DataObject", "Customer record", SystemOfRecord="Policy administration system")
    rule = _ent(core, model, actor, "Requirement", "A customer's email address is valid", RequirementKind="Data quality",
                QualityDimension="Validity", Target="99% of customer records by the end of the year")
    _rel(core, model, actor, dom, "Aggregation", bo)
    _rel(core, model, actor, do, "Realization", bo)
    _rel(core, model, actor, rule, "Association", do)


def _digital(conn, core, p: dict, model: str, user, actor: str) -> None:
    _ent(core, model, actor, "ApplicationComponent", "Customer app", BuildingBlock="Solution building block")
    _ent(core, model, actor, "Service", "Online quote", BuildingBlock="Architecture building block")
    _ent(core, model, actor, "Node", "Cloud platform", BuildingBlock="Solution building block")


FILL = {AGILE: _agile, RISK: _risk, DATA: _data, DIGITAL: _digital}


def run() -> list[str]:
    """Fills the Release 12 samples that are there and empty; returns what it did. Each sample in a transaction of its
    own: one that cannot be filled is left as it was made, and says why."""
    from .. import permissions as perms
    from .. import projects as pj

    admin = perms.Principal("user_super_admin", ("super-admin",))
    maker = perms.Principal("user_project_admin", ("user",))
    token = perms.current.set(admin)
    said: list[str] = []
    try:
        for name, raci, gates in PLANS:
            try:
                with pj.connections() as conn:
                    row = conn.execute(text("SELECT guid::text AS guid, home_model::text AS home FROM proj.projects WHERE name = :n"),
                                       {"n": name}).mappings().first()
                    if not row:
                        continue
                    p = pj.project_row(conn, row["guid"])
                    if conn.execute(text("SELECT 1 FROM proj.milestones WHERE project_id = :p"), {"p": p["id"]}).first():
                        continue                     # filled already
                    _plan(conn, p, maker, raci, gates)
                    if name in FILL and row["home"]:
                        FILL[name](conn, pj.core(conn), p, row["home"], maker, admin.username)
                    said.append(f"{name}: filled")
            except Exception as exc:  # noqa: BLE001 - that sample's transaction is undone; the others go on
                said.append(f"{name}: not filled ({exc})")
    finally:
        perms.current.reset(token)
    return said
