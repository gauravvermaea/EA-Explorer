"""Release 14.7: the Monte Carlo engine's refusals and small parts (D962), beside the known answers of
test_r14_7_monte_carlo_engine.py: what it refuses is said in words, and the summary a screen reads is whole."""

from __future__ import annotations

import pytest

from eax import monte_carlo as mc


@pytest.mark.parametrize("args,why", [(("a", 1, 2), "are numbers"), ((1, float("inf"), 2), "are numbers"),
                                      ((None, 1, 2), "are numbers")])
def test_a_range_of_something_else_is_refused(args, why):
    with pytest.raises(ValueError, match=why):
        mc.Range(*args)


def test_an_event_and_a_group_out_of_shape_are_refused():
    with pytest.raises(ValueError, match="a number from 0 to 1"):
        mc.Event("often", mc.Range(1, 2, 3))
    with pytest.raises(ValueError, match="impact is a range"):
        mc.Event(0.5, (1, 2, 3))
    with pytest.raises(ValueError, match="no members"):
        mc.Group("empty", [])


def test_the_means_and_the_names():
    assert mc.Range(2, 5, 14).mean() == 6 and mc.Range(2, 5, 14, "triangular").mean() == 7
    assert mc.Event(0.5, mc.Range(2, 5, 14)).mean() == 3
    assert repr(mc.Range(1, 2, 3)) == "Range(1, 2, 3, 'pert')"


def test_what_a_simulation_refuses():
    r = mc.Range(1, 2, 3)
    for fn, why in ((lambda: mc.draw(r, "many", 1), "whole number"), (lambda: mc.total({}, 10, 1), "nothing to simulate"),
                    (lambda: mc.total({str(i): r for i in range(mc.MAX_INPUTS + 1)}, 10, 1), "at most"),
                    (lambda: mc.total({"a": (1, 2, 3)}, 10, 1), "not a range or an event"),
                    (lambda: mc.total({"a": r, "b": r, "c": r}, 10, 1, [mc.Group("g", ["a", "b"]), mc.Group("h", ["b", "c"])]),
                     "in two groups"),
                    (lambda: mc.net({"a": r}, {"a": r}, 10, 1), "both a benefit and a cost"),
                    (lambda: mc.schedule({"a": r}, {"z": ["a"]}, 10, 1), "z waits for others"),
                    (lambda: mc.best({}, 10, 1), "at least one option"),
                    (lambda: mc.best({"A": {"F1": r}, "B": {"F2": r}}, 10, 1), "every future"),
                    (lambda: mc.best({"A": {"F1": r}}, 10, 1, {"F2": 1}), "every future"),
                    (lambda: mc.best({"A": {"F1": r}}, 10, 1, {"F1": 0}), "not all 0")):
        with pytest.raises(ValueError, match=why):
            fn()


def test_the_summary_a_screen_reads():
    s = mc.schedule({"A": mc.Range(1, 2, 4), "B": mc.Range(1, 1, 1)}, {"B": ["A"]}, 500, 3).summary()
    assert {"runs", "seed", "digest", "mean", "low", "high", "p10", "p50", "p80", "p90", "drivers", "histogram", "s_curve",
            "critical"} <= set(s)
    assert sum(b["runs"] for b in s["histogram"]) == 500 and len(s["s_curve"]) == 21
    flat = mc.total({"a": mc.Range(5, 5, 5)}, 50, 1)
    assert flat.histogram() == [{"from": 5, "to": 5, "runs": 50}] and "critical" not in flat.summary()
