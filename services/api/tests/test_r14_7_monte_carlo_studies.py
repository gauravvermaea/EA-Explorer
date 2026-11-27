"""Release 14.7: Monte Carlo studies in a project (D957, D962): the rules of eax/monte_carlo_studies.py on an in-memory
store standing in for proj.mc_studies, proj.mc_runs and proj.mc_risk_scale (the SQL is eight small helpers, checked
on PostgreSQL when the release was built), the API's routes and the MCP tools as an AI calls them. The test cases:
docs/release-14.7-test-cases.md (MC-S, MC-A, MC-R)."""

from __future__ import annotations

import ast
import copy
import itertools
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eax import monte_carlo as mc
from eax import monte_carlo_studies as ms
from eax import permissions as perms
from eax.metamodel_edit import EditError
from eax.seed import sample_monte_carlo as sample

API = Path(__file__).resolve().parents[1]
ME = perms.Principal("user_lead_architect", ("user",))
BOSS = perms.Principal("user_super_admin", ("super-admin",))
P = {"id": 7, "guid": "pg-7", "name": "Protea build or buy (sample)"}


class Store:
    """The three tables in memory, behind the module's helpers."""

    def __init__(self):
        self.studies: list[dict] = []
        self.runs: list[dict] = []
        self.scale: dict | None = None
        self.ids = itertools.count(1)
        self.readers: set[str] = set()      # usernames that may read but not change

    def install(self, mp):
        def need(pc, p, user, what="read"):
            if what != "read" and user.username in self.readers:
                raise EditError(f"Not allowed on {p['name']}: needs a contributing role (not Stakeholder).", 403)
            return set()

        def project(pc, project, user, what="read"):
            if project != P["guid"] and project != P["name"]:
                raise EditError(f"No project {project}.", 404)
            need(pc, P, user, what)
            return P
        mp.setattr(ms, "_project", project)
        mp.setattr(ms.pj, "_need", need)
        mp.setattr(ms.pj, "_super", lambda user: "super-admin" in (user.roles or ()))
        mp.setattr(ms, "_studies", lambda pc, p: sorted((s for s in self.studies if s["project_id"] == p["id"]),
                                                         key=lambda s: s["name"].lower()))
        mp.setattr(ms, "_runs", lambda pc, s: sorted((r for r in self.runs if r["study_id"] == s["id"]),
                                                      key=lambda r: -r["number"]))
        mp.setattr(ms, "_insert_study", self.insert_study)
        mp.setattr(ms, "_update_study", self.update_study)
        mp.setattr(ms, "_delete_study", self.delete_study)
        mp.setattr(ms, "_insert_run", self.insert_run)
        mp.setattr(ms, "_scale_row", lambda pc: copy.deepcopy(self.scale))
        mp.setattr(ms, "_save_scale", lambda pc, clean, who: setattr(self, "scale", {**clean, "set_by": who,
                                                                                        "set_at": datetime.now(UTC)}))
        return self

    def insert_study(self, pc, row):
        s = {"id": next(self.ids), "guid": f"00000000-0000-0000-0000-{len(self.studies):012d}", "project_id": row["project_id"],
             "name": row["name"], "kind": row["kind"], "question": row["question"], "currency": row["currency"],
             "unit": row["unit"], "runs": 10000, "seed": 1, "inputs": [], "groups": [], "settings": {},
             "created_by": row["by"], "updated_by": row["by"], "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}
        self.studies.append(s)
        return copy.deepcopy(s)

    def update_study(self, pc, sid, sets, who):
        s = next(x for x in self.studies if x["id"] == sid)
        s.update(copy.deepcopy(sets), updated_by=who, updated_at=datetime.now(UTC))

    def delete_study(self, pc, sid):
        self.studies = [s for s in self.studies if s["id"] != sid]
        self.runs = [r for r in self.runs if r["study_id"] != sid]

    def insert_run(self, pc, row):
        r = {"id": next(self.ids), "guid": f"run-{row['number']}", "study_id": row["study_id"], "number": row["number"],
             "inputs": copy.deepcopy(row["inputs"]), "runs": row["runs"], "seed": row["seed"], "digest": row["digest"],
             "result": copy.deepcopy(row["result"]), "run_by": row["by"], "run_at": datetime.now(UTC)}
        self.runs.append(r)
        return copy.deepcopy(r)


@pytest.fixture()
def store(monkeypatch):
    return Store().install(monkeypatch)


def _make(name, kind, data, unit="", cur="", by="person"):
    ms.create(None, P["guid"], ME, name, kind, "Why?", cur, unit)
    return ms.update(None, P["guid"], ME, name, data, by=by)


# ---------------------------------------------------------------- the tables and where they are kept
def test_the_migration_holds_rows_only_and_project_backups_carry_it():
    sql = (API / "migrations" / "sql" / "0127_r14_7_monte_carlo.sql").read_text(encoding="utf-8")
    for t in ("proj.mc_studies", "proj.mc_runs", "proj.mc_risk_scale"):
        assert f"CREATE TABLE IF NOT EXISTS {t}" in sql
    assert "CREATE FUNCTION" not in sql.upper() and "CREATE TRIGGER" not in sql.upper()      # rows only (D248)
    wrapper = (API / "migrations" / "versions" / "0127_r14_7_monte_carlo.py").read_text(encoding="utf-8")
    assert 'down_revision = "0125_release_14_5_0"' in wrapper
    from eax import project_backup as pb
    names = [t[0] for t in pb.TABLES]
    assert names.index("mc_studies") < names.index("mc_runs") and {"mc_studies", "mc_runs"} <= pb.NEW_GUID


# ---------------------------------------------------------------- a study (MC-S)
def test_mc_s01_s02_studies_side_by_side_and_the_model_untouched(store):
    out = ms.create(None, P["guid"], ME, "Supplier's estimates", "roadmap", "When live?")
    assert out["study"]["unit"] == "weeks" and out["link"].startswith("/#/projects/pg-7/montecarlo/")
    ms.create(None, P["guid"], ME, "Our own estimates", "roadmap", "When live?", unit="months")
    over = ms.overview(None, P["guid"], ME)
    assert [s["name"] for s in over["studies"]] == ["Our own estimates", "Supplier's estimates"]
    assert over["may_change"] and not over["may_set_scale"] and {k["kind"] for k in over["kinds"]} == set(ms.KINDS)
    with pytest.raises(EditError, match="already has a study"):
        ms.create(None, P["guid"], ME, "our own ESTIMATES", "risk")
    for bad, why in ((("", "roadmap"), "a name"), (("X", "guess"), "kind is one of"), (("X", "roadmap", "", "", "years"), "durations")):
        with pytest.raises(EditError, match=why):
            ms.create(None, P["guid"], ME, *bad)
    assert ms.create(None, P["guid"], ME, "Y", "risk", confirm=False) == {
        "preview": {"will": ["make the study Y in Protea build or buy (sample): Risk exposure"]}} and ms.count(None, P) == 2


def test_mc_s03_the_currency_is_the_studys_own(store):
    store.scale = {**ms.DEFAULT_SCALE, "currency": "ZAR", "set_by": "x", "set_at": None}
    assert ms.create(None, P["guid"], ME, "Case", "business_case")["study"]["currency"] == "ZAR"   # the installation's
    assert ms.create(None, P["guid"], ME, "Case 2", "business_case", currency="EUR")["study"]["currency"] == "EUR"


def test_mc_s04_s05_the_risk_scale_set_once_and_one_risk_overridden(store):
    assert ms.risk_scale(None)["default"] is True
    with pytest.raises(EditError, match="Super Admin"):
        ms.set_risk_scale(None, ME, ms.DEFAULT_SCALE)
    assert "preview" in ms.set_risk_scale(None, BOSS, ms.DEFAULT_SCALE, confirm=False) and store.scale is None
    scale = copy.deepcopy(ms.DEFAULT_SCALE)
    scale["likelihood"]["3"], scale["currency"] = 0.5, "ZAR"
    ms.set_risk_scale(None, BOSS, scale)
    now = ms.risk_scale(None)
    assert not now["default"] and now["likelihood"]["3"] == 0.5 and now["set_by"] == "user_super_admin"
    _make("Risks", "risk", {"inputs": [{"name": "Scaled", "likelihood": 3, "impact": 2},
                                       {"name": "Own", "chance": 0.1, "low": 5, "likely": 5, "high": 5}]})
    run = ms.run(None, P["guid"], ME, "Risks", runs=4000)["run"]
    assert run["inputs"]["scale"]["likelihood"]["3"] == 0.5                      # the run keeps the scale it used
    by = {d["input"] for d in run["result"]["result"]["drivers"]}
    assert by == {"Scaled", "Own"}


@pytest.mark.parametrize("change,why", [
    (lambda s: s.__setitem__("likelihood", {"1": 0.1}), "Likelihood 2"),
    (lambda s: s["likelihood"].__setitem__("2", 1.5), "0 to 1"),
    (lambda s: s["impact"].__setitem__("2", [1, 2]), r"\[low, likely, high\]"),
    (lambda s: s["impact"].__setitem__("2", [5, 2, 9]), "low <= likely"),
    (lambda s: s["likelihood"].__setitem__("2", 0.01), "lower than 1"),
    (lambda s: s["impact"].__setitem__("3", [0, 1, 2]), "Impact 3's likely loss is lower"),
])
def test_a_risk_scale_out_of_order_is_refused(change, why):
    s = copy.deepcopy(ms.DEFAULT_SCALE)
    change(s)
    with pytest.raises(EditError, match=why):
        ms.clean_scale(s)
    with pytest.raises(EditError, match="The scale is"):
        ms.clean_scale("high")


def test_mc_s06_a_run_kept_with_its_inputs_gives_the_same_answer_again(store):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP, "settings": {"target": 32}}, unit="weeks")
    one = ms.run(None, P["guid"], ME, "Road", runs=2000, seed=7)
    two = ms.run(None, P["guid"], ME, "Road", runs=2000, seed=7)
    assert one["run"]["number"] == 1 and two["run"]["number"] == 2
    assert one["run"]["digest"] == two["run"]["digest"] and one["run"]["result"] == two["run"]["result"]
    again = ms.get_run(None, P["guid"], ME, "Road", "#1")
    assert again["result"] == one["run"]["result"] and again["inputs"]["inputs"][0]["name"] == "Discovery and design"
    assert ms.run(None, P["guid"], ME, "Road", runs=2000, seed=8)["run"]["digest"] != one["run"]["digest"]
    assert "preview" in ms.run(None, P["guid"], ME, "Road", runs=500, confirm=False) and len(store.runs) == 3
    for bad, why in (("x", "a run is its number"), (9, "has no run 9")):
        with pytest.raises(EditError, match=why.capitalize() if why.startswith("a") else why):
            ms.get_run(None, P["guid"], ME, "Road", bad)
    for runs in (50, 200_000):
        with pytest.raises(EditError, match="Runs is 100"):
            ms.run(None, P["guid"], ME, "Road", runs=runs)


