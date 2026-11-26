"""D949: a project page's goals read their outcomes' links through the entities' index (runs 19 to 21, 26 Nov 2026: the
project page stayed on "Loading..." 25 s; the failed step's report showed this statement running 20 s and more)."""

from __future__ import annotations

from eax import project_work as pw

GOAL = {"id": "11111111-1111-1111-1111-111111111111", "name": "Grow", "description": "", "type": pw.GOAL}
OUTCOME = {"id": "22222222-2222-2222-2222-222222222222", "name": "More", "description": "", "type": pw.OUTCOME}


def _goals(monkeypatch, entities, links=()):
    asked = []

    def rows(conn, sql, **p):
        asked.append((sql, p))
        return list(entities) if "et.name IN ('Goal', 'Outcome')" in sql else list(links)
    monkeypatch.setattr(pw, "_rows", rows)
    monkeypatch.setattr(pw.pj, "core", lambda c: c)
    out = pw.goals(object(), {"home_model": "m", "guid": "p"})
    return out, asked


def test_no_outcome_no_second_statement(monkeypatch):
    out, asked = _goals(monkeypatch, [GOAL])
    assert len(asked) == 1 and out[0]["name"] == "Grow"


def test_the_links_by_uuid_so_the_index_is_used(monkeypatch):
    out, asked = _goals(monkeypatch, [GOAL, OUTCOME], [{"outcome": OUTCOME["id"], "goal": GOAL["id"]}])
    sql, params = asked[1]
    assert "s.guid = ANY (CAST(:ids AS uuid[]))" in sql and "guid::text = ANY" not in sql
    assert params == {"ids": [OUTCOME["id"]]}
    assert out[0]["outcomes"][0]["name"] == "More"
