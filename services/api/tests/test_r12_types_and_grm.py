"""Release 12 (D879): the risk and security, data governance and Agile types in both root metamodels, added to an
installation that already has them; and the TOGAF Government Reference Model (GRM) in the library (R12.1).

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
NEW = {"Risk", "Threat", "SecurityRequirement", "DataDomain", "QualityRule", "AnalyticsProduct", "Epic", "Feature"}


def test_the_new_types_are_in_both_roots_as_extensions():
    assert set(build.UPGRADE_TYPES) == NEW
    assert NEW <= {t[0] for t in A.EXTENSIONS} and not NEW & set(A.SPEC_TYPES)
    assert all(A.EXTENSION_DESCRIPTIONS[t].startswith(A.EXTENSION_NOTE) for t in NEW)
    assert NEW <= {t[0] for t in togaf10.TYPES}
    assert all(d.startswith("EA Explorer extension") for c, _n, _l, _p, _a, d in togaf10.TYPES if c in NEW)


def test_the_risk_data_and_agile_attributes():
    def attrs(t):
        return {a for a, *_ in A.MAP[t]}
    assert {"Likelihood", "Impact", "InherentRisk", "RiskTreatment", "ResidualRisk"} <= attrs("Risk")
    assert "SecurityProperty" in attrs("SecurityRequirement")
    assert {"DataSteward", "SystemOfRecord"} <= attrs("BusinessObject") and {"DataSteward", "SystemOfRecord"} <= attrs("DataObject")
    assert {"QualityDimension", "Target"} <= attrs("QualityRule")
    assert {"AcceptanceCriteria", "Priority"} <= attrs("Epic") and attrs("Epic") == attrs("Feature")
    rules = {(a, r) for a, _t, r, *_ in A.RULES}
    assert ("Likelihood", "Range") in rules and ("Impact", "Range") in rules


def test_the_new_relationships_are_allowed():
    allowed = {(s, r, t) for s, r, t, _ in build.expand_allowed()}
    for triple in [("Threat", "Influence", "Risk"), ("Control", "Influence", "Risk"), ("Risk", "Influence", "Goal"),
                   ("ApplicationComponent", "Realization", "SecurityRequirement"), ("DataDomain", "Aggregation", "BusinessObject"),
                   ("ApplicationComponent", "Realization", "AnalyticsProduct"), ("Epic", "Aggregation", "Feature"),
                   ("Feature", "Realization", "Capability"), ("Feature", "Realization", "Requirement")]:
        assert triple in allowed, triple


def test_an_existing_installation_gets_the_types_and_nothing_else_changes():
    sql = build.root_upgrade_sql()
    inserts = sql.count("INSERT INTO")
    assert inserts and sql.count("ON CONFLICT DO NOTHING") == inserts       # only what is missing; nothing updated
    assert "UPDATE " not in sql and "DELETE " not in sql and "INSERT INTO core.models" not in sql
    assert build.gid("entity_type", "x") != build.gid("entity_type", "y")
    # the guids are those a new installation gives the same rows, so both kinds of installation match
    assert build.gid(build.TEMPLATE_KEY, "entity_type", "Risk") in sql
    assert build.gid(togaf10.KEY, "entity_type", "Risk") in sql
    # a new installation's seed is unchanged: no ON CONFLICT there
    assert "ON CONFLICT" not in build.seed_sql(with_sample=False, with_insurance=False)
    # the seed runs it when either root lacks one of the types, and says so
    assert "root_upgrade_sql()" in SEED_MAIN and "UPGRADE_TYPES" in SEED_MAIN and "2 * len(UPGRADE_TYPES)" in SEED_MAIN


def test_the_demo_estate_has_one_of_each_new_type():
    from eax.seed import demo_estate as D
    assert NEW <= {t for t, *_ in D.E}


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
