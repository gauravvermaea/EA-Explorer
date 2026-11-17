"""Site pairings and sync (Release 6.5, D749 and D753; owner, 17 Nov 2026, 19:30 to 19:40, 20:51).

The pure parts run anywhere; the flow runs on a database every migration has run on (EAX_MIGRATED_TEST_DSN), both
sides of a pairing in the one database (each pairing row says which side it is), everything rolled back."""

from __future__ import annotations

import json
import os

import pytest

from eax import pairing as sp
from eax.metamodel_edit import EditError

DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")
real_db = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


class U:
    def __init__(self, name, roles):
        self.username, self.roles = name, list(roles)


SA, IT = U("sue_admin", ["super-admin"]), U("ian_it", ["it-admin"])


# ---------------------------------------------------------------- pure
def test_a_key_names_its_pairing_and_nothing_else_is_a_key():
    g = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    key = sp.new_key(g)
    assert key.startswith("eaxp_") and sp.key_pairing(key) == g
    assert sp.hash_key(key) != key and len(sp.hash_key(key)) == 64
    for bad in ("", "eaxp_short_x", "eaxk_" + key[5:], g):
        assert sp.key_pairing(bad) is None


def test_a_dr_copy_refuses_changes_but_not_reading_the_sync_or_taking_over(monkeypatch):
    monkeypatch.setattr(sp, "dr_copy", lambda conn=None: {"from": "Production", "pairing": "x"})
    assert "DR copy of Production" in sp.refused_on_dr("POST", "/api/v1/models/abc/entities")
    assert sp.refused_on_dr("GET", "/api/v1/models") is None
    for path in ("/api/v1/sync/batch", "/api/v1/pairings/x", "/api/v1/heartbeat"):
        assert sp.refused_on_dr("POST", path) is None
    monkeypatch.setattr(sp, "dr_copy", lambda conn=None: None)
    assert sp.refused_on_dr("POST", "/api/v1/models/abc/entities") is None


def test_a_batch_file_says_what_it_holds_and_a_newer_one_is_refused(monkeypatch):
    data = sp.build_file([({"kind": "users", "id": "users", "name": "Users"}, b'{"users": []}')], {"seq": 4, "kind": "dr"})
    head, z = sp.read_file(data)
    assert head["format"] == sp.FORMAT and head["seq"] == 4
    assert head["items"][0]["file"] == "items/users.json" and head["items"][0]["sha256"] == sp.sha256(b'{"users": []}')
    assert z.read("items/users.json") == b'{"users": []}'
    from eax import backups as bk
    monkeypatch.setattr(bk, "newer_than_here", lambda v: True)
    with pytest.raises(EditError) as exc:
        sp.read_file(data)
    assert exc.value.status == 409 and "upgrade this site first" in str(exc.value)
    with pytest.raises(EditError):
        sp.read_file(b"not a zip")


def test_dr_is_always_the_entire_site_and_a_choice_needs_something_chosen():
    assert sp._clean_scope({"all": False, "models": ["x" * 36]}, "dr") == {"all": True}
    with pytest.raises(EditError):
        sp._clean_scope({"all": False}, "content")
    g = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    assert sp._clean_scope({"all": False, "projects": [g, "nope"]}, "content")["projects"] == [g]


def test_the_api_the_jobs_the_page_and_the_read_only_are_wired():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    app = (root / "services/api/eax/app.py").read_text()
    assert "pairing_blp" in app and "pairing.refused_on_dr(request.method, request.path)" in app
    jobs = (root / "services/api/eax/jobs.py").read_text()
    assert 'name="eax.sync_tick"' in jobs and 'name="eax.sync_enqueue"' in jobs and 'name="eax.sync_commit"' in jobs
    assert '["pairings", "Site pairings"' in (root / "services/web/src/Admin.jsx").read_text()
    assert "#/admin/pairings" in (root / "services/web/src/menu.js").read_text()
    from eax import settings
    assert settings.REGISTRY["site_purpose"][3] == "PROD"


