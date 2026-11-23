"""Release 12, R12.5 (D879, D887): the risk register is the Governance log's Risk records linked to the risk
Assessments of the project's models: no new type, no new table for risks.

Run on a real PostgreSQL while building (23 Nov 2026): a model with two risk Assessments (one 4x5 High owned by the
CISO and bearing on the customer portal, one 3x4 Low reduced by a control) and a Finding; the register listed the two
risks as not logged (the finding left out), with their scores, residual risk, controls and what they bear on; logging
the first made RSK-001 describing it; logging it again refused; logging the finding refused; an existing record RSK-002
was linked to the second risk; the register then showed both records with their risks, the High one first."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from eax import decisions as dec
from eax import risk_register as rr

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"
SRC = inspect.getsource(rr)


def test_no_new_type_or_table_for_risks():
    assert rr.RISK == "Risk" and rr.DESCRIBES == "describes"
    assert "CREATE TABLE" not in SRC
    assert "t.code = 'Assessment'" in SRC and '(r.get("AssessmentKind") or "") == RISK' in SRC
    assert set(rr.VALUES) >= {"Likelihood", "Impact", "InherentRisk", "RiskTreatment", "ResidualRisk"}


def test_a_record_describes_a_risk_in_a_model():
    assert "describes" in dec.RELATIONS["element"] and "affects" in dec.RELATIONS["element"]
    sql = (ROOT / "migrations" / "sql" / "0119_r12_project_management.sql").read_text(encoding="utf-8")
    assert "'depends-on', 'describes')" in sql and "DROP CONSTRAINT IF EXISTS gov_links_relation_check" in sql


def test_the_register_reads_both_sides():
    reg = inspect.getsource(rr.register)
    assert "assessments(pj.core(pc), _models(pc, p))" in reg and "g.kind = :k" in reg
    assert '"not_logged": loose' in reg
    a = inspect.getsource(rr.assessments)
    assert 'n["type"] == "Control"' in a and '"bears_on"' in a and 'r["score"] = r["Likelihood"] * r["Impact"]' in a
    assert rr.LEVELS == {"High": 3, "Medium": 2, "Low": 1}          # worst residual risk first


def test_logging_and_linking():
    log = inspect.getsource(rr.log)
    assert "is in the Governance log already." in log and "an Assessment whose Assessment Kind is Risk" in log
    assert '"relation": DESCRIBES' in log and "gv.add(pc, project, user, {\"kind\": RISK" in log
    assert "Only a Risk record describes a risk in the architecture." in inspect.getsource(rr.describe)


def test_the_routes_and_the_screen():
    app = (ROOT / "eax" / "app.py").read_text(encoding="utf-8")
    assert "from .api.risk_register import blp as risk_blp" in app and "plan_blp, risk_blp):" in app
    api = (ROOT / "eax" / "api" / "risk_register.py").read_text(encoding="utf-8")
    assert '"/projects/<string:project>/risk-register")' in api and '/risk-register/<string:record>/describes")' in api
    gov = (WEB / "ProjectGovernance.jsx").read_text(encoding="utf-8")
    assert '{kind === "Risk" && <RiskRegister p={p} />}' in gov
    ui = (WEB / "RiskRegister.jsx").read_text(encoding="utf-8")
    assert "Log it" in ui and "no control" in ui and "Describes which risk in the models?" in ui
    help_ = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "button:Log it" in help_
