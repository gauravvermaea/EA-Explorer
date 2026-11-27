"""Monte Carlo simulation, the engine (Release 14.7, R14.7.1; D957).

Pure code, no database and no AI, like eax/game_theory.py: EA Explorer works the figures out itself and shows how
(D857 (4)). Every uncertain number is a range of three numbers a person can give (low, most likely, high) or an event
that happens with a chance; a plan or a sum is played thousands of times, each time drawing every number from its
range, and the results are counted: how likely a date or an amount is met, the percentiles, what drives the result.

* **shapes** (D957 (4)): PERT (the default; a Beta curve through the three numbers, weighted to the most likely) and
  triangular (straight lines); an **event** (yes or no, with a chance; its impact a range): a risk in the year, a
  regulator's delay. Log-normal and the rest wait.
* **moving together** (D957 (5)): inputs in a named group (a supplier, a currency) are drawn together, by a strength
  (weak, medium, strong); everything else is independent. Each member keeps its own range exactly (its draws are only
  put in another order, the Iman-Conover way, from a shared normal score).
* **the same answer every time**: a fixed seed; each input draws from its own stream (named by the seed and the input),
  so the order inputs are given in changes nothing; the digest names the inputs, the seed and the runs.
* **uses** (D957 (1)): a sum (costs, a year's losses: total), benefits less costs (net), a network of work packages
  (schedule: each starts when all before it have ended; the share of runs each is on the critical path), and the
  chance each option scores highest across futures (best).

Checked against known answers in tests/test_r14_7_monte_carlo_engine.py (MC-E01 to MC-E40).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

SHAPES = ("pert", "triangular")
STRENGTHS = {"weak": 0.45, "medium": 0.75, "strong": 0.92}   # the shared score's weight in each member's order
MAX_RUNS = 100_000
DEFAULT_RUNS = 10_000
MAX_INPUTS = 500


class Range:
    """A three-point estimate: low <= likely <= high, drawn as PERT (the default) or triangular."""

    def __init__(self, low: float, likely: float, high: float, shape: str = "pert") -> None:
        """Checks the numbers are in order and the shape is known (ValueError otherwise)."""
        try:
            low, likely, high = float(low), float(likely), float(high)
        except (TypeError, ValueError) as exc:
            raise ValueError("low, likely and high are numbers") from exc
        if not (math.isfinite(low) and math.isfinite(likely) and math.isfinite(high)):
            raise ValueError("low, likely and high are numbers")
        if not low <= likely <= high:
            raise ValueError(f"a range runs low <= likely <= high: {low:g}, {likely:g}, {high:g}")
        if shape not in SHAPES:
            raise ValueError(f"a shape is one of {', '.join(SHAPES)}, not {shape!r}")
        self.low, self.likely, self.high, self.shape = low, likely, high, shape

    def one(self, rng: random.Random) -> float:
        """One draw."""
        a, m, b = self.low, self.likely, self.high
        if a == b:
            return a
        if self.shape == "triangular":
            return rng.triangular(a, b, m)
        alpha = 1 + 4 * (m - a) / (b - a)
        beta = 1 + 4 * (b - m) / (b - a)
        return a + (b - a) * rng.betavariate(alpha, beta)

    def mean(self) -> float:
        """The range's own mean (PERT: (a + 4m + b) / 6; triangular: (a + m + b) / 3)."""
        a, m, b = self.low, self.likely, self.high
        return (a + 4 * m + b) / 6 if self.shape == "pert" else (a + m + b) / 3

    def key(self) -> list:
        """What the range is, for the digest."""
        return ["range", self.low, self.likely, self.high, self.shape]

    def __repr__(self) -> str:
        """Range(low, likely, high, shape)."""
        return f"Range({self.low:g}, {self.likely:g}, {self.high:g}, {self.shape!r})"


