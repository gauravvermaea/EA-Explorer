"""R5.5.1: architecture decision records and dispensations (owner, 15 Nov 2026, 18:20; agreed 20:31 to 20:34). The
code's own checks; test_r5_5_1_decisions_on_a_real_database.py runs them on PostgreSQL after every migration."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import decisions as dec  # noqa: E402
from eax import governance as gv  # noqa: E402
from eax.metamodel_edit import EditError  # noqa: E402

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]


def test_the_two_kinds_and_their_lifecycles():
    assert gv.KINDS[dec.ADR] == ("ADR", ["Draft", "Proposed", "Accepted", "Superseded", "Deprecated", "Rejected", "Expired"])
    assert gv.KINDS[dec.DISP] == ("DISP", ["Draft", "Proposed", "Accepted", "Expired", "Closed", "Rejected", "Withdrawn"])
    assert gv.PHASES[0] == "Preliminary" and gv.PHASES[-1] == "Requirements Management" and "D" in gv.PHASES


def test_the_templates_as_written():
    t = dec.templates()
    adr = {f["name"]: f["required"] for f in t[dec.ADR]["fields"]}
    disp = {f["name"]: f["required"] for f in t[dec.DISP]["fields"]}
    assert adr == {"context": True, "options": True, "decision": True, "rationale": True, "consequences": True}
    assert disp["waived"] and disp["systems"] and disp["justification"] and disp["risks"] and disp["remediation"]
    assert not disp["impact"] and not disp["mitigations"]
    assert set(t[dec.DISP]["needs"]) >= {"sponsor", "expires_on", "owner"}


def test_required_fields_are_named_when_missing():
    with pytest.raises(EditError) as e:
        dec.check_required(dec.DISP, {"title": "x", "fields": {"waived": "w"}})
    for want in ("Justification", "Risks", "Remediation plan", "its sponsor", "its expiry date"):
        assert want in str(e.value)
    dec.check_required(dec.DISP, {"title": "x", "owner": "o", "sponsor": "s", "expires_on": "2027-01-01",
                                  "fields": {"waived": "w", "systems": "s", "justification": "j", "risks": "r", "remediation": "m"}})


def test_only_a_templates_own_fields_are_kept():
    assert dec.clean_fields(dec.ADR, {"context": " c ", "evil": "x", "decision": ""}) == {"context": "c"}
    assert dec.clean_fields("Risk", {"context": "c"}) == {}
    assert dec.clean_fields(dec.ADR, json.dumps({"options": "o"})) == {"options": "o"}


def test_the_summary_report():
    from datetime import date
    rows = [{"Kind": dec.ADR, "Status": "Accepted", "Project": "P1", "ExpiresOn": None, "EndingSoon": False},
            {"Kind": dec.ADR, "Status": "Draft", "Project": "Organisation", "ExpiresOn": None, "EndingSoon": False},
            {"Kind": dec.DISP, "Status": "Accepted", "Project": "P1", "ExpiresOn": date(2027, 1, 1), "EndingSoon": True},
            {"Kind": dec.DISP, "Status": "Expired", "Project": "P1", "ExpiresOn": date(2026, 1, 1), "EndingSoon": False}]
    s = dec.summary(rows)
    assert s["decisions_by_status"] == {"Accepted": 1, "Draft": 1} and s["ending_soon"] == 1
    assert len(s["active_dispensations"]) == 1 and s["active_dispensations"][0]["ExpiresOn"] == "2027-01-01"


def test_the_architecture_board_role_everywhere():
    from eax import keycloak_upkeep as ku
    from eax import permissions as p
    assert p.ARCHITECTURE_BOARD in p.GLOBAL_ROLES and "governance.board" in p.GLOBAL_PERMISSIONS
    assert ("user_architecture_board", "eax-architecture-board", {}) in p.TEST_USERS
    assert any(r["name"] == "eax-architecture-board" for r in ku.LATER_ROLES)
    assert '"name": "eax-architecture-board"' in (REPO / "deploy/keycloak/realm-eaexplorer.json.tmpl").read_text()
    sql = (API / "migrations/sql/0093_r5_5_1_decisions.sql").read_text()
    assert "('eax-architecture-board', 'architecture-board'" in sql and "'architecture-board', 'Architecture Board', 'global'" in sql
    assert "ku.ensure_roles()" in (API / "eax/jobs.py").read_text()


def test_the_board_is_who_may_accept_outside_projects():
    class U:
        def __init__(self, roles):
            self.roles = roles
    assert dec.is_board(U(["architecture-board"])) and dec.is_board(U(["super-admin"])) and not dec.is_board(U(["user"]))


def test_the_routes_and_the_odata_feed():
    from eax.app import create_app
    rules = {(r.rule, m) for r in create_app(testing=True).url_map.iter_rules() for m in r.methods}
    for want in (("/api/v1/governance", "GET"), ("/api/v1/governance", "POST"), ("/api/v1/governance/<string:rid>", "PUT"),
                 ("/api/v1/governance/<string:rid>/decision", "POST"), ("/api/v1/governance/templates", "GET"),
                 ("/api/v1/governance/ending-soon", "GET"), ("/api/v1/governance/report", "GET"),
                 ("/api/v1/governance/records/<string:rid>/links", "POST"),
                 ("/api/v1/models/<uuid:model_id>/entities/<uuid:entity_id>/decisions", "GET"),
                 ("/api/v1/odata/governance/", "GET"), ("/api/v1/odata/governance/<table>", "GET")):
        assert want in rules, want
    from eax import odata as od
    assert '<EntitySet Name="GovernanceDecisions"' in od.gov_metadata()
    page = od.gov_query([{"Id": "1", "Ref": "ADR-2026-001", "Kind": dec.ADR, "Title": "t", "Status": "Accepted"}],
                        {"$filter": "Status eq 'Accepted'", "$select": "Ref"}, "https://x/api/v1/odata/governance/")
    assert page["value"] == [{"Id": "1", "Ref": "ADR-2026-001"}]


def test_the_hourly_job_warns_expires_and_copies_the_report():
    from eax import jobqueue
    src = (API / "eax/jobs.py").read_text()
    job = src[src.index('name="eax.governance"'):src.index("def keycloak_upkeep")]
    assert 'lock="governance"' in job and "dec.run_ending(conn)" in job and "dec.refresh_report(conn)" in job
    assert "eax.governance" in jobqueue.WORDS


def test_the_screens():
    web = REPO / "services/web/src"
    g = (web / "GovernanceRecords.jsx").read_text(encoding="utf-8")
    for want in ("export function TemplateFields", "export function RecordLinks", "export function EndingSoon",
                 "export default function OrgGovernance", "export function ElementDecisions", "export function GovernanceReport"):
        assert want in g
    assert "<TemplateFields f={f} set={set} can={can} />" in (web / "ProjectGovernance.jsx").read_text(encoding="utf-8")
    assert '["decisions", "Linked decisions and dispensations"]' in (web / "ModelViews.jsx").read_text(encoding="utf-8")
    assert '{ label: "Governance Log", href: "#/governance" }' in (web / "menu.js").read_text(encoding="utf-8")
    assert 'route.startsWith("#/governance") ? <OrgGovernance />' in (web / "App.jsx").read_text(encoding="utf-8")
    help_ = json.loads((web / "help/catalogue.json").read_text(encoding="utf-8"))
    assert "ADR-2026-001" in json.dumps(help_["page:#/governance"])


def test_the_samples_and_the_setting():
    from eax import settings
    assert settings.REGISTRY["gov_dispensation_warn_days"][3] == 30
    s = (API / "eax/seed/sample_content.py").read_text()
    assert "_decisions(conn, karoo, sa, pa, today, gv, pj)" in s and "timedelta(days=12)" in s
    assert '"Requested"' not in s                       # the old dispensation status is gone
