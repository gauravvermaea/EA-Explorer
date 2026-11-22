"""The working of scenario planning and game theory (Release 10, R10.2 and R10.3; D788, D857).

Pure code, no database: EA Explorer works these out itself, never the AI (D857 (4)), and shows the working so a person
can check it.

* **values in any form** (D857 (5)): a number, a score, money or words. Words are given with the score the person agreed
  ({"words": "much better", "score": 2}). In one table the values are compared in their own form when they all share it
  (all money, or all scores); when the forms are mixed, money is scaled onto the scores' range, and `how` says so.
* **games of moves at once** (a payoff table): each player's best replies, dominant options (strict and weak), the stable
  outcomes (pure Nash equilibria), the outcomes nobody can improve without hurting another (Pareto), and where the
  players would all do better by agreeing (a stable outcome another outcome beats for everyone); **mixed strategies** for
  two players (support enumeration, exact fractions).
* **games in turn** (a tree): worked back from the end (backward induction), each player's choice at each point, the path
  played and what each gets, and ties said.
* **options across futures** (R10.3): the best option in each future, the most robust (the best worst case), the least
  regret (the smallest loss against the best choice in each future), options another beats in every future, and those
  that only win in one future.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, product
from typing import Any

MAX_OPTIONS = 8              # a player's options in one game (support enumeration grows fast)
MAX_PLAYERS = 6
MAX_OUTCOMES = 4096
MAX_TREE = 2000              # nodes in a game in turn


class GameError(ValueError):
    """Something in a game or table that cannot be worked out, said in words."""


# ---------------------------------------------------------------- values in any form
def value_of(v: Any) -> dict:
    """One value as given: {"form": "score" | "money" | "words", "score"?, "money"?, "words"?, "currency"?}."""
    if isinstance(v, bool):
        raise GameError("A value is a number, {\"score\": n}, {\"money\": n} or {\"words\": \"...\", \"score\": n}.")
    if isinstance(v, (int, float)):
        return {"form": "score", "score": float(v)}
    if isinstance(v, str):
        try:
            return {"form": "score", "score": float(v.replace(",", "").strip())}
        except ValueError as exc:
            raise GameError(f"'{v}' is in words: give it with the score the person agreed, as "
                            "{\"words\": \"...\", \"score\": n}.") from exc
    if isinstance(v, dict):
        if v.get("money") is not None:
            try:
                return {"form": "money", "money": float(v["money"]), "currency": str(v.get("currency") or "")[:8]}
            except (TypeError, ValueError) as exc:
                raise GameError(f"Money must be a number: {v['money']!r}.") from exc
        if v.get("score") is not None:
            try:
                s = float(v["score"])
            except (TypeError, ValueError) as exc:
                raise GameError(f"A score must be a number: {v['score']!r}.") from exc
            if v.get("words"):
                return {"form": "words", "words": str(v["words"])[:200], "score": s}
            return {"form": "score", "score": s}
        if v.get("words"):
            raise GameError(f"'{v['words']}' needs the score the person agreed: {{\"words\": \"...\", \"score\": n}}.")
    raise GameError(f"Not a value: {v!r}. A value is a number, {{\"score\": n}}, {{\"money\": n}} or "
                    "{\"words\": \"...\", \"score\": n}.")


def numbers(values: list[Any]) -> tuple[list[float], str]:
    """The values of one table as numbers to compare, and how they were compared."""
    vs = [value_of(v) for v in values]
    if not vs:
        return [], "nothing to compare"
    money = [v for v in vs if v["form"] == "money"]
    scored = [v for v in vs if v["form"] != "money"]
    if not money:
        words = sum(1 for v in vs if v["form"] == "words")
        return [v["score"] for v in vs], ("as scores" + (f" ({words} given in words, each with the score agreed)" if words else ""))
    currencies = {v["currency"] for v in money if v["currency"]}
    if len(currencies) > 1:
        raise GameError(f"Money in more than one currency in one table ({', '.join(sorted(currencies))}): give one.")
    if not scored:
        return [v["money"] for v in vs], "as money" + (f" ({currencies.pop()})" if currencies else "")
    lo_m, hi_m = min(v["money"] for v in money), max(v["money"] for v in money)
    lo_s, hi_s = min(v["score"] for v in scored), max(v["score"] for v in scored)
    if hi_s == lo_s:
        lo_s, hi_s = lo_s - 2, lo_s + 2
    out = []
    for v in vs:
        if v["form"] == "money":
            out.append((lo_s + hi_s) / 2 if hi_m == lo_m else lo_s + (v["money"] - lo_m) * (hi_s - lo_s) / (hi_m - lo_m))
        else:
            out.append(v["score"])
    return out, (f"mixed forms: the {len(money)} money value(s) were scaled onto the scores' range ({lo_s:g} to {hi_s:g}), "
                 "the lowest money to the lowest score; compare with care")


def _f(x: float) -> Fraction:
    return Fraction(x).limit_denominator(10**6)


def _show(x: Fraction | float) -> float:
    return round(float(x), 4)


# ---------------------------------------------------------------- games of moves at once
def normal_form(game: dict) -> dict:
    """A game of moves at once worked out. game: {"players": [names], "options": {player: [options]},
    "payoffs": [{"options": {player: option}, "values": {player: value}}]}."""
    players = [str(p) for p in game.get("players") or []]
    if not 2 <= len(players) <= MAX_PLAYERS:
        raise GameError(f"A game has 2 to {MAX_PLAYERS} players.")
    if len(set(players)) != len(players):
        raise GameError("A player is named twice.")
    opts = {p: [str(o) for o in (game.get("options") or {}).get(p) or []] for p in players}
    for p, os_ in opts.items():
        if not 1 <= len(os_) <= MAX_OPTIONS or len(set(os_)) != len(os_):
            raise GameError(f"{p} needs 1 to {MAX_OPTIONS} options, each named once.")
    profiles = list(product(*[opts[p] for p in players]))
    if len(profiles) > MAX_OUTCOMES:
        raise GameError(f"Too many outcomes ({len(profiles)}); at most {MAX_OUTCOMES}.")
    given: dict[tuple, dict] = {}
    for row in game.get("payoffs") or []:
        chosen = row.get("options") or {}
        key = tuple(str(chosen.get(p, "")) for p in players)
        if key not in set(profiles):
            raise GameError(f"An outcome names options the players do not have: {chosen}.")
        vals = row.get("values") or {}
        if set(map(str, vals)) != set(players):
            raise GameError(f"The outcome {', '.join(key)} needs a value for every player.")
        given[key] = {str(k): v for k, v in vals.items()}
    missing = [", ".join(k) for k in profiles if k not in given]
    if missing:
        raise GameError(f"{len(missing)} outcome(s) have no values, e.g. {missing[0]}.")
    flat = [given[k][p] for k in profiles for p in players]
    nums, how = numbers(flat)
    pay = {k: {p: nums[i * len(players) + j] for j, p in enumerate(players)} for i, k in enumerate(profiles)}

    def swap(prof: tuple, i: int, o: str) -> tuple:
        return prof[:i] + (o,) + prof[i + 1:]

    best: dict[str, list[dict]] = {}
    dominant: dict[str, dict] = {}
    for i, p in enumerate(players):
        others = list(product(*[opts[q] for q in players if q != p]))
        replies = []
        for rest in others:
            def prof_of(o, rest=rest, i=i):
                r = list(rest)
                r.insert(i, o)
                return tuple(r)
            top = max(pay[prof_of(o)][p] for o in opts[p])
            replies.append({"others": dict(zip([q for q in players if q != p], rest, strict=True)),
                            "best": [o for o in opts[p] if pay[prof_of(o)][p] == top]})
        best[p] = replies
        strict, weak = None, None
        for o in opts[p]:
            ge = all(pay[swap(k, i, o)][p] >= pay[k][p] for k in profiles)
            gt_each = all(pay[swap(k, i, o)][p] > pay[swap(k, i, o2)][p] for k in profiles for o2 in opts[p] if o2 != o)
            if gt_each and len(opts[p]) > 1:
                strict = o
            elif ge and len(opts[p]) > 1 and any(pay[swap(k, i, o)][p] > pay[k][p] for k in profiles):
                weak = weak or o
        dominant[p] = {"strict": strict, "weak": None if strict else weak}
    stable = [k for k in profiles
              if all(pay[k][p] >= max(pay[swap(k, i, o)][p] for o in opts[p]) for i, p in enumerate(players))]

    def beats(a: tuple, b: tuple) -> bool:
        return all(pay[a][p] >= pay[b][p] for p in players) and any(pay[a][p] > pay[b][p] for p in players)
    pareto = [k for k in profiles if not any(beats(o, k) for o in profiles)]
    agree = []
    for k in stable:
        better = [o for o in profiles if all(pay[o][p] > pay[k][p] for p in players)]
        if better:
            agree.append({"stable": dict(zip(players, k, strict=True)),
                          "better_for_all": [dict(zip(players, o, strict=True)) for o in better]})
    mixed = mixed_equilibria(players, opts, pay) if len(players) == 2 else None
    out = {
        "kind": "simultaneous", "players": players, "how_compared": how,
        "outcomes": [{"options": dict(zip(players, k, strict=True)),
                      "values": {p: _show(pay[k][p]) for p in players}} for k in profiles],
        "best_replies": best,
        "dominant": {p: d for p, d in dominant.items() if d["strict"] or d["weak"]},
        "stable": [dict(zip(players, k, strict=True)) for k in stable],
        "pareto": [dict(zip(players, k, strict=True)) for k in pareto],
        "agreeing_helps": agree,
        "mixed": mixed,
    }
    out["in_words"] = _normal_words(out, players)
    return out


def _named(prof: dict) -> str:
    return ", ".join(f"{p}: {o}" for p, o in prof.items())


def _normal_words(r: dict, players: list[str]) -> list[str]:
    said = []
    for p, d in r["dominant"].items():
        if d["strict"]:
            said.append(f"{p} does best with {d['strict']} whatever the others do (a dominant option).")
        elif d["weak"]:
            said.append(f"{p} never does worse with {d['weak']}, and sometimes better (weakly dominant).")
    if r["stable"]:
        for s in r["stable"]:
            said.append(f"Stable: {_named(s)}. No player gains by changing alone (a Nash equilibrium).")
    else:
        said.append("No outcome is stable when each player picks one option outright: someone always gains by changing.")
    for a in r["agreeing_helps"]:
        said.append(f"The stable outcome {_named(a['stable'])} is beaten for every player by "
                    f"{_named(a['better_for_all'][0])}: they would all do better by agreeing, if they can trust it holds.")
    if r["mixed"]:
        for m in r["mixed"]["equilibria"]:
            if m["pure"]:
                continue
            parts = [f"{p} " + ", ".join(f"{o} {round(q * 100)}%" for o, q in m["mix"][p].items() if q) for p in players]
            said.append("Mixed: " + "; ".join(parts) + " (each keeps the other unable to gain; " +
                        ", ".join(f"{p} expects {m['expect'][p]:g}" for p in players) + ").")
    return said


def _solve(rows: list[list[Fraction]]) -> list[Fraction] | None:
    """Gaussian elimination on an augmented square system; None when it has no single answer."""
    n = len(rows)
    a = [r[:] for r in rows]
    for c in range(n):
        piv = next((r for r in range(c, n) if a[r][c] != 0), None)
        if piv is None:
            return None
        a[c], a[piv] = a[piv], a[c]
        for r in range(n):
            if r != c and a[r][c] != 0:
                f = a[r][c] / a[c][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c], strict=True)]
    return [a[i][n] / a[i][i] for i in range(n)]


def mixed_equilibria(players: list[str], opts: dict, pay: dict) -> dict:
    """Every equilibrium of a two-player game with mixed strategies, by support enumeration (exact fractions; equal
    support sizes, which finds them all in a nondegenerate game)."""
    p1, p2 = players
    r_opts, c_opts = opts[p1], opts[p2]
    a = [[_f(pay[(r, c)][p1]) for c in c_opts] for r in r_opts]
    b = [[_f(pay[(r, c)][p2]) for c in c_opts] for r in r_opts]
    found, seen = [], set()
    for k in range(1, min(len(r_opts), len(c_opts)) + 1):
        for rs in combinations(range(len(r_opts)), k):
            for cs in combinations(range(len(c_opts)), k):
                # column mix q over cs makes p1 indifferent across rs; row mix p over rs makes p2 indifferent across cs
                q = _solve([[a[i][j] for j in cs] + [Fraction(-1), Fraction(0)] for i in rs] +
                           [[Fraction(1)] * k + [Fraction(0), Fraction(1)]]) if k else None
                p = _solve([[b[i][j] for i in rs] + [Fraction(-1), Fraction(0)] for j in cs] +
                           [[Fraction(1)] * k + [Fraction(0), Fraction(1)]])
                if q is None or p is None:
                    continue
                qv, u1 = q[:k], q[k]
                pv, u2 = p[:k], p[k]
                if any(x < 0 for x in qv) or any(x < 0 for x in pv):
                    continue
                qfull = [Fraction(0)] * len(c_opts)
                for j, x in zip(cs, qv, strict=True):
                    qfull[j] = x
                pfull = [Fraction(0)] * len(r_opts)
                for i, x in zip(rs, pv, strict=True):
                    pfull[i] = x
                if any(sum(a[i][j] * qfull[j] for j in range(len(c_opts))) > u1 for i in range(len(r_opts))):
                    continue
                if any(sum(pfull[i] * b[i][j] for i in range(len(r_opts))) > u2 for j in range(len(c_opts))):
                    continue
                key = (tuple(pfull), tuple(qfull))
                if key in seen:
                    continue
                seen.add(key)
                found.append({"mix": {p1: {o: _show(x) for o, x in zip(r_opts, pfull, strict=True)},
                                      p2: {o: _show(x) for o, x in zip(c_opts, qfull, strict=True)}},
                              "fractions": {p1: {o: str(x) for o, x in zip(r_opts, pfull, strict=True)},
                                            p2: {o: str(x) for o, x in zip(c_opts, qfull, strict=True)}},
                              "expect": {p1: _show(u1), p2: _show(u2)}, "pure": k == 1})
    return {"equilibria": found, "method": "support enumeration over equal-sized supports, exact fractions"}


# ---------------------------------------------------------------- games in turn
def _leaves(node: dict, out: list, depth: int = 0) -> None:
    if depth > 50:
        raise GameError("A game in turn is at most 50 moves deep.")
    if "values" in node:
        out.append(node)
        return
    for ch in node.get("choices") or []:
        _leaves(ch.get("then") or {}, out, depth + 1)


def _count(node: dict) -> int:
    return 1 + sum(_count(c.get("then") or {}) for c in node.get("choices") or [] if isinstance(c, dict))


def tree(game: dict) -> dict:
    """A game in turn worked back from the end. game: {"players": [...], "tree": node}; node is
    {"player": p, "choices": [{"option": o, "then": node}]} or an end {"values": {player: value}}."""
    players = [str(p) for p in game.get("players") or []]
    if not 2 <= len(players) <= MAX_PLAYERS:
        raise GameError(f"A game has 2 to {MAX_PLAYERS} players.")
    root = game.get("tree")
    if not isinstance(root, dict):
        raise GameError("A game in turn needs its tree: {player, choices: [{option, then}]} down to ends {values}.")
    if _count(root) > MAX_TREE:
        raise GameError(f"The tree is too big; at most {MAX_TREE} points.")
    leaves: list[dict] = []
    _leaves(root, leaves)
    if not leaves:
        raise GameError("The tree has no ends with values.")
    for lf in leaves:
        if set(map(str, lf["values"])) != set(players):
            raise GameError("Every end of the tree needs a value for every player.")
    nums, how = numbers([lf["values"][p] for lf in leaves for p in players])
    val = {id(lf): {p: nums[i * len(players) + j] for j, p in enumerate(players)} for i, lf in enumerate(leaves)}
    plan: list[dict] = []
    ties: list[str] = []

    def back(node: dict, path: list[str]) -> tuple[dict, list[str]]:
        if "values" in node:
            return val[id(node)], []
        who = str(node.get("player") or "")
        if who not in players:
            raise GameError(f"A point in the tree names a player who is not in the game: {who!r}.")
        choices = node.get("choices") or []
        if not choices:
            raise GameError(f"{who} has a point with no choices.")
        worked = []
        for ch in choices:
            v, line = back(ch.get("then") or {}, path + [f"{who}: {ch.get('option')}"])
            worked.append((str(ch.get("option")), v, line))
        top = max(w[1][who] for w in worked)
        picks = [w for w in worked if w[1][who] == top]
        if len(picks) > 1:
            ties.append(f"After {' then '.join(path) or 'the start'}, {who} is indifferent between "
                        f"{', '.join(w[0] for w in picks)}; the first was taken.")
        pick = picks[0]
        plan.append({"after": path, "player": who, "chooses": pick[0], "gets": _show(top)})
        return pick[1], [f"{who}: {pick[0]}"] + pick[2]

    result, line = back(root, [])
    out = {"kind": "sequential", "players": players, "how_compared": how, "path": line,
           "outcome": {p: _show(result[p]) for p in players}, "plan": plan, "ties": ties}
    out["in_words"] = ([f"Worked back from the end, play goes: {' then '.join(line)}."] +
                       [", ".join(f"{p} gets {out['outcome'][p]:g}" for p in players) + "."] + ties)
    return out


def work_out(game: dict) -> dict:
    """Either kind of game, by its kind (simultaneous, the default, or sequential)."""
    kind = str(game.get("kind") or "simultaneous")
    if kind == "sequential":
        return tree(game)
    if kind != "simultaneous":
        raise GameError('A game\'s kind is "simultaneous" (moves at once) or "sequential" (moves in turn).')
    return normal_form(game)


# ---------------------------------------------------------------- options across the futures
def robustness(options: list[str], futures: list[str], scores: list[dict]) -> dict:
    """Options scored in each future (higher is better): scores [{option, future, value}]."""
    options = [str(o) for o in options]
    futures = [str(f) for f in futures]
    if not options or not futures:
        raise GameError("Give the options and the futures before scoring them.")
    cell: dict[tuple, Any] = {}
    for s in scores:
        o, f = str(s.get("option") or ""), str(s.get("future") or "")
        if o not in options or f not in futures:
            raise GameError(f"A score names an option or future that is not in the study: {o!r} in {f!r}.")
        cell[(o, f)] = s.get("value")
    missing = [f"{o} in {f}" for o in options for f in futures if (o, f) not in cell]
    if missing:
        raise GameError(f"{len(missing)} score(s) missing, e.g. {missing[0]}.")
    nums, how = numbers([cell[(o, f)] for o in options for f in futures])
    v = {(o, f): nums[i * len(futures) + j] for i, o in enumerate(options) for j, f in enumerate(futures)}
    best_in = {f: max(v[(o, f)] for o in options) for f in futures}
    winners = {f: [o for o in options if v[(o, f)] == best_in[f]] for f in futures}
    worst = {o: min(v[(o, f)] for f in futures) for o in options}
    regret = {o: max(best_in[f] - v[(o, f)] for f in futures) for o in options}
    robust = [o for o in options if worst[o] == max(worst.values())]
    least = [o for o in options if regret[o] == min(regret.values())]
    dominated = [{"option": o, "by": o2} for o in options for o2 in options if o2 != o
                 and all(v[(o2, f)] >= v[(o, f)] for f in futures) and any(v[(o2, f)] > v[(o, f)] for f in futures)]
    wins = {o: [f for f in futures if o in winners[f]] for o in options}
    one_hit = [o for o in options if len(wins[o]) == 1 and o not in robust and o not in least]
    out = {"how_compared": how,
           "table": [{"option": o, **{f: _show(v[(o, f)]) for f in futures}, "worst": _show(worst[o]), "regret": _show(regret[o])}
                     for o in options],
           "best_in_each": {f: winners[f] for f in futures}, "robust": robust, "least_regret": least,
           "dominated": dominated, "only_wins_in_one": [{"option": o, "future": wins[o][0]} for o in one_hit]}
    said = [f"Most robust: {', '.join(robust)} (its worst case, {max(worst.values()):g}, is the best of the options' worst cases)."]
    said.append(f"Least regret: {', '.join(least)} (never more than {min(regret.values()):g} behind the best choice in any future).")
    for d in dominated:
        said.append(f"{d['option']} is beaten by {d['by']} in every future (never better).")
    for h in out["only_wins_in_one"]:
        said.append(f"{h['option']} wins only if {h['future']} comes true.")
    out["in_words"] = said
    return out


def players_answers(games: list[dict], worked: list[dict], organisation: str, options: list[str]) -> list[str]:
    """Where a game's organisation player has the study's options: which of them the other players' likely answers
    favour (the options in its stable outcomes, or on the path of a game in turn)."""
    said = []
    opts = {o.lower() for o in options}
    for g, w in zip(games, worked, strict=False):
        if organisation not in (w.get("players") or []) or "error" in w:
            continue
        if w["kind"] == "simultaneous":
            picked = sorted({s[organisation] for s in w["stable"] if s[organisation].lower() in opts})
            if picked:
                said.append(f"In the game {g.get('name')}, the others' likely answers leave {organisation} best with "
                            f"{', '.join(picked)}.")
        else:
            picked = [m.split(": ", 1)[1] for m in w["path"] if m.startswith(f"{organisation}: ")]
            picked = [p for p in picked if p.lower() in opts]
            if picked:
                said.append(f"In the game {g.get('name')}, worked back from the end, {organisation} chooses {picked[0]}.")
    return said