# ---------------------------------------------------------------- the flow, on a real database
@pytest.fixture()
def conn(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, text
    monkeypatch.setenv("EAX_REMOTE_SECRET_KEY", "a-test-key-of-enough-length")
    monkeypatch.setattr(sp, "_local_name", lambda c: "Here")
    monkeypatch.setattr(sp, "_own_url", lambda: "https://here.example")
    monkeypatch.setattr(sp, "purpose", lambda c=None: "PROD")
    monkeypatch.setattr(sp, "folder", lambda: tmp_path)
    eng = create_engine(DSN)
    c = eng.connect()
    tx = c.begin()
    c.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
    yield c
    tx.rollback()
    c.close()
    eng.dispose()


def _paired(conn, kind="content"):
    """Site 2 makes a key; Site 1 pairs with it (its call to Site 2 answered by Site 2's own code, here)."""
    key = sp.make_key(conn, SA, "From Site 1")["key"]

    def call(p, method, path, body=None, data=None, headers=None, key=None):
        assert path == "/api/v1/sync/hello" and method == "POST"
        return sp.hello(conn, body["key"], body)
    sender = sp.pair(conn, SA, {"name": "To Site 2", "url": "https://site2.example", "key": key, "kind": kind}, call=call)
    receiver = next(p for p in sp.listing(conn)["pairings"] if p["side"] == "receiver")
    return key, sender, receiver


@real_db
def test_only_a_super_admin_pairs(conn):
    with pytest.raises(EditError) as exc:
        sp.make_key(conn, IT)
    assert exc.value.status == 403


@real_db
def test_pairing_waits_for_site_2_to_accept_and_site_1_learns_it(conn):
    key, sender, receiver = _paired(conn)
    assert sender["status"] == "waiting" and receiver["status"] == "waiting"
    assert receiver["peer_name"] == "Here" and receiver["peer_url"] == "https://here.example"
    with pytest.raises(EditError) as exc:                          # nothing is taken before it is accepted
        sp.receive(conn, key, 1, "", b"")
    assert exc.value.status == 403 and "waiting" in str(exc.value)
    sp.decide(conn, SA, receiver["id"], "accept", {"commit_mode": "manual"})

    def status_call(p, method, path, **kw):
        return sp.status_for_peer(conn, key)
    assert sp.check_peers(conn, call=status_call) == ["To Site 2: accepted by Site 2"]
    assert sp._one(conn, sender["id"])["status"] == "accepted"
    with pytest.raises(EditError):                                 # a wrong key opens nothing
        sp.status_for_peer(conn, key[:-3] + "xyz")


@real_db
def test_batches_are_taken_in_order_each_answered(conn):
    key, _sender, receiver = _paired(conn)
    sp.decide(conn, SA, receiver["id"], "accept", {"commit_mode": "manual"})
    b1 = sp.build_file([({"kind": "users", "id": "users", "name": "Users"}, b'{"users": []}')], {"seq": 1})
    assert sp.receive(conn, key, 1, sp.sha256(b1), b1) == (200, {"status": "received", "seq": 1, "expect": 2,
                                                              "commit": "waiting for this site's admin"})
    assert sp.receive(conn, key, 1, sp.sha256(b1), b1)[1]["status"] == "duplicate"
    status, out = sp.receive(conn, key, 3, sp.sha256(b1), b1)
    assert status == 409 and out["status"] == "gap" and out["expect"] == 2
    status, out = sp.receive(conn, key, 2, "0" * 64, b1)
    assert status == 400 and out["status"] == "damaged"
    waiting = sp.batches(conn, receiver["id"])
    assert [b["status"] for b in waiting] == ["waiting"]
    applied = []
    out = sp.commit(conn, conn, waiting[0]["id"], "sue_admin",
                    apply=lambda core, pc, item, data, who: applied.append((item["kind"], data, who.username)) or "done")
    assert out["status"] == "committed" and applied == [("users", b'{"users": []}', "sync:From Site 1")]
    with pytest.raises(EditError):                                 # committed once only
        sp.commit(conn, conn, waiting[0]["id"], "sue_admin", apply=lambda *a: "x")


@real_db
def test_one_item_failing_does_not_stop_the_others(conn):
    key, _sender, receiver = _paired(conn)
    sp.decide(conn, SA, receiver["id"], "accept", {"commit_mode": "auto"})
    b1 = sp.build_file([({"kind": "users", "id": "users", "name": "Users"}, b"{}"),
                        ({"kind": "organisation", "id": "organisation", "name": "Org"}, b"zz")], {"seq": 1})
    sp.receive(conn, key, 1, sp.sha256(b1), b1)
    todo = sp.next_to_commit(conn)
    assert len(todo) == 1                                         # auto: picked up by the minute job

    def apply(core, pc, item, data, who):
        if item["kind"] == "organisation":
            raise RuntimeError("Documents is away")
        return "fine"
    out = sp.commit(conn, conn, todo[0], "sync", apply=apply)
    assert out["status"] == "committed" and out["failed"] == ["Org: Documents is away"] and out["done"] == ["Users: fine"]


@real_db
def test_a_dr_pairing_commits_by_itself_makes_a_dr_copy_and_taking_over_lifts_it(conn):
    _key, _sender, receiver = _paired(conn, kind="dr")
    assert receiver["commit_mode"] == "auto"
    sp.decide(conn, SA, receiver["id"], "accept", {"commit_mode": "manual"})       # DR stays by itself
    assert sp._one(conn, receiver["id"])["commit_mode"] == "auto"
    assert sp.dr_copy(conn)["from"] == "Here"
    sp.decide(conn, SA, receiver["id"], "stop")
    assert sp.dr_copy(conn) is None


@real_db
def test_sync_now_queues_numbered_batches_and_automatic_sends_only_what_changed(conn, monkeypatch, tmp_path):
    key, sender, receiver = _paired(conn)
    sp.decide(conn, SA, receiver["id"], "accept", {})
    conn.execute(__import__("sqlalchemy").text("UPDATE core.site_pairings SET status = 'accepted' WHERE guid = CAST(:g AS uuid)"),
                 {"g": str(sender["id"])})
    items = [{"kind": "model", "id": "m1", "name": "Model one"}, {"kind": "project", "id": "p1", "name": "Project one"}]
    prints = {"m1": "a", "p1": "b"}
    monkeypatch.setattr(sp, "_scope_items", lambda core, pc, p: items)
    monkeypatch.setattr(sp, "fingerprint", lambda core, pc, item: prints[item["id"]])
    monkeypatch.setattr(sp, "item_bytes", lambda core, pc, item, by: f"bytes of {item['id']}".encode())
    first = sp.enqueue(conn, conn, sender["id"], "sue_admin")
    assert first["items"] == 2 and [b["seq"] for b in first["batches"]] == [1]
    assert sp.enqueue(conn, conn, sender["id"], "sync", only_changed=True)["items"] == 0
    prints["p1"] = "changed"
    again = sp.enqueue(conn, conn, sender["id"], "sync", only_changed=True)
    assert again["items"] == 1 and again["batches"][0]["seq"] == 2

    sent = []

    def call(p, method, path, data=None, headers=None, **kw):       # Site 2's own code answers each batch
        status, out = sp.receive(conn, key, int(headers["X-Eax-Seq"]), headers["X-Eax-Sha256"], data)
        sent.append((headers["X-Eax-Seq"], out["status"]))
        if status >= 400:
            err = EditError(out.get("message") or out["status"], status)
            err.answer = out
            raise err
        return out
    sp.send_queued(conn, call=call)
    assert sent == [("1", "received"), ("2", "received")]
    out_batches = [b for b in sp.batches(conn, sender["id"]) if b["direction"] == "out"]
    assert {b["status"] for b in out_batches} == {"sent"}
    assert all(b["reply"]["status"] == "received" for b in out_batches)
    # Site 2 restored to before batch 2: it expects 2 again, Site 1 sends from there
    assert sp.rewind(conn, sp._one(conn, sender["id"])["_id"], 2) == 1
    assert json.dumps([b["status"] for b in sp.batches(conn, sender["id"]) if b["direction"] == "out"]) == '["queued", "sent"]'