class Event:
    """Something that happens in a run with a chance (0 to 1); when it does, its impact is drawn from a range."""

    def __init__(self, chance: float, impact: Range) -> None:
        """Checks the chance is 0 to 1 and the impact is a Range (ValueError otherwise)."""
        try:
            chance = float(chance)
        except (TypeError, ValueError) as exc:
            raise ValueError("a chance is a number from 0 to 1") from exc
        if not 0 <= chance <= 1:
            raise ValueError(f"a chance is from 0 to 1, not {chance:g}")
        if not isinstance(impact, Range):
            raise ValueError("an event's impact is a range")
        self.chance, self.impact = chance, impact

    def one(self, rng: random.Random) -> float:
        """One draw: 0 when it does not happen, else its impact."""
        return self.impact.one(rng) if rng.random() < self.chance else 0.0

    def mean(self) -> float:
        """The chance times the impact's mean."""
        return self.chance * self.impact.mean()

    def key(self) -> list:
        """What the event is, for the digest."""
        return ["event", self.chance, self.impact.key()]


class Group:
    """Inputs that move together (a supplier's work packages, the costs in one currency), by a strength."""

    def __init__(self, name: str, members: Iterable[str], strength: str = "medium") -> None:
        """Checks the strength is known and there are members (ValueError otherwise)."""
        if strength not in STRENGTHS:
            raise ValueError(f"a strength is one of {', '.join(STRENGTHS)}, not {strength!r}")
        self.name, self.members, self.strength = str(name), [str(m) for m in members], strength
        if not self.members:
            raise ValueError(f"group {self.name} has no members")

    def key(self) -> list:
        """What the group is, for the digest."""
        return [self.name, sorted(self.members), self.strength]


Input = Range | Event


@dataclass
class Result:
    """The runs of one simulation: the results sorted, each input's draws in run order, and what drives the result."""

    values: list[float]
    inputs: dict[str, list[float]]
    digest: str
    runs: int
    seed: int
    critical: dict[str, float] = field(default_factory=dict)
    drivers: list[tuple[str, float]] = field(default_factory=list)

    @property
    def mean(self) -> float:
        """The mean of the results."""
        return statistics.fmean(self.values)

    def percentile(self, q: float) -> float:
        """The result at or below which q percent of the runs fall (nearest rank)."""
        n = len(self.values)
        k = min(n - 1, max(0, math.ceil(q / 100 * n) - 1))
        return self.values[k]

    def chance_at_most(self, x: float) -> float:
        """The share of runs whose result is x or less (a date or an amount met)."""
        return _count_at_most(self.values, x) / len(self.values)

    def chance_above(self, x: float) -> float:
        """The share of runs whose result is more than x."""
        return 1 - self.chance_at_most(x)

    def histogram(self, bins: int = 20) -> list[dict]:
        """The results in equal bins: [{from, to, runs}]."""
        lo, hi = self.values[0], self.values[-1]
        if lo == hi:
            return [{"from": lo, "to": hi, "runs": len(self.values)}]
        width = (hi - lo) / bins
        counts = [0] * bins
        for v in self.values:
            counts[min(bins - 1, int((v - lo) / width))] += 1
        return [{"from": lo + i * width, "to": lo + (i + 1) * width, "runs": c} for i, c in enumerate(counts)]

    def s_curve(self, points: int = 21) -> list[dict]:
        """The chance of meeting each result, from the lowest to the highest: [{value, chance}]."""
        return [{"value": self.percentile(100 * i / (points - 1)) if i else self.values[0], "chance": i / (points - 1)}
                for i in range(points)]

    def summary(self) -> dict:
        """What a screen, a report or the AI reads: the percentiles, the mean, the extremes, the drivers, the curve."""
        out = {"runs": self.runs, "seed": self.seed, "digest": self.digest, "mean": self.mean,
               "low": self.values[0], "high": self.values[-1],
               "p10": self.percentile(10), "p50": self.percentile(50), "p80": self.percentile(80), "p90": self.percentile(90),
               "drivers": [{"input": n, "strength": r} for n, r in self.drivers],
               "histogram": self.histogram(), "s_curve": self.s_curve()}
        if self.critical:
            out["critical"] = dict(sorted(self.critical.items(), key=lambda kv: -kv[1]))
        return out


