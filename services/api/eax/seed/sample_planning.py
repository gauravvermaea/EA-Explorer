"""Scenario planning and game theory, the sample (Release 10, R10.4; D788, D857): laptop only, made once, on
"Protea build or buy (sample)", where scenario A: build and B: buy are already compared (sample_scenarios). Every name
is invented.

* **Version 1** (finished): "Should Protea build or buy its policy platform, whatever the next five years bring?" on the
  grid template: four driving forces; two critical uncertainties (how fast regulation moves, how fast customers move to
  digital); four futures with their stories and signposts; the players (Protea, a rival insurer, the policy suite's
  vendor) and two games (a pricing game played at once, and a negotiation in turn); the two options (pointing to the
  scenario models) scored in every future, in money, scores and words.
* **Version 2** (finished, a re-run): started from version 1 after the vendor's price rise, with the buy option scored
  again; the recommendation stays "buy", more narrowly; signpost SP-1 marked seen at the last review.

Made through the same code the AI uses (eax/scenario_planning.py), as the Lead Architect.
"""

from __future__ import annotations

from sqlalchemy import text

PROJECT = "Protea build or buy (sample)"
A, B = "Protea scenario A: build", "Protea scenario B: buy"
BUILD, BUY = "Build in house", "Buy the policy suite"
F1, F2, F3, F4 = "Slow and steady", "Rules race ahead", "Digital rush", "Fast on both fronts"

FORCES = [
    {"name": "Insurance regulation (conduct, data, solvency)", "kind": "regulation", "impact": 5, "uncertainty": 4,
     "note": "New conduct and data rules expected; timing unclear."},
    {"name": "Customers moving to digital self-service", "kind": "social", "impact": 5, "uncertainty": 4,
     "note": "Younger customers expect to buy and claim on the phone."},
    {"name": "Cost of skilled engineers", "kind": "economic", "impact": 3, "uncertainty": 2, "note": ""},
    {"name": "Cloud policy platforms maturing", "kind": "technology", "impact": 4, "uncertainty": 2, "note": ""},
]
UNCERTAINTIES = [
    {"name": "Pace of regulation", "low": "Slow, predictable change", "high": "Fast, frequent new rules",
     "force": "Insurance regulation (conduct, data, solvency)"},
    {"name": "Customer shift to digital", "low": "Gradual, branches still matter", "high": "Rapid, digital first",
     "force": "Customers moving to digital self-service"},
]
FUTURES = [
    {"name": F1, "when": "2027 to 2031", "positions": {"Pace of regulation": "low", "Customer shift to digital": "low"},
     "story": "Rules change slowly and customers keep using brokers and branches. The platform must above all be cheap to run.",
     "true": ["Few new reporting rules", "Broker channel still over half of sales"], "model": A},
    {"name": F2, "when": "2027 to 2031", "positions": {"Pace of regulation": "high", "Customer shift to digital": "low"},
     "story": "Regulators issue new conduct and data rules every year; customers change slowly. Speed of rule changes wins.",
     "true": ["Annual rule changes to products", "Data residency enforced"], "model": B},
    {"name": F3, "when": "2027 to 2031", "positions": {"Pace of regulation": "low", "Customer shift to digital": "high"},
     "story": "Customers move to the phone fast while rules stay put. New digital products every quarter.",
     "true": ["Digital sales pass brokers by 2029", "Quarterly product launches"], "model": A},
    {"name": F4, "when": "2027 to 2031", "positions": {"Pace of regulation": "high", "Customer shift to digital": "high"},
     "story": "Both at once: frequent new rules and a rush to digital. Only a platform that changes quickly keeps up.",
     "true": ["Rule changes and product launches every quarter"], "model": B},
]
SIGNPOSTS = [
    {"future": F2, "sign": "The regulator publishes draft conduct rules for policy data", "watch": "Regulator's consultation papers",
     "level": "A draft with a date"},
    {"future": F3, "sign": "Digital sales pass 30% of new policies", "watch": "Monthly sales by channel", "level": "30% for two quarters"},
    {"future": F4, "sign": "Two competitors launch app-only products", "watch": "Market launches", "level": "Two within a year"},
    {"future": F1, "sign": "Broker share stays above 55%", "watch": "Monthly sales by channel", "level": "55% for a year"},
]
PLAYERS = [
    {"name": "Protea", "kind": "organisation", "goals": "A policy platform that keeps up with rules and customers at a cost it can carry."},
    {"name": "Rival insurer", "kind": "competitor", "goals": "Win digital customers on price."},
    {"name": "Suite vendor", "kind": "supplier", "goals": "Sell the policy suite at the best price, and keep Protea for ten years."},
]


def _pricing() -> dict:
    v = {("Hold price", "Hold price"): (3, 3), ("Hold price", "Cut price"): (0, 5),
         ("Cut price", "Hold price"): (5, 0), ("Cut price", "Cut price"): (1, 1)}
    return {"name": "Digital pricing", "kind": "simultaneous", "players": ["Protea", "Rival insurer"],
            "options": {"Protea": ["Hold price", "Cut price"], "Rival insurer": ["Hold price", "Cut price"]},
            "payoffs": [{"options": {"Protea": a, "Rival insurer": b}, "values": {"Protea": x, "Rival insurer": y}}
                        for (a, b), (x, y) in v.items()],
            "note": "Scores 0 to 5: market share and margin together."}