def test_mc_s07_the_study_says_when_its_inputs_changed_since_the_run(store):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP[:2]}, unit="weeks")
    ms.run(None, P["guid"], ME, "Road", runs=500)
    assert ms.get_study(None, P["guid"], ME, "Road")["changed_since"] is False
    ms.update(None, P["guid"], ME, "Road", {"inputs": sample.ROADMAP[:3]})
    s = ms.get_study(None, P["guid"], ME, "Road")
    assert s["changed_since"] is True and s["latest"]["number"] == 1 and len(s["latest"]["inputs"]["inputs"]) == 2


def test_mc_s08_a_study_deleted_takes_its_runs(store):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP[:1]}, unit="weeks")
    ms.run(None, P["guid"], ME, "Road", runs=200)
    assert ms.delete(None, P["guid"], ME, "Road", confirm=False)["preview"]["will"] == ["delete the study Road and its 1 run(s)"]
    assert ms.delete(None, P["guid"], ME, "Road")["message"].startswith("The study Road")
    assert not store.studies and not store.runs
    with pytest.raises(EditError, match="no Monte Carlo study Road") as e:
        ms.get_study(None, P["guid"], ME, "Road")
    assert e.value.status == 404


def test_mc_s09_groups_checked(store):
    ms.create(None, P["guid"], ME, "Case", "business_case")
    ms.update(None, P["guid"], ME, "Case", {"inputs": sample.CASE})
    ok = ms.update(None, P["guid"], ME, "Case", {"groups": [{"name": "Vendor", "members": ["Licences", "Running cost"]}]})
    assert ok["study"]["groups"] == [{"name": "Vendor", "members": ["Licences", "Running cost"], "strength": "medium"}]
    for groups, why in (
        ([{"name": "", "members": ["Licences", "Running cost"]}], "has no name"),
        ([{"name": "V", "members": ["Licences"]}], "at least two"),
        ([{"name": "V", "members": ["Licences", "Nope"]}], "names Nope"),
        ([{"name": "V", "members": ["Licences", "Running cost"], "strength": "total"}], "weak, medium or strong"),
        ([{"name": "A", "members": ["Licences", "Running cost"]}, {"name": "B", "members": ["Licences", "Implementation"]}],
         "in two groups"),
        ("x", "a list"), (["x"], "not an object"), ([{"name": f"g{i}"} for i in range(60)], "At most"),
    ):
        with pytest.raises(EditError, match=why):
            ms.update(None, P["guid"], ME, "Case", {"groups": groups})
    # a member taken out of the inputs takes its group with it
    ms.update(None, P["guid"], ME, "Case", {"inputs": [i for i in sample.CASE if i["name"] != "Running cost"]})
    assert ms.get_study(None, P["guid"], ME, "Case")["groups"] == []