def _count_at_most(sorted_values: list[float], x: float) -> int:
    """How many of the sorted values are x or less (binary search)."""
    lo, hi = 0, len(sorted_values)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_values[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _runs_ok(runs: Any) -> int:
    try:
        n = int(runs)
    except (TypeError, ValueError) as exc:
        raise ValueError("runs is a whole number") from exc
    if not 1 <= n <= MAX_RUNS:
        raise ValueError(f"runs is 1 to {MAX_RUNS:,}")
    return n


def _stream(seed: int, *names: str) -> random.Random:
    """An input's own random stream: the same seed and name always give the same draws."""
    h = hashlib.sha256(":".join([str(seed), *names]).encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def draw(x: Input, runs: int, seed: int) -> list[float]:
    """One input drawn on its own, `runs` times."""
    n = _runs_ok(runs)
    rng = _stream(seed, "draw")
    return [x.one(rng) for _ in range(n)]


def _check(inputs: Mapping[str, Input], groups: Iterable[Group]) -> list[Group]:
    if not inputs:
        raise ValueError("there is nothing to simulate: give at least one input")
    if len(inputs) > MAX_INPUTS:
        raise ValueError(f"at most {MAX_INPUTS} inputs")
    for name, x in inputs.items():
        if not isinstance(x, Range | Event):
            raise ValueError(f"{name} is not a range or an event")
    groups = list(groups or ())
    seen: dict[str, str] = {}
    for g in groups:
        for m in g.members:
            if m not in inputs:
                raise ValueError(f"group {g.name} names {m}, which is not one of the inputs")
            if m in seen:
                raise ValueError(f"{m} is in two groups ({seen[m]} and {g.name})")
            seen[m] = g.name
    return groups


def _sample(inputs: Mapping[str, Input], runs: int, seed: int, groups: Iterable[Group]) -> dict[str, list[float]]:
    """Every input's draws in run order; a group's members reordered to move together."""
    n = _runs_ok(runs)
    groups = _check(inputs, groups)
    out: dict[str, list[float]] = {}
    for name in sorted(inputs):
        rng = _stream(seed, "input", name)
        out[name] = [inputs[name].one(rng) for _ in range(n)]
    for g in groups:
        shared_rng = _stream(seed, "group", g.name)
        shared = [shared_rng.gauss(0, 1) for _ in range(n)]
        w = STRENGTHS[g.strength]
        rest = math.sqrt(1 - w * w)
        for m in g.members:
            own = _stream(seed, "group", g.name, m)
            score = [w * shared[i] + rest * own.gauss(0, 1) for i in range(n)]
            order = sorted(range(n), key=score.__getitem__)
            ranked = sorted(out[m])
            moved = [0.0] * n
            for rank, i in enumerate(order):
                moved[i] = ranked[rank]
            out[m] = moved
    return out


def _digest(kind: str, inputs: Mapping[str, Input], seed: int, runs: int, groups: Iterable[Group], extra: Any = None) -> str:
    body = {"kind": kind, "inputs": {k: inputs[k].key() for k in sorted(inputs)}, "seed": seed, "runs": runs,
            "groups": sorted(g.key() for g in groups or ()), "extra": extra}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _drivers(ins: Mapping[str, list[float]], totals: list[float]) -> list[tuple[str, float]]:
    """Each input's correlation with the result (0 when either does not vary), the strongest first (the tornado)."""
    out = []
    total_varies = statistics.pstdev(totals) > 0
    for k in sorted(ins):
        xs = ins[k]
        r = statistics.correlation(xs, totals) if total_varies and statistics.pstdev(xs) > 0 else 0.0
        out.append((k, round(abs(r), 6)))
    return sorted(out, key=lambda kv: (-kv[1], kv[0]))


def total(inputs: Mapping[str, Input], runs: int = DEFAULT_RUNS, seed: int = 1, groups: Iterable[Group] = ()) -> Result:
    """The sum of the inputs in each run: a cost, a duration, a year's losses."""
    ins = _sample(inputs, runs, seed, groups)
    n = len(next(iter(ins.values())))
    sums = [math.fsum(ins[k][i] for k in ins) for i in range(n)]
    return Result(sorted(sums), ins, _digest("total", inputs, seed, n, groups), n, seed, drivers=_drivers(ins, sums))


def net(benefits: Mapping[str, Input], costs: Mapping[str, Input], runs: int = DEFAULT_RUNS, seed: int = 1,
        groups: Iterable[Group] = ()) -> Result:
    """Benefits less costs in each run: an option's business case."""
    both = set(benefits) & set(costs)
    if both:
        raise ValueError(f"{', '.join(sorted(both))} is both a benefit and a cost")
    every = {**benefits, **costs}
    ins = _sample(every, runs, seed, groups)
    n = len(next(iter(ins.values())))
    nets = [math.fsum(ins[k][i] for k in benefits) - math.fsum(ins[k][i] for k in costs) for i in range(n)]
    return Result(sorted(nets), ins, _digest("net", every, seed, n, groups, sorted(costs)), n, seed,
                  drivers=_drivers(ins, nets))


def order_of(packages: Mapping[str, Input], after: Mapping[str, Iterable[str]]) -> list[str]:
    """The work packages in an order where each comes after those it waits for (ValueError on a loop or an unknown one)."""
    for k, before in after.items():
        if k not in packages:
            raise ValueError(f"{k} waits for others but is not one of the work packages")
        for b in before:
            if b not in packages:
                raise ValueError(f"{k} waits for {b}, which is not one of the work packages")
    state: dict[str, int] = {}
    order: list[str] = []
    for start in sorted(packages):
        if state.get(start):
            continue
        stack = [(start, iter(sorted(after.get(start, ()))))]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                state[node] = 2
                order.append(node)
            elif state.get(nxt) == 1:
                raise ValueError(f"a dependency loop: {nxt} waits, through others, for itself")
            elif not state.get(nxt):
                state[nxt] = 1
                stack.append((nxt, iter(sorted(after.get(nxt, ())))))
    return order


def schedule(packages: Mapping[str, Input], after: Mapping[str, Iterable[str]], runs: int = DEFAULT_RUNS, seed: int = 1,
             groups: Iterable[Group] = ()) -> Result:
    """A network of work packages, each a duration: each starts when all it waits for have ended. The result is when the
    last one ends (from the start, in the durations' unit); critical is the share of runs each was on the longest path."""
    after = {k: list(v) for k, v in (after or {}).items()}
    order = order_of(packages, after)
    ins = _sample(packages, runs, seed, groups)
    n = len(next(iter(ins.values())))
    on_path = {k: 0 for k in packages}
    ends = []
    for i in range(n):
        finish: dict[str, float] = {}
        before: dict[str, str | None] = {}
        for k in order:
            start, prev = 0.0, None
            for b in after.get(k, ()):
                if finish[b] > start:
                    start, prev = finish[b], b
            finish[k] = start + ins[k][i]
            before[k] = prev
        last = max(order, key=lambda k: (finish[k], k))
        ends.append(finish[last])
        k = last
        while k is not None:
            on_path[k] += 1
            k = before[k]
    return Result(sorted(ends), ins, _digest("schedule", packages, seed, n, groups, sorted((k, sorted(v)) for k, v in after.items())),
                  n, seed, critical={k: c / n for k, c in on_path.items()}, drivers=_drivers(ins, ends))


def best(scores: Mapping[str, Mapping[str, Input]], runs: int = DEFAULT_RUNS, seed: int = 1,
         weights: Mapping[str, float] | None = None) -> dict[str, float]:
    """Each option's chance of scoring highest. scores {option: {future: score}}. With weights {future: chance}, each run
    first draws the future by its weight and compares the options there; without, the options' scores summed over the
    futures are compared. A tie shares the run."""
    n = _runs_ok(runs)
    if not scores:
        raise ValueError("give at least one option")
    futures = sorted(next(iter(scores.values())))
    for o, by in scores.items():
        if sorted(by) != futures:
            raise ValueError(f"option {o} needs a score in every future ({', '.join(futures)})")
    if weights is not None:
        if sorted(weights) != futures:
            raise ValueError(f"give a weight for every future ({', '.join(futures)})")
        if any(w < 0 for w in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("the weights are 0 or more and not all 0")
    rng = _stream(seed, "best")
    wins = dict.fromkeys(scores, 0.0)
    w = [weights[f] for f in futures] if weights else None
    for _ in range(n):
        if w:
            f = rng.choices(futures, w)[0]
            got = {o: scores[o][f].one(rng) for o in sorted(scores)}
        else:
            got = {o: math.fsum(scores[o][f].one(rng) for f in futures) for o in sorted(scores)}
        top = max(got.values())
        winners = [o for o, v in got.items() if v == top]
        for o in winners:
            wins[o] += 1 / len(winners)
    return {o: wins[o] / n for o in scores}
