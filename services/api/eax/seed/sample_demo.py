"""The demo project (owner, 17 Nov 2026, 15:18: "Make one Mega Project with 2-3 mega models you can use any existing one,
it should be pinned but all the data every kind should be in it so that when i demo I have eveything in one model";
answers: grow Protea Claims Transformation 2028, and "create a new user called demo-super-admin we will use this user
for all demos"; D734). Laptop only, the last sample step, made once part by part.

The demo project is **Protea Claims Transformation 2028 (sample)**, with its three models: Protea Insurance (demo
estate) (current: drawn views, KPI trends, tags, gap analyses, duplicates, deliveries, an MCP clean-up copy, discovery),
Protea claims target 2028 and Protea claims transition 2027 (a merge request withdrawn), and the Insurance reference
model it refers to. The other samples already give it: Business Model Canvases of every kind, customer journeys today
and 2028, key questions in every state, drawn views as evidence, uploads, an ADM iteration history and a project
library. This step adds what only other sample projects had, so one project shows every kind:

* the governance log with a record of every kind in every approval state, the charter approved, the project's people,
  its calendar, phases and steps done, a deliverable placed in the content framework and two tracking sheets
* an architecture decision record and a dispensation linked to the demo estate's elements
* stakeholders with discussions, standards, tasks in each status, a document sent for sign-off
* a scenario made from the target, with a what-if, and a scenario assessment
* demo-super-admin on the project, with the project and its models pinned (Recent and pinned)

Every name is invented. A part already there is left alone; a part that cannot be made (Documents not up yet, a phase
frozen by the project's iteration) is said and the rest goes on.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

PROJECT = "Protea Claims Transformation 2028 (sample)"
DEMO_USER = "demo-super-admin"
MODELS = ["Protea Insurance (demo estate)", "Protea claims target 2028", "Protea claims transition 2027", "Insurance reference model"]
SCENARIO = "Protea claims: partner-led (scenario)"
MARK = "Demo project: every kind of content"


def _p(name, roles=("user",)):
    from .. import permissions as perms
    return perms.Principal(name, tuple(roles))


def run() -> list[str]:
    """Fills the demo project with every kind of content it lacks, and pins it for demo-super-admin."""
    from .. import notify
    from .. import permissions as perms
    from .. import projects as pj
    said: list[str] = []
    sa = _p("user_super_admin", ("super-admin",))
    real_notify = notify.create
    notify.create = lambda *a, **k: None          # no notifications for seed data
    token = perms.current.set(sa)
    try:
        with pj.connections(True) as conn:
            pg = conn.execute(text("SELECT guid::text FROM proj.projects WHERE name = :n"), {"n": PROJECT}).scalar()
        if not pg:
            return [f"demo project skipped: {PROJECT} is not there yet"]
        for part in (_mark, _governance, _decisions, _stakeholders, _standards, _tasks, _signoff, _pins):
            try:
                with pj.connections(True) as conn:
                    out = part(conn, pg, sa)
                if out:
                    said.append(out)
            except Exception as exc:  # noqa: BLE001 - one part never stops the others
                said.append(f"demo project: {part.__name__.strip('_')} not made: {str(exc)[:160]}")
        try:
            out = _scenario(pg)
            if out:
                said.append(out)
        except Exception as exc:  # noqa: BLE001
            said.append(f"demo project: scenario not made: {str(exc)[:160]}")
    finally:
        perms.current.reset(token)
        notify.create = real_notify
    return said


def _mark(conn, pg, sa) -> str:
    """The project says it is the demo project, and demo-super-admin is on it as its Project Admin."""
    from .. import projects as pj
    p = pj.project_row(conn, pg)
    if MARK not in (p.get("description") or ""):
        conn.execute(text("UPDATE proj.projects SET description = :d WHERE id = :i"),
                     {"d": f"{MARK} (the one to demo, signed in as {DEMO_USER}). " + (p.get("description") or ""), "i": p["id"]})
    conn.execute(text("""INSERT INTO proj.members (project_id, username, role, added_by) VALUES (:p, :u, 'project-admin', 'user_super_admin')
                         ON CONFLICT DO NOTHING"""), {"p": p["id"], "u": DEMO_USER})
    return ""


def _governance(conn, pg, sa) -> str:
    """Every kind of governance record in every approval state, the charter, people, calendar, steps, sheets (the same
    as the cloud migration sample's, made here too)."""
    from .. import calendars as cl
    from .. import content_framework as cf
    from .. import governance as gv
    from .. import project_org as po
    from .. import projects as pj
    from .. import tracking_sheets as ts
    from . import sample_content as sc
    p = pj.project_row(conn, pg)
    if conn.execute(text("SELECT 1 FROM proj.gov_records WHERE project_id = :p AND kind = 'Risk'"), {"p": p["id"]}).first():
        return ""
    sc._karoo(conn, pg, sa, _p("user_project_admin"), _p("user_lead_architect"), _p("user_model_admin"), _p("user_architect"),
              date.today(), gv, po, cl, cf, ts, pj)
    return f"{PROJECT}: governance of every kind and state, charter, people, calendar, steps, sheets"


def _decisions(conn, pg, sa) -> str:
    """An architecture decision record (accepted) and a dispensation (waiting), linked to the demo estate's elements."""
    from .. import decisions as dec
    from .. import governance as gv
    from .. import projects as pj
    p = pj.project_row(conn, pg)
    if conn.execute(text("SELECT 1 FROM proj.gov_records WHERE project_id = :p AND kind = :k"), {"p": p["id"], "k": dec.ADR}).first():
        return ""
    pa = _p("user_project_admin")
    els = [dict(r) for r in pj.core(conn).execute(text("""SELECT e.guid::text AS id, m.guid::text AS model FROM core.entities e
                                                           JOIN core.models m ON m.id = e.model_id
                                                          WHERE m.name = 'Protea Insurance (demo estate)' AND NOT e.is_deleted
                                                          ORDER BY (e.name ILIKE '%claim%') DESC, e.name LIMIT 3""")).mappings()]
    adr = gv.add(conn, pg, pa, {
        "kind": dec.ADR, "title": "Settle simple motor claims automatically", "status": "Draft", "owner": "Thandi Nkosi",
        "phase": "C", "record_type": "Application", "html": "<p>Demo decision record.</p>",
        "fields": {"context": "Most motor claims are small and simple, yet each waits a week for a handler.",
                   "options": "1. More handlers. 2. Rules that settle simple claims at once. 3. Outsource first notice of loss.",
                   "decision": "Settle claims under the simple-claim rules automatically on the claims hub.",
                   "rationale": "Claimants are paid the same day; handlers keep the complex claims.",
                   "consequences": "Fraud rules must run before payment; the rules are reviewed every quarter."}})["id"]
    gv.approve_with_evidence(conn, pg, pa, adr, "Accepted at the Architecture Board (demo).")
    for e in els[:2]:
        dec.add_link(conn, pa, adr, {"kind": "element", "target": e["id"], "model": e["model"]})
    disp = gv.add(conn, pg, pa, {
        "kind": dec.DISP, "title": "Paper claim forms accepted until the app reaches every region", "status": "Draft",
        "owner": "Claims operations", "sponsor": "Head of Claims", "expires_on": str(date.today() + timedelta(days=90)),
        "fields": {"waived": "Digital channels only", "systems": "Paper claim intake",
                   "justification": "Two regions have poor mobile coverage.",
                   "impact": "A scanning step stays in the claims process.", "risks": "Slower claims in those regions.",
                   "mitigations": "Forms scanned on the day they arrive.", "remediation": "Retire paper with the WhatsApp claims line."}})["id"]
    gv.send_for_approval(conn, pg, pa, disp, "For the next Architecture Board (demo).")
    if els:
        dec.add_link(conn, pa, disp, {"kind": "element", "target": els[-1]["id"], "model": els[-1]["model"]})
    return f"{PROJECT}: a decision record and a dispensation linked to the demo estate"


def _stakeholders(conn, pg, sa) -> str:
    """Stakeholders across the power and interest grid, with a discussion noted."""
    from .. import stakeholders as sh
    have = sh.listing(conn, pg, sa)["stakeholders"]
    if len(have) >= 3:
        return ""
    made = 0
    for d in ({"name": "Head of Claims", "power": "High", "interest": "High", "concerns": "Claim cycle time; handler workload"},
              {"name": "Chief Risk Officer", "power": "High", "interest": "Low", "concerns": "Fraud losses; regulatory reporting"},
              {"name": "Brokers' forum", "power": "Low", "interest": "High", "concerns": "Claim status for their clients"},
              {"name": "Repairer panel", "power": "Low", "interest": "Low", "concerns": "Payment terms"}):
        if any(s["name"] == d["name"] for s in have):
            continue
        out = sh.add(conn, pg, sa, d)
        made += 1
        if d["name"] == "Head of Claims":
            sh.add_note(conn, pg, sa, out["id"], {"title": "Target walkthrough", "html": "<p>Agreed the same-day target for simple claims (demo).</p>"})
    return f"{PROJECT}: {made} stakeholders" if made else ""


def _standards(conn, pg, sa) -> str:
    from .. import standards as st
    if st.listing(conn, pg, sa).get("standards"):
        return ""
    for d in ({"area": "Application", "name": "APIs described in OpenAPI 3", "status": "Active", "source": "Integration guild"},
              {"area": "Security", "name": "Single sign-on for every staff application", "status": "Active", "source": "CISO"},
              {"area": "Data", "name": "Claims data kept in the country", "status": "Trial", "source": "Compliance"}):
        st.add(conn, pg, sa, d)
    return f"{PROJECT}: 3 standards"


def _tasks(conn, pg, sa) -> str:
    from .. import project_tasks as tk
    from .. import projects as pj
    p = pj.project_row(conn, pg)
    if conn.execute(text("SELECT 1 FROM proj.tasks WHERE project_id = :p"), {"p": p["id"]}).first():
        return ""
    statuses = tk.statuses(conn, p)
    for n, (title, who) in enumerate((("Collect the claims volumes per region", "user_architect"),
                                      ("Draft the claims hub's target data flows", "user_lead_architect"),
                                      ("Book the target walkthrough with the Head of Claims", "user_project_admin"),
                                      ("Check the fraud rules with the risk team", ""))):
        tk.add(conn, pg, sa, {"title": title, "assigned_to": who, "status": statuses[min(n, len(statuses) - 1)]})
    return f"{PROJECT}: 4 tasks in each status"


def _signoff(conn, pg, sa) -> str:
    """A deliverable with a file sent for sign-off (when Documents has its files)."""
    from .. import project_work as pw
    from .. import projects as pj
    p = pj.project_row(conn, pg)
    if conn.execute(text("""SELECT 1 FROM proj.signoff_requests r JOIN proj.documents d ON d.id = r.document_id
                             WHERE d.project_id = :p"""), {"p": p["id"]}).first():
        return ""
    for d in conn.execute(text("""SELECT guid::text AS g FROM proj.documents WHERE project_id = :p AND mayan_document_id IS NOT NULL
                                   AND kind IN ('Deliverable', 'Artifact') ORDER BY id"""), {"p": p["id"]}).mappings():
        try:
            pw.raise_signoff(conn, pg, _p("user_lead_architect"), d["g"], "Please sign off (demo).")
            return f"{PROJECT}: a document sent for sign-off"
        except Exception:  # noqa: BLE001 - a phase frozen by the iteration: try the next document
            continue
    return ""


def _pins(conn, pg, sa) -> str:
    """demo-super-admin's Recent and pinned: the demo project and its models."""
    from .. import projects as pj
    from .. import workspace as ws
    core = pj.core(conn)
    ws.set_favourite(conn, DEMO_USER, "project", pg, True, PROJECT)
    n = 1
    for name in MODELS + [SCENARIO]:
        g = core.execute(text("SELECT guid::text FROM core.models WHERE name = :n"), {"n": name}).scalar()
        if g:
            ws.set_favourite(conn, DEMO_USER, "model", g, True, name)
            n += 1
    return f"{DEMO_USER}: the demo project and {n - 1} models pinned"


def _scenario(pg) -> str:
    """A scenario made from the 2028 target, with a what-if, and its assessment against the target."""
    from .. import projects as pj
    from .. import scenarios as sc
    la = _p("user_lead_architect")
    with pj.connections(True) as pc:
        if pc.execute(text("""SELECT 1 FROM proj.scenario_assessments a JOIN proj.projects p ON p.id = a.project_id
                               WHERE p.name = :n"""), {"n": PROJECT}).first():
            return ""
        pj.core(pc).execute(text("SELECT set_config('eax.actor', 'user_lead_architect', true)"))
        if not pj.core(pc).execute(text("SELECT 1 FROM core.models WHERE name = :n"), {"n": SCENARIO}).first():
            sc.make_scenario(pc, pg, la, SCENARIO, "copy", "Protea claims target 2028", confirm=True)
    with pj.connections(True) as pc:
        pj.core(pc).execute(text("SELECT set_config('eax.actor', 'user_lead_architect', true)"))
        try:
            sc.apply_what_ifs(pc, pg, la, SCENARIO, [{"add": "Claims administration partner (outsourced first notice of loss)",
                                                       "type": "ApplicationComponent",
                                                       "description": "A partner takes first notice of loss (demo scenario)."}],
                              confirm=True)
        except Exception:  # noqa: BLE001 - the assessment still shows the scenario
            pass
    with pj.connections(True) as pc:
        pj.core(pc).execute(text("SELECT set_config('eax.actor', 'user_lead_architect', true)"))
        out = sc.record_assessment(
            pc, pg, la, "Claims: in house or partner-led",
            [{"model": "Protea claims target 2028", "score": 7, "notes": "Same-day settlement in house; needs the claims hub team."},
             {"model": SCENARIO, "score": 6, "notes": "Faster to start; a partner holds the first contact with claimants."}],
            recommendation="Keep claims in house (the 2028 target).\n\nThe first contact with a claimant is the moment that matters most.",
            recommended="Protea claims target 2028", governance="draft", via="mcp", confirm=True)
        return f"{PROJECT}: scenario {SCENARIO} and assessment {out.get('ref', '')}"