def _negotiation(discount: bool = True) -> dict:
    vendor_then = {"player": "Suite vendor", "choices": [
        {"option": "Give a discount", "then": {"values": {"Protea": {"money": 2_500_000, "currency": "ZAR"},
                                                          "Suite vendor": {"money": 9_000_000, "currency": "ZAR"}}}},
        {"option": "Hold the list price", "then": {"values": {"Protea": {"money": 2_000_000, "currency": "ZAR"},
                                                              "Suite vendor": {"money": 10_500_000 if discount else 11_000_000,
                                                                               "currency": "ZAR"}}}}]}
    return {"name": "Suite negotiation", "kind": "sequential", "players": ["Protea", "Suite vendor"],
            "tree": {"player": "Protea", "choices": [
                {"option": BUY, "then": vendor_then},
                {"option": BUILD, "then": {"values": {"Protea": {"money": 1_500_000, "currency": "ZAR"},
                                                      "Suite vendor": {"money": 0, "currency": "ZAR"}}}}]},
            "note": "Five-year saving for Protea and revenue for the vendor."}


OPTIONS = [{"name": BUILD, "model": A, "description": "Build the policy platform in house on the cloud data platform."},
           {"name": BUY, "model": B, "description": "Buy the policy suite and retire the rules engine."}]


def _scores(buy_rush: dict) -> list[dict]:
    return [
        {"option": BUILD, "future": F1, "value": 3, "why": "Cheap to run once built."},
        {"option": BUILD, "future": F2, "value": {"words": "much worse", "score": -2}, "why": "Every rule change is our own work."},
        {"option": BUILD, "future": F3, "value": 4, "why": "Our own product team moves fast."},
        {"option": BUILD, "future": F4, "value": {"words": "a bit worse", "score": -1}, "why": "Too much change for one team."},
        {"option": BUY, "future": F1, "value": 1, "why": "Licence costs weigh most when little changes."},
        {"option": BUY, "future": F2, "value": 4, "why": "The vendor ships rule changes."},
        {"option": BUY, "future": F3, **buy_rush},
        {"option": BUY, "future": F4, "value": 3, "why": "Rules from the vendor, products configured."},
    ]


def run() -> list[str]:
    """Loads the sample study (two versions) once."""
    from .. import permissions as perms
    from .. import projects as pj
    from .. import scenario_planning as sp
    try:
        with pj.connections(True) as pc:
            p = pc.execute(text("SELECT id, guid::text AS g FROM proj.projects WHERE name = :n"), {"n": PROJECT}).mappings().first()
            if not p:
                return [f"scenario planning sample skipped: {PROJECT} is not there"]
            if pc.execute(text("SELECT 1 FROM proj.sp_runs WHERE project_id = :p LIMIT 1"), {"p": p["id"]}).first():
                return []
    except Exception as exc:  # noqa: BLE001 - an older database: nothing to do
        return [f"scenario planning sample skipped: {exc}"]
    who = perms.Principal("user_super_admin", ("super-admin",))
    token = perms.current.set(who)
    try:
        with pj.connections(True) as pc:
            g = p["g"]
            sp.start(pc, g, who, "Should Protea build or buy its policy platform, whatever the next five years bring?", "grid", confirm=True)
            for part, items in (("forces", FORCES), ("uncertainties", UNCERTAINTIES), ("futures", FUTURES), ("signposts", SIGNPOSTS),
                                ("players", PLAYERS), ("games", [_pricing(), _negotiation()]), ("options", OPTIONS),
                                ("scores", _scores({"value": 2, "why": "Configurable, but slower than our own team."}))):
                sp.save(pc, g, who, part, items, confirm=True)
            sp.finish(pc, g, who, "Buy the policy suite. It is the most robust choice: it is never badly placed, and it wins "
                      "when regulation moves fast, which the signposts say is the more likely.\n\nBuilding in house wins "
                      "only if rules stay put; keep it as the fallback if the vendor will not move on price.", BUY, confirm=True)
            sp.start(pc, g, who, "Build or buy, again after the vendor's 2027 price rise?", "grid", copy_latest=True, confirm=True)
            sp.save(pc, g, who, "games", [_pricing(), _negotiation(discount=False)], confirm=True)
            sp.save(pc, g, who, "scores", _scores({"value": {"money": 500_000, "currency": "ZAR"},
                                                   "why": "After the price rise: a small five-year saving."}), confirm=True)
            sp.finish(pc, g, who, "Still buy the policy suite, more narrowly: the price rise cuts its lead where customers rush "
                      "to digital. Negotiate the discount before signing.", BUY, confirm=True)
            sp.mark_signposts(pc, g, who, [{"signpost": "SP-1", "seen": True, "note": "Draft rules published for comment."},
                                          {"signpost": "SP-2", "seen": False, "note": "Digital at 22% of new policies."}], confirm=True)
        return [f"{PROJECT}: scenario planning, two finished versions and a review's signpost marks"]
    except Exception as exc:  # noqa: BLE001 - the sample never stops the rest
        return [f"scenario planning sample not made: {exc}"]
    finally:
        perms.current.reset(token)
