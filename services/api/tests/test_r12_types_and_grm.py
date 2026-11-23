"""Release 12 (D879, D887): no new element types; the existing ones carry the risk, security, data governance and Agile
attributes, added to an installation's ArchiMate 4 root when missing; and the TOGAF Government Reference Model (GRM) in the library (R12.1).

Checked on a real PostgreSQL while building (22 Nov 2026): Release 11's roots loaded, then the upgrade run twice: the
first added the eight types to each root (ArchiMate 4 49 to 57, TOGAF 10 41 to 49), the second changed nothing; the GRM
loaded as a locked reference model with 278 elements and 267 relationships.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from eax.seed import archimate4 as A
from eax.seed import build, togaf10
from eax.seed import industries as IND
from eax.seed import industry_grm as GRM

ROOT = Path(__file__).resolve().parents[3]
SEED_MAIN = (ROOT / "services" / "api" / "eax" / "seed" / "__main__.py").read_text(encoding="utf-8")
NEW_ATTRS = {"Likelihood", "Impact", "InherentRisk", "RiskTreatment", "ResidualRisk", "SecurityProperty", "DataSteward",
             "SystemOfRecord", "QualityDimension", "AcceptanceCriteria", "AssessmentKind", "RequirementKind", "BacklogLevel"}
GONE = {"Risk", "Threat", "SecurityRequirement", "DataDomain", "QualityRule", "AnalyticsProduct", "Epic", "Feature"}


def test_no_new_types_the_existing_ones_carry_attributes():
    """The owner, 23 Nov 2026, after the duplicate review: "Always use the existing names of models do not create new
    types. Add attributes where missing." (D887)."""
    assert not GONE & {t[0] for t in A.ENTITY_TYPES} and not GONE & {t[0] for t in togaf10.TYPES}
    assert {t[0] for t in A.EXTENSIONS} == {"ValueStreamStage", "ProductLifecycleStage", "BusinessScenario", "Control", "Contract", "Measure"}
    assert set(build.UPGRADE_ATTRS) == NEW_ATTRS and NEW_ATTRS <= {a[0] for a in A.ATTRS}

    def attrs(t):
        return {a for a, *_ in A.MAP[t]}
    assert {"AssessmentKind", "Likelihood", "Impact", "InherentRisk", "RiskTreatment", "ResidualRisk"} <= attrs("Assessment")
    assert {"RequirementKind", "SecurityProperty", "QualityDimension", "Target"} <= attrs("Requirement")
    assert {"DataSteward", "DataClassification"} <= attrs("Grouping")
    assert {"DataSteward", "SystemOfRecord"} <= attrs("BusinessObject") and {"DataSteward", "SystemOfRecord"} <= attrs("DataObject")
    assert {"BacklogLevel", "AcceptanceCriteria"} <= attrs("WorkPackage")
    assert A.LISTS["AssessmentKind"] == ["Risk", "Threat", "Vulnerability", "Finding"]
    assert A.LISTS["BacklogLevel"] == ["Epic", "Feature", "Story"]
    assert "Security" in A.LISTS["RequirementKind"] and "Data quality" in A.LISTS["RequirementKind"]
    rules = {(a, r) for a, _t, r, *_ in A.RULES}
    assert ("Likelihood", "Range") in rules and ("Impact", "Range") in rules
    allowed = {(s, r, t) for s, r, t, _ in build.expand_allowed()}
    assert ("Control", "Influence", "Assessment") in allowed


def test_an_existing_installation_gets_the_attributes_and_nothing_else_changes():
    sql = build.root_upgrade_sql()
    inserts = sql.count("INSERT INTO")
    assert inserts and sql.count("ON CONFLICT DO NOTHING") == inserts       # only what is missing; nothing updated
    assert "UPDATE " not in sql and "DELETE " not in sql and "INSERT INTO core.models" not in sql
    assert build.gid(build.TEMPLATE_KEY, "attribute_type", "Likelihood") in sql   # the guid a new installation gives it
    assert "ON CONFLICT" not in build.seed_sql(with_sample=False, with_insurance=False)
    assert "root_upgrade_sql()" in SEED_MAIN and "UPGRADE_ATTRS" in SEED_MAIN and "have < len(UPGRADE_ATTRS)" in SEED_MAIN


def test_the_demo_estate_uses_the_existing_types_with_the_new_attributes():
    from eax.seed import demo_estate as D
    by_name = {e[1]: e for e in D.E}
    assert by_name["Customer data exposed through the portal"][0] == "Assessment"
    assert by_name["Online claims"][0] == "WorkPackage" and by_name["Claims dashboard"][0] == "DataObject"
    assert not GONE & {t for t, *_ in D.E}


def test_the_grm_is_in_the_library_as_a_locked_reference_model():
    row = next(m for m in IND.MODELS if m[0] == "grm")
    assert IND.model_name("grm") == "Government Reference Model (TOGAF GRM)"
    assert "www.opengroup.org/library/g21d" in row[3] and "EA Explorer's own" in row[3]
    sql = build.seed_sql(with_template=False, with_insurance=False, with_sample=False, with_principles=False,
                         with_togaf10=False, with_industries={"grm"})
    assert sql.count("INSERT INTO core.models") == 1 and "'Government Reference Model (TOGAF GRM)'" in sql and "'reference'" in sql


def test_the_grm_has_its_eleven_sectors_with_functions_services_and_drivers():
    by_key = {k: (t, n, d, p) for k, t, n, d, p, _a in GRM.ENTITIES}
    sectors = [k for k in by_key if re.fullmatch(r"S\d\d", k)]
    assert len(sectors) == 11 and all(by_key[k][0] == "Function" for k in sectors)
    names = [by_key[k][1] for k in sectors]
    assert names[0] == "International Affairs and Trade" and names[-1] == "Transport and Operations" and "Shared Services" in names
    functions = [k for k in by_key if re.fullmatch(r"S\d\d\.F\d\d", k)]
    services = [k for k in by_key if re.fullmatch(r"S\d\d\.F\d\d\.V\d\d", k)]
    drivers = [k for k in by_key if re.fullmatch(r"S\d\d\.D\d\d", k)]
    assert len(functions) == 36 and len(services) == 196 and len(drivers) == 35
    assert all(by_key[k][3] == k[:3] and by_key[k][0] == "Function" for k in functions)
    assert all(by_key[k][3] == k[:7] and by_key[k][0] == "Service" for k in services)
    assert all(by_key[k][0] == "Driver" and by_key[k][3] is None for k in drivers)
    assert every_sector_has_a_driver(by_key, sectors, drivers)
    # each level says what it is, in EA Explorer's own words, never a copy of the guide
    assert all(by_key[k][2].startswith("Government Reference Model, Level 3 service of ") for k in services)
    rels = {(s, r, t) for s, r, t, _n in GRM.RELATIONSHIPS}
    assert all((k[:3], "Composition", k) in rels for k in functions)
    assert all((k[:7], "Realization", k) in rels for k in services)
    assert all((k, "Association", k[:3]) in rels for k in drivers)


def every_sector_has_a_driver(by_key, sectors, drivers) -> bool:
    """Each sector has at least one driver for change."""
    return {d[:3] for d in drivers} == set(sectors)


def test_the_grm_module_is_made_by_its_tool_from_the_taxonomy():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_grm_model as B
    ents, rels = B.build()
    assert ents == [tuple(e) for e in GRM.ENTITIES] and rels == [tuple(r) for r in GRM.RELATIONSHIPS]
    assert "do not edit by hand" in (ROOT / "services" / "api" / "eax" / "seed" / "industry_grm.py").read_text(encoding="utf-8")
