"""Release 14.7: the Monte Carlo engine's test cases, written before the engine (owner, 27 Nov 2026, 15:34: "write test
cases for monte carlo"; D957). Every case is a known answer: a formula, a limit or a case with only one possible result,
so the engine is checked against arithmetic, never against itself. Skipped until eax/monte_carlo.py exists; then each
must pass. The cases and the engine's interface they assume: docs/release-14.7-test-cases.md (MC-E01 to MC-E40).

The interface assumed (pure code like eax/game_theory.py: no database, no AI):
  Range(low, likely, high, shape="pert" | "triangular")      a three-point estimate
  Event(chance, impact: Range)                               happens in a run with the chance; then draws its impact
  Group(name, members, strength="weak" | "medium" | "strong") inputs that move together (D957 (5))
  draw(x, runs, seed) -> list[float]                         one input on its own
  total(inputs, runs, seed, groups=()) -> Result             a sum (costs, a year's losses)
  net(benefits, costs, runs, seed, groups=()) -> Result      benefits less costs (an option's business case)
  schedule(packages, after, runs, seed, groups=()) -> Result the end of a network of work packages
  best(scores, runs, seed, weights=None) -> dict             each option's chance of scoring highest
  Result: values (sorted), mean, percentile(p), chance_at_most(x), chance_above(x), drivers [(name, r)],
          inputs {name: each run's draw, in run order}, critical {package: share of runs on the critical path}
          (schedule only), digest (of the inputs, seed and runs)
"""

from __future__ import annotations

import math
import statistics
import time

import pytest

mc = pytest.importorskip("eax.monte_carlo", reason="Release 14.7's engine is not built yet (R14.7.1)")

N = 20_000          # enough runs for the tolerances below: 4 standard errors, so a correct engine fails 1 in ~15,000


def _se(sd: float, runs: int = N) -> float:
    """Four standard errors of a mean of `runs` draws."""
    return 4 * sd / math.sqrt(runs)


# ---------------------------------------------------------------- the shapes (MC-E01 to MC-E09)

def test_mc_e01_pert_mean_and_spread():
    # Beta-PERT: mean (a + 4m + b) / 6; variance (mean - a)(b - mean) / 7
    a, m, b = 2.0, 5.0, 14.0
    mean = (a + 4 * m + b) / 6                                         # 6.0
    sd = math.sqrt((mean - a) * (b - mean) / 7)                        # 2.138
    xs = mc.draw(mc.Range(a, m, b), N, seed=1)
    assert abs(statistics.fmean(xs) - mean) < _se(sd)
    assert abs(statistics.stdev(xs) - sd) < 0.05 * sd


def test_mc_e02_triangular_mean_and_spread():
    a, m, b = 2.0, 5.0, 14.0
    mean = (a + m + b) / 3                                             # 7.0
    sd = math.sqrt((a * a + m * m + b * b - a * m - a * b - m * b) / 18)
    xs = mc.draw(mc.Range(a, m, b, shape="triangular"), N, seed=1)
    assert abs(statistics.fmean(xs) - mean) < _se(sd)
    assert abs(statistics.stdev(xs) - sd) < 0.05 * sd


def test_mc_e03_pert_is_the_default_and_narrower_than_triangular():
    r = mc.Range(2, 5, 14)
    assert r.shape == "pert"
    assert statistics.stdev(mc.draw(r, N, seed=2)) < statistics.stdev(mc.draw(mc.Range(2, 5, 14, shape="triangular"), N, seed=2))


@pytest.mark.parametrize("shape", ["pert", "triangular"])
def test_mc_e04_every_draw_lies_within_the_range(shape):
    xs = mc.draw(mc.Range(3, 4, 9, shape=shape), N, seed=3)
    assert min(xs) >= 3 and max(xs) <= 9


@pytest.mark.parametrize("shape", ["pert", "triangular"])
def test_mc_e05_a_range_of_one_number_always_gives_that_number(shape):
    assert set(mc.draw(mc.Range(7, 7, 7, shape=shape), 1_000, seed=4)) == {7}