# ---------------------------------------------------------------- the inputs, each kind
def test_an_input_keeps_who_set_it_and_where_it_came_from(store):
    _make("Case", "business_case", {"inputs": sample.CASE}, by="ai")
    first = {i["name"]: i for i in ms.get_study(None, P["guid"], ME, "Case")["inputs"]}
    assert first["Licences"]["by"] == "ai" and first["Licences"]["source"] == "Vendor quote"
    changed = [dict(i) for i in sample.CASE]
    changed[0] = {**changed[0], "high": 13_000_000}
    ms.update(None, P["guid"], ME, "Case", {"inputs": changed})
    now = {i["name"]: i for i in ms.get_study(None, P["guid"], ME, "Case")["inputs"]}
    assert now["Licences"]["by"] == "person" and now["Implementation"]["by"] == "ai"        # MC-U02


@pytest.mark.parametrize("kind,item,why", [
    ("roadmap", {"name": "A", "low": 5, "likely": 4, "high": 9}, "low <= likely <= high"),
    ("roadmap", {"name": "A", "low": -1, "likely": 4, "high": 9}, "low is 0 or more"),
    ("roadmap", {"name": "A", "low": "x", "likely": 4, "high": 9}, "must be a number"),
    ("roadmap", {"name": "A", "low": float("nan"), "likely": 4, "high": 9}, "must be a number"),
    ("roadmap", {"name": "A", "low": 1, "likely": 4, "high": 9, "shape": "lognormal"}, "log-normal waits"),
    ("roadmap", {"name": "A", "low": 1, "likely": 4, "high": 9, "after": "B"}, "after is a list"),
    ("roadmap", {"name": "A", "low": 1, "likely": 4, "high": 9, "after": ["B"]}, "waits for B"),
    ("roadmap", {"name": "", "low": 1, "likely": 4, "high": 9}, "has no name"),
    ("business_case", {"name": "A", "low": 1, "likely": 4, "high": 9}, "benefit or cost"),
    ("scenarios", {"option": "A", "low": 1, "likely": 4, "high": 9}, "option and its future"),
    ("risk", {"name": "A", "low": 1, "likely": 4, "high": 9}, "chance in a year"),
    ("risk", {"name": "A", "chance": 1.2, "impact": 2}, "from 0 to 1"),
    ("risk", {"name": "A", "likelihood": 6, "impact": 2}, "1 to 5"),
    ("risk", {"name": "A", "chance": 0.2}, "its loss"),
    ("risk", {"name": "A", "chance": 0.2, "impact": 2, "likelihood_after": 0}, "1 to 5"),
    ("guess", {"name": "A"}, "kind is one of"),
])
def test_an_input_out_of_shape_is_refused_saying_which(kind, item, why):
    with pytest.raises(EditError, match=why):
        ms.clean_inputs(kind, [item], "me", "person")


