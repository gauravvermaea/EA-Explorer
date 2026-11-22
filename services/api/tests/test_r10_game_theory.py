"""Release 10 (R10.2, R10.3; D857 (4), (5)): the working of games and of options across futures, done by EA Explorer's
own code (eax/game_theory.py), never guessed by the AI. Checked against games whose answers are known."""

from __future__ import annotations

import pytest

from eax import game_theory as g


def _table(players, opts, values):
    return {"players": players, "options": dict(zip(players, opts, strict=True)),
            "payoffs": [{"options": dict(zip(players, k, strict=True)), "values": dict(zip(players, v, strict=True))}
                        for k, v in values.items()]}


PD = _table(["Us", "Rival"], [["Cut", "Hold"], ["Cut", "Hold"]],
            {("Cut", "Cut"): (1, 1), ("Cut", "Hold"): (5, 0), ("Hold", "Cut"): (0, 5), ("Hold", "Hold"): (3, 3)})


def test_the_prisoners_dilemma_dominant_stable_and_agreeing_helps():
    r = g.normal_form(PD)
    assert r["dominant"] == {"Us": {"strict": "Cut", "weak": None}, "Rival": {"strict": "Cut", "weak": None}}
    assert r["stable"] == [{"Us": "Cut", "Rival": "Cut"}]
    assert {"Us": "Hold", "Rival": "Hold"} in r["pareto"] and {"Us": "Cut", "Rival": "Cut"} not in r["pareto"]
    assert r["agreeing_helps"][0]["better_for_all"] == [{"Us": "Hold", "Rival": "Hold"}]
    assert any("better by agreeing" in s for s in r["in_words"])
    # best replies: whatever the rival does, Us replies Cut
    assert all(b["best"] == ["Cut"] for b in r["best_replies"]["Us"])


def test_matching_pennies_has_only_a_mixed_equilibrium_at_a_half():
    mp = _table(["A", "B"], [["H", "T"], ["H", "T"]],
                {("H", "H"): (1, -1), ("H", "T"): (-1, 1), ("T", "H"): (-1, 1), ("T", "T"): (1, -1)})
    r = g.normal_form(mp)
    assert r["stable"] == []
    eq = r["mixed"]["equilibria"]
    assert len(eq) == 1 and not eq[0]["pure"]
    assert eq[0]["fractions"] == {"A": {"H": "1/2", "T": "1/2"}, "B": {"H": "1/2", "T": "1/2"}}
    assert eq[0]["expect"] == {"A": 0.0, "B": 0.0}


def test_the_battle_of_the_sexes_two_pure_and_one_mixed_exactly():
    bs = _table(["A", "B"], [["X", "Y"], ["X", "Y"]],
                {("X", "X"): (2, 1), ("X", "Y"): (0, 0), ("Y", "X"): (0, 0), ("Y", "Y"): (1, 2)})
    eq = g.normal_form(bs)["mixed"]["equilibria"]
    assert sum(e["pure"] for e in eq) == 2
    mixed = next(e for e in eq if not e["pure"])
    assert mixed["fractions"] == {"A": {"X": "2/3", "Y": "1/3"}, "B": {"X": "1/3", "Y": "2/3"}}


def test_three_players_work_without_mixed_strategies():
    vals = {(a, b, c): (int(a == "L"), int(b == "L"), int(c == "L")) for a in "LR" for b in "LR" for c in "LR"}
    r = g.normal_form(_table(["A", "B", "C"], [["L", "R"]] * 3, vals))
    assert r["stable"] == [{"A": "L", "B": "L", "C": "L"}] and r["mixed"] is None


def test_an_entry_game_worked_back_from_the_end_and_ties_said():
    t = {"kind": "sequential", "players": ["Us", "Rival"], "tree": {"player": "Us", "choices": [
        {"option": "Enter", "then": {"player": "Rival", "choices": [
            {"option": "Fight", "then": {"values": {"Us": -1, "Rival": -1}}},
            {"option": "Share", "then": {"values": {"Us": 1, "Rival": 1}}}]}},
        {"option": "Stay out", "then": {"values": {"Us": 0, "Rival": 2}}}]}}
    r = g.work_out(t)
    assert r["path"] == ["Us: Enter", "Rival: Share"] and r["outcome"] == {"Us": 1.0, "Rival": 1.0}
    assert {"after": ["Us: Enter"], "player": "Rival", "chooses": "Share", "gets": 1.0} in r["plan"]
    t["tree"]["choices"][1]["then"]["values"]["Us"] = 1          # now Us is indifferent at the start
    assert any("indifferent" in x for x in g.work_out(t)["ties"])


def test_options_across_futures_robust_least_regret_dominated_and_one_win():
    opts, futs = ["Build", "Buy", "Wait"], ["Slow", "Fast"]
    vals = {("Build", "Slow"): 5, ("Build", "Fast"): -2, ("Buy", "Slow"): 2, ("Buy", "Fast"): 3,
            ("Wait", "Slow"): 1, ("Wait", "Fast"): 1}
    r = g.robustness(opts, futs, [{"option": o, "future": f, "value": v} for (o, f), v in vals.items()])
    assert r["robust"] == ["Buy"] and r["least_regret"] == ["Buy"]
    assert {"option": "Wait", "by": "Buy"} in r["dominated"]
    assert r["only_wins_in_one"] == [{"option": "Build", "future": "Slow"}]
    assert r["best_in_each"] == {"Slow": ["Build"], "Fast": ["Buy"]}


def test_values_in_any_form():
    assert g.numbers([{"money": 10}, {"money": 30}])[0] == [10, 30]
    nums, how = g.numbers([{"words": "much better", "score": 2}, 0, {"money": 100}, {"money": 300}])
    assert nums[0] == 2 and nums[1] == 0 and nums[2] == 0 and nums[3] == 2 and "scaled" in how
    with pytest.raises(g.GameError, match="score the person agreed"):
        g.value_of({"words": "better"})
    with pytest.raises(g.GameError, match="more than one currency"):
        g.numbers([{"money": 1, "currency": "ZAR"}, {"money": 2, "currency": "USD"}])
    with pytest.raises(g.GameError):
        g.value_of(True)


def test_games_that_do_not_hold_together_are_said_in_words():
    bad = dict(PD, payoffs=PD["payoffs"][:3])
    with pytest.raises(g.GameError, match="no values"):
        g.normal_form(bad)
    with pytest.raises(g.GameError, match="2 to"):
        g.normal_form({"players": ["Solo"], "options": {"Solo": ["A"]}, "payoffs": []})
    with pytest.raises(g.GameError, match="kind"):
        g.work_out({"kind": "poker"})
    with pytest.raises(g.GameError, match="missing"):
        g.robustness(["A"], ["F"], [])