def test_mc_e06_a_skewed_range_has_its_median_toward_the_likely_end():
    xs = sorted(mc.draw(mc.Range(0, 1, 10), N, seed=5))
    assert xs[N // 2] < (0 + 10) / 2 and statistics.fmean(xs) > xs[N // 2]     # long tail to the right


def test_mc_e07_an_event_happens_in_its_share_of_runs():
    p = 0.3
    xs = mc.draw(mc.Event(p, mc.Range(100, 100, 100)), N, seed=6)
    happened = sum(1 for x in xs if x > 0) / N
    assert abs(happened - p) < 4 * math.sqrt(p * (1 - p) / N)
    assert set(xs) <= {0, 100}


@pytest.mark.parametrize("p,expected", [(0.0, {0}), (1.0, {100})])
def test_mc_e08_an_event_of_chance_nought_or_one(p, expected):
    assert set(mc.draw(mc.Event(p, mc.Range(100, 100, 100)), 1_000, seed=7)) == expected


def test_mc_e09_an_events_mean_is_its_chance_times_its_impacts_mean():
    p, a, m, b = 0.2, 10, 20, 60
    impact = (a + 4 * m + b) / 6
    xs = mc.draw(mc.Event(p, mc.Range(a, m, b)), N, seed=8)
    assert abs(statistics.fmean(xs) - p * impact) < _se(statistics.stdev(xs))


# ---------------------------------------------------------------- inputs refused (MC-E10 to MC-E14)

@pytest.mark.parametrize("low,likely,high", [(5, 4, 9), (1, 10, 9), (9, 5, 1)])
def test_mc_e10_a_range_out_of_order_is_refused(low, likely, high):
    with pytest.raises(ValueError):
        mc.Range(low, likely, high)


@pytest.mark.parametrize("p", [-0.1, 1.1])
def test_mc_e11_a_chance_outside_nought_to_one_is_refused(p):
    with pytest.raises(ValueError):
        mc.Event(p, mc.Range(1, 2, 3))


def test_mc_e12_an_unknown_shape_strength_or_run_count_is_refused():
    with pytest.raises(ValueError):
        mc.Range(1, 2, 3, shape="lognormal")                           # waits (D957 (4))
    with pytest.raises(ValueError):
        mc.Group("g", ["a", "b"], strength="total")
    with pytest.raises(ValueError):
        mc.total({"a": mc.Range(1, 2, 3)}, 0, seed=1)


def test_mc_e13_a_dependency_loop_or_an_unknown_package_is_refused():
    packages = {"A": mc.Range(1, 1, 1), "B": mc.Range(1, 1, 1)}
    with pytest.raises(ValueError, match="(?i)loop|cycle"):
        mc.schedule(packages, {"A": ["B"], "B": ["A"]}, 100, seed=1)
    with pytest.raises(ValueError, match="C"):
        mc.schedule(packages, {"A": ["C"]}, 100, seed=1)


def test_mc_e14_a_group_naming_an_input_that_is_not_there_is_refused():
    with pytest.raises(ValueError, match="z"):
        mc.total({"a": mc.Range(1, 2, 3)}, 100, seed=1, groups=[mc.Group("g", ["a", "z"])])


# ---------------------------------------------------------------- the same answer every time (MC-E15 to MC-E17)

def test_mc_e15_the_same_inputs_and_seed_give_the_same_answer():
    inputs = {"a": mc.Range(1, 2, 9), "b": mc.Event(0.4, mc.Range(5, 6, 20))}
    one, two = mc.total(inputs, 5_000, seed=42), mc.total(inputs, 5_000, seed=42)
    assert one.values == two.values and one.digest == two.digest


def test_mc_e16_another_seed_gives_other_draws_but_the_same_picture():
    inputs = {"a": mc.Range(1, 2, 9)}
    one, two = mc.total(inputs, N, seed=1), mc.total(inputs, N, seed=2)
    assert one.values != two.values and one.digest != two.digest
    assert abs(one.mean - two.mean) < 2 * _se(statistics.stdev(one.values))


def test_mc_e17_the_order_inputs_are_given_in_does_not_change_the_answer():
    a, b = mc.Range(1, 2, 9), mc.Range(3, 3, 4)
    assert mc.total({"a": a, "b": b}, 2_000, seed=9).values == mc.total({"b": b, "a": a}, 2_000, seed=9).values


# ---------------------------------------------------------------- the results (MC-E18 to MC-E23)

def test_mc_e18_percentiles_rise_and_bracket_the_runs():
    r = mc.total({"a": mc.Range(1, 3, 20)}, N, seed=10)
    p = [r.percentile(q) for q in (10, 50, 80, 90)]
    assert p == sorted(p) and r.values[0] <= p[0] and p[-1] <= r.values[-1]


def test_mc_e19_a_certain_total_has_every_percentile_equal():
    r = mc.total({"a": mc.Range(4, 4, 4), "b": mc.Range(6, 6, 6)}, 1_000, seed=11)
    assert {r.percentile(q) for q in (10, 50, 80, 90)} == {10} and r.mean == 10


def test_mc_e20_the_chance_of_meeting_a_figure():
    r = mc.total({"a": mc.Range(10, 10, 10)}, 1_000, seed=12)
    assert r.chance_at_most(10) == 1.0 and r.chance_at_most(9.99) == 0.0 and r.chance_above(10) == 0.0
    s = mc.total({"a": mc.Range(0, 5, 10, shape="triangular")}, N, seed=12)  # symmetrical: half at or below 5
    assert abs(s.chance_at_most(5) - 0.5) < 4 * math.sqrt(0.25 / N)
    assert s.chance_at_most(5) + s.chance_above(5) == pytest.approx(1.0)


def test_mc_e21_a_sum_of_independent_ranges_adds_means_and_variances():
    parts = [(2, 5, 14), (1, 1, 7), (10, 12, 20)]
    mean = sum((a + 4 * m + b) / 6 for a, m, b in parts)
    var = sum(((a + 4 * m + b) / 6 - a) * (b - (a + 4 * m + b) / 6) / 7 for a, m, b in parts)
    r = mc.total({f"p{i}": mc.Range(*p) for i, p in enumerate(parts)}, N, seed=13)
    assert abs(r.mean - mean) < _se(math.sqrt(var))
    assert abs(statistics.stdev(r.values) - math.sqrt(var)) < 0.05 * math.sqrt(var)


def test_mc_e22_the_sum_of_most_likely_values_is_beaten_more_often_than_not():
    # the reason for the release: three right-skewed estimates added at their most likely values
    parts = {"migration": mc.Range(4, 6, 12), "integration": mc.Range(3, 5, 8), "testing": mc.Range(2, 3, 6)}
    r = mc.total(parts, N, seed=14)
    assert r.chance_at_most(6 + 5 + 3) < 0.5


def test_mc_e23_the_input_with_the_widest_range_drives_the_result_most():
    r = mc.total({"narrow": mc.Range(9, 10, 11), "wide": mc.Range(0, 10, 60), "fixed": mc.Range(5, 5, 5)}, N, seed=15)
    names = [n for n, _r in r.drivers]
    assert names[0] == "wide" and names[-1] == "fixed"
    assert dict(r.drivers)["fixed"] == 0 and 0 < dict(r.drivers)["narrow"] < dict(r.drivers)["wide"] <= 1


# ---------------------------------------------------------------- moving together (MC-E24 to MC-E27)

def _corr(xs: list[float], ys: list[float]) -> float:
    return statistics.correlation(xs, ys)


def test_mc_e24_inputs_in_no_group_are_independent():
    r = mc.total({"a": mc.Range(1, 5, 9), "b": mc.Range(1, 5, 9)}, N, seed=16)
    assert abs(_corr(r.inputs["a"], r.inputs["b"])) < 0.05


@pytest.mark.parametrize("strength,low", [("weak", 0.15), ("medium", 0.4), ("strong", 0.7)])
def test_mc_e25_a_groups_members_move_together_by_its_strength(strength, low):
    r = mc.total({"a": mc.Range(1, 5, 9), "b": mc.Range(1, 5, 9)}, N, seed=17,
                 groups=[mc.Group("Supplier X", ["a", "b"], strength=strength)])
    assert _corr(r.inputs["a"], r.inputs["b"]) > low


def test_mc_e26_moving_together_widens_the_total_but_keeps_its_mean():
    inputs = {k: mc.Range(1, 5, 15) for k in "abcd"}
    apart = mc.total(inputs, N, seed=18)
    together = mc.total(inputs, N, seed=18, groups=[mc.Group("USD costs", list("abcd"), strength="strong")])
    assert abs(apart.mean - together.mean) < _se(statistics.stdev(together.values))
    assert together.percentile(90) - together.percentile(10) > 1.3 * (apart.percentile(90) - apart.percentile(10))


def test_mc_e27_a_group_keeps_each_members_own_shape():
    r = mc.total({"a": mc.Range(2, 5, 14), "b": mc.Range(100, 100, 100)}, N, seed=19,
                 groups=[mc.Group("g", ["a", "b"], strength="strong")])
    assert abs(statistics.fmean(r.inputs["a"]) - 6.0) < _se(2.138) and set(r.inputs["b"]) == {100}


# ---------------------------------------------------------------- roadmap confidence (MC-E28 to MC-E33)

def test_mc_e28_a_chain_of_certain_packages_ends_at_their_sum():
    r = mc.schedule({"A": mc.Range(3, 3, 3), "B": mc.Range(4, 4, 4), "C": mc.Range(5, 5, 5)},
                    {"B": ["A"], "C": ["B"]}, 500, seed=20)
    assert set(r.values) == {12} and r.critical == {"A": 1.0, "B": 1.0, "C": 1.0}


def test_mc_e29_parallel_packages_end_at_the_longer_path():
    r = mc.schedule({"A": mc.Range(3, 3, 3), "B": mc.Range(7, 7, 7), "C": mc.Range(2, 2, 2)},
                    {"C": ["A", "B"]}, 500, seed=21)
    assert set(r.values) == {9} and r.critical["B"] == 1.0 and r.critical["A"] == 0.0


def test_mc_e30_two_uncertain_paths_end_later_than_either_alone():
    # the merge bias: the expected maximum of two equal paths is above either path's mean
    one = mc.Range(5, 10, 15, shape="triangular")
    r = mc.schedule({"A": one, "B": one}, {}, N, seed=22)
    assert r.mean > 10 + 0.5 and 0.4 < r.critical["A"] < 0.6 and r.critical["A"] + r.critical["B"] == pytest.approx(1.0)


def test_mc_e31_a_package_with_nothing_before_it_starts_at_once():
    r = mc.schedule({"A": mc.Range(2, 2, 2), "B": mc.Range(1, 1, 1)}, {}, 200, seed=23)
    assert set(r.values) == {2}


def test_mc_e32_the_chance_of_a_plateau_by_a_date():
    r = mc.schedule({"A": mc.Range(10, 12, 20), "B": mc.Range(5, 6, 10)}, {"B": ["A"]}, N, seed=24)
    assert r.chance_at_most(15) == 0.0 and r.chance_at_most(30) == 1.0
    assert 0.8 <= r.chance_at_most(r.percentile(80)) < 0.81


def test_mc_e33_ten_thousand_runs_of_two_hundred_packages_in_seconds():
    packages = {f"WP{i}": mc.Range(1, 2, 5) for i in range(200)}
    after = {f"WP{i}": [f"WP{i - 1}", f"WP{i - 7}"] if i >= 7 else ([f"WP{i - 1}"] if i else []) for i in range(200)}
    started = time.perf_counter()
    mc.schedule(packages, after, 10_000, seed=25)
    assert time.perf_counter() - started < 10         # the proposal: a few seconds, fast enough for a page


# ---------------------------------------------------------------- an option's cost and benefit (MC-E34 to MC-E36)

def test_mc_e34_net_value_is_benefits_less_costs():
    r = mc.net({"savings": mc.Range(100, 100, 100)}, {"licences": mc.Range(30, 30, 30), "build": mc.Range(20, 20, 20)},
               500, seed=26)
    assert set(r.values) == {50} and r.chance_above(0) == 1.0


def test_mc_e35_the_chance_an_option_pays_for_itself():
    r = mc.net({"b": mc.Range(0, 10, 20, shape="triangular")}, {"c": mc.Range(10, 10, 10)}, N, seed=27)
    assert abs(r.chance_above(0) - 0.5) < 4 * math.sqrt(0.25 / N)


def test_mc_e36_a_cost_and_a_benefit_that_move_together_narrow_the_net():
    b, c = {"b": mc.Range(50, 100, 150)}, {"c": mc.Range(50, 100, 150)}
    apart = mc.net(b, c, N, seed=28)
    together = mc.net(b, c, N, seed=28, groups=[mc.Group("volume", ["b", "c"], strength="strong")])
    assert together.percentile(90) - together.percentile(10) < apart.percentile(90) - apart.percentile(10)


# ---------------------------------------------------------------- risk exposure (MC-E37 to MC-E38)

def test_mc_e37_a_years_losses_from_events():
    risks = {"outage": mc.Event(0.1, mc.Range(1_000, 1_000, 1_000)), "breach": mc.Event(0.05, mc.Range(5_000, 5_000, 5_000))}
    r = mc.total(risks, N, seed=29)
    assert abs(r.mean - (0.1 * 1_000 + 0.05 * 5_000)) < _se(statistics.stdev(r.values))
    nothing = (1 - 0.1) * (1 - 0.05)                                   # independent: neither happens
    assert abs(r.chance_at_most(0) - nothing) < 4 * math.sqrt(nothing * (1 - nothing) / N)
    assert abs(r.chance_above(5_500) - 0.1 * 0.05) < 4 * math.sqrt(0.005 / N)   # only both together pass 5,500


def test_mc_e38_controls_that_lower_the_chance_lower_every_percentile():
    before = mc.total({"r": mc.Event(0.4, mc.Range(10, 50, 200))}, N, seed=30)
    after = mc.total({"r": mc.Event(0.1, mc.Range(10, 50, 200))}, N, seed=30)
    assert all(after.percentile(q) <= before.percentile(q) for q in (50, 80, 90)) and after.mean < before.mean


# ---------------------------------------------------------------- scenario planning with chances (MC-E39 to MC-E40)

def test_mc_e39_an_option_better_in_every_run_is_best_every_time():
    scores = {"A": {"boom": mc.Range(8, 9, 10), "bust": mc.Range(8, 9, 10)},
              "B": {"boom": mc.Range(1, 2, 3), "bust": mc.Range(1, 2, 3)}}
    assert mc.best(scores, 1_000, seed=31) == {"A": 1.0, "B": 0.0}


def test_mc_e40_the_futures_weights_decide_between_options_that_each_win_one_future():
    scores = {"A": {"boom": mc.Range(10, 10, 10), "bust": mc.Range(0, 0, 0)},
              "B": {"boom": mc.Range(0, 0, 0), "bust": mc.Range(10, 10, 10)}}
    chances = mc.best(scores, N, seed=32, weights={"boom": 0.7, "bust": 0.3})
    assert abs(chances["A"] - 0.7) < 4 * math.sqrt(0.21 / N) and chances["A"] + chances["B"] == pytest.approx(1.0)