def test_inputs_refused_as_a_whole():
    with pytest.raises(EditError, match="a list"):
        ms.clean_inputs("roadmap", {"name": "A"}, "me", "person")
    with pytest.raises(EditError, match="not an object"):
        ms.clean_inputs("roadmap", ["A"], "me", "person")
    with pytest.raises(EditError, match="Two inputs"):
        ms.clean_inputs("roadmap", [{"name": "A", "low": 1, "likely": 1, "high": 1}] * 2, "me", "person")
    with pytest.raises(EditError, match="At most"):
        ms.clean_inputs("roadmap", [{}] * 501, "me", "person")
    loop = [{"name": "A", "low": 1, "likely": 1, "high": 1, "after": ["B"]}, {"name": "B", "low": 1, "likely": 1, "high": 1, "after": ["A"]}]
    with pytest.raises(EditError, match="dependency loop"):
        ms.clean_inputs("roadmap", loop, "me", "person")


def test_settings_checked_for_each_kind(store):
    road = [{"name": "A", "low": 1, "likely": 2, "high": 3}]
    assert ms.clean_settings("roadmap", None, road) == {}
    assert ms.clean_settings("roadmap", {"target": "5", "milestones": [{"name": "M", "packages": ["A"]}]}, road) == {
        "target": 5.0, "milestones": [{"name": "M", "packages": ["A"]}]}
    for s, why in (("x", "an object"), ({"milestones": [{"name": "M", "packages": []}]}, "has a name"),
                   ({"milestones": [{"name": "M", "packages": ["Z"]}]}, "names Z")):
        with pytest.raises(EditError, match=why):
            ms.clean_settings("roadmap", s, road)
    assert ms.clean_settings("risk", {"amounts": [20, 5, 5]}, []) == {"amounts": [5.0, 20.0]}
    with pytest.raises(EditError, match="list of numbers"):
        ms.clean_settings("risk", {"amounts": 5}, [])
    sc = [{"option": "A", "future": "F1"}, {"option": "A", "future": "F2"}]
    assert ms.clean_settings("scenarios", {"weights": {"F1": 1, "F2": 3}}, sc) == {"weights": {"F1": 1.0, "F2": 3.0}}
    for w, why in (({"F1": 1}, "every future"), ({"F1": 0, "F2": 0}, "not all 0"), ({"F1": -1, "F2": 2}, "0 or more")):
        with pytest.raises(EditError, match=why):
            ms.clean_settings("scenarios", {"weights": w}, sc)
    assert ms.clean_settings("business_case", {"anything": 1}, []) == {}


def test_update_checks_each_part(store):
    ms.create(None, P["guid"], ME, "Road", "roadmap")
    ms.create(None, P["guid"], ME, "Other", "roadmap")
    out = ms.update(None, P["guid"], ME, "Road", {"name": "Road map", "question": "When?", "currency": "ZAR", "unit": "days",
                                                   "runs": 5000, "seed": 42})
    assert set(out["changed"]) == {"name", "question", "currency", "unit", "runs", "seed"}
    s = ms.get_study(None, P["guid"], ME, "Road map")
    assert (s["unit"], s["runs"], s["seed"]) == ("days", 5000, 42)
    for data, why in (({"name": "other"}, "already has"), ({"unit": "years"}, "durations"), ({"runs": 10}, "Runs is 100"),
                      ({}, "Nothing to change"), ("x", "Send the parts")):
        with pytest.raises(EditError, match=why):
            ms.update(None, P["guid"], ME, "Road map", data)
    assert "preview" in ms.update(None, P["guid"], ME, "Road map", {"question": "Q"}, confirm=False)
    assert ms.get_study(None, P["guid"], ME, s["id"])["question"] == "When?"        # found by its id too


def test_reading_needs_a_role_changing_a_contributing_one(store):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP[:1]}, unit="weeks")
    store.readers.add("user_stakeholder")
    reader = perms.Principal("user_stakeholder", ("user",))
    assert ms.overview(None, P["guid"], reader)["may_change"] is False
    assert ms.get_study(None, P["guid"], reader, "Road")["name"] == "Road"
    for fn in (lambda: ms.run(None, P["guid"], reader, "Road"), lambda: ms.delete(None, P["guid"], reader, "Road"),
               lambda: ms.update(None, P["guid"], reader, "Road", {"question": "x"}),
               lambda: ms.create(None, P["guid"], reader, "New", "risk")):
        with pytest.raises(EditError, match="contributing role") as e:
            fn()
        assert e.value.status == 403
    with pytest.raises(EditError, match="No project"):
        ms.overview(None, "nope", ME)


# ---------------------------------------------------------------- each kind worked out
def test_roadmap_confidence_with_a_target_and_milestones(store):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP, "groups": [{"name": "Vendor", "members": ["Vendor set-up",
                                                                     "Product configuration"], "strength": "strong"}],
                              "settings": {"target": 32, "milestones": [{"name": "Pilot live", "packages": ["Product configuration"], "by": 22},
                                                                        {"name": "Tested", "packages": ["Testing"]}]}}, unit="weeks")
    res = ms.run(None, P["guid"], ME, "Road", runs=3000)["run"]["result"]
    r = res["result"]
    assert r["p10"] <= r["p50"] <= r["p80"] <= r["p90"] and 0 <= res["target"]["chance"] <= 1
    assert r["critical"]["Discovery and design"] == 1.0                              # everything waits for it
    pilot, tested = res["milestones"]
    assert pilot["p80"] < r["p80"] and "chance" in pilot and "chance" not in tested
    assert any("critical path" in w for w in res["in_words"]) and any("Pilot live" in w for w in res["in_words"])


def test_a_business_case_net_value_and_the_chance_it_pays(store):
    _make("Case", "business_case", {"inputs": sample.CASE}, cur="ZAR")
    res = ms.run(None, P["guid"], ME, "Case", runs=3000)["run"]["result"]
    assert 0 < res["chance_positive"] < 1 and res["in_words"][0].startswith("The net value is ZAR")
    _make("Costs only", "business_case", {"inputs": [{"name": "C", "side": "cost", "low": 5, "likely": 5, "high": 5}]})
    only = ms.run(None, P["guid"], ME, "Costs only", runs=200)["run"]["result"]
    assert only["chance_positive"] == 0 and only["result"]["p50"] == -5


def test_risk_exposure_before_and_after_controls_and_its_amounts(store):
    _make("Risks", "risk", {"inputs": sample.RISKS, "settings": {"amounts": [5_000_000, 20_000_000]}}, cur="ZAR")
    res = ms.run(None, P["guid"], ME, "Risks", runs=4000)["run"]["result"]
    assert 0 < res["chance_none"] < 1 and res["after"]["mean"] < res["result"]["mean"]
    assert [a["amount"] for a in res["amounts"]] == [5_000_000, 20_000_000]
    assert all(a["after"] <= a["before"] for a in res["amounts"])
    assert any("After controls" in w for w in res["in_words"])
    _make("No controls", "risk", {"inputs": [{"name": "R", "chance": 0.5, "impact": 1}]})
    plain = ms.run(None, P["guid"], ME, "No controls", runs=500)["run"]["result"]
    assert "after" not in plain and plain["amounts"] == []


def test_scenarios_each_options_chance_of_being_best(store):
    _make("Futures", "scenarios", {"inputs": sample.SCORES, "settings": {"weights": {sample.F[0]: 0.2, sample.F[1]: 0.3,
                                                                                     sample.F[2]: 0.3, sample.F[3]: 0.2}}})
    res = ms.run(None, P["guid"], ME, "Futures", runs=3000)["run"]["result"]
    assert res["weighted"] and sum(res["across"].values()) == pytest.approx(1.0)
    assert res["in_each"]["Rules race ahead"]["Buy the policy suite"] == 1.0
    assert res["in_words"][0].startswith("Weighted by how likely")
    ms.update(None, P["guid"], ME, "Futures", {"settings": {}})
    assert ms.run(None, P["guid"], ME, "Futures", runs=500)["run"]["result"]["in_words"][0].startswith("Over all the futures")
    ms.update(None, P["guid"], ME, "Futures", {"inputs": sample.SCORES[:-1]})
    with pytest.raises(EditError, match="score in every future; missing: Buy the policy suite in Fast on both fronts"):
        ms.run(None, P["guid"], ME, "Futures")


def test_a_study_without_inputs_says_what_to_do(store):
    ms.create(None, P["guid"], ME, "Empty", "roadmap")
    with pytest.raises(EditError, match="no inputs yet"):
        ms.run(None, P["guid"], ME, "Empty")
    with pytest.raises(EditError, match="kind is one of"):
        ms.work({"kind": "guess", "inputs": [{"name": "x"}]}, ms.DEFAULT_SCALE, 100, 1)


def test_the_engines_refusal_is_said_in_words(store, monkeypatch):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP[:1]}, unit="weeks")
    monkeypatch.setattr(mc, "schedule", lambda *a, **k: (_ for _ in ()).throw(ValueError("the engine says no")))
    with pytest.raises(EditError, match="the engine says no"):
        ms.run(None, P["guid"], ME, "Road")


# ---------------------------------------------------------------- reports and exports (MC-R)
def test_mc_r01_r02_the_project_report_and_the_csv(store):
    _make("Road", "roadmap", {"inputs": sample.ROADMAP, "settings": {"milestones": [{"name": "M", "packages": ["Testing"], "by": 20}]}},
          unit="weeks")
    _make("Case", "business_case", {"inputs": sample.CASE})
    _make("Risks", "risk", {"inputs": sample.RISKS, "settings": {"amounts": [1_000_000]}})
    _make("Futures", "scenarios", {"inputs": sample.SCORES})
    ms.create(None, P["guid"], ME, "Not run", "risk")
    for n in ("Road", "Case", "Risks", "Futures"):
        ms.run(None, P["guid"], ME, n, runs=500)
    sec = ms.report_section(None, P)
    assert [s["name"] for s in sec] == ["Case", "Futures", "Risks", "Road"] and all(s["in_words"] for s in sec)
    assert sec[3]["s_curve"][0]["chance"] == 0 and sec[3]["s_curve"][-1]["chance"] == 1
    for n, want in (("Road", "Share of runs on the critical path"), ("Case", "Chance the net value is positive"),
                    ("Risks", "Chance of losses above 1000000.0"), ("Futures", "Chance of being best")):
        rows, name = ms.run_rows(None, P["guid"], ME, n, 1)
        flat = [str(c) for r in rows for c in r]
        assert name == f"{n} run 1" and any(want in c for c in flat) and "In words" in flat, n
    over = ms.overview(None, P["guid"], ME)["studies"]
    assert {s["name"]: s["latest"] is None for s in over}["Not run"] and over[0]["latest"]["in_words"]


# ---------------------------------------------------------------- the sample, the API and the MCP tools (MC-A)
def test_the_sample_studies_all_run(store):
    for name, kind, data, unit, cur in (
        ("Policy platform roadmap", "roadmap", {"inputs": sample.ROADMAP}, "weeks", ""),
        ("Five-year case", "business_case", {"inputs": sample.CASE}, "", "ZAR"),
        ("Platform risks", "risk", {"inputs": sample.RISKS}, "", "ZAR"),
        ("Build or buy across the futures", "scenarios", {"inputs": sample.SCORES}, "", ""),
    ):
        _make(name, kind, data, unit, cur, by="ai")
        assert ms.run(None, P["guid"], ME, name, runs=500)["in_words"], name
    src = (API / "eax" / "seed" / "later.py").read_text(encoding="utf-8")
    assert "sample_monte_carlo" in src


def test_the_api_routes_and_the_mcp_tools_are_there():
    api = (API / "eax" / "api" / "monte_carlo.py").read_text(encoding="utf-8")
    for route in ('"/projects/<string:project>/monte-carlo"', '"/projects/<string:project>/monte-carlo/<string:study>"',
                  '"/projects/<string:project>/monte-carlo/<string:study>/run"', '"/monte-carlo/risk-scale"',
                  '"/projects/<string:project>/monte-carlo/<string:study>/runs"',
                  '"/projects/<string:project>/monte-carlo/<string:study>/runs/<string:number>/csv"'):
        assert route in api, route
    assert "monte_carlo_blp" in (API / "eax" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse((API / "eax" / "mcp_monte_carlo.py").read_text(encoding="utf-8"))
    tools = {f.name: f for f in tree.body if isinstance(f, ast.AsyncFunctionDef)}
    assert {"how_to_run_monte_carlo", "mc_kinds", "mc_overview", "mc_study", "mc_run_result", "mc_risk_scale",
            "mc_start", "mc_save", "mc_run"} <= set(tools)
    assert not any("delete" in n for n in tools)                                      # nothing deleted through MCP (R4.22)
    for n in ("mc_start", "mc_save", "mc_run"):                                       # a preview, then a yes (D458)
        assert "confirm" in [a.arg for a in tools[n].args.args], n
    from eax import mcp_catalogue
    assert mcp_catalogue.AREAS["mcp_monte_carlo"].startswith("Monte Carlo")
    from eax.testing import mcp_check
    assert "study" in mcp_check.GUESSED and "study" in mcp_check.AN_ID


def test_mc_a01_the_ai_drafts_through_a_preview(store):
    ms.create(None, P["guid"], ME, "Case", "business_case")
    seen = ms.update(None, P["guid"], ME, "Case", {"inputs": sample.CASE}, by="ai", confirm=False)
    assert seen["preview"]["inputs"][0]["by"] == "ai" and ms.get_study(None, P["guid"], ME, "Case")["inputs"] == []
    ms.update(None, P["guid"], ME, "Case", {"inputs": sample.CASE}, by="ai")
    assert {i["by"] for i in ms.get_study(None, P["guid"], ME, "Case")["inputs"]} == {"ai"}


def test_words_for_small_and_large_numbers():
    assert ms._f(12.345) == "12.3" and ms._f(12_345) == "12,345" and ms._pct(0.125) == "12%"  # noqa: SLF001
    assert ms.kinds()[0]["kind"] == "roadmap" and ms.STEPS[0].startswith("1.")


def test_a_study_is_read_as_the_projects_rules_say(monkeypatch):
    asked = []
    monkeypatch.setattr(ms.pj, "project_row", lambda pc, project: {**P, "asked": project})
    monkeypatch.setattr(ms.pj, "_need", lambda pc, p, user, what: asked.append((p["asked"], user.username, what)))
    assert ms._project(None, "Protea", ME, "contribute")["asked"] == "Protea"  # noqa: SLF001 - the projects' own rules
    assert asked == [("Protea", "user_lead_architect", "contribute")]
