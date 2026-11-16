"""R5.5.1 on a real database: architecture decision records and dispensations, run against every migration (0001 to the
newest) on PostgreSQL. Each test runs in a transaction rolled back at the end.

They need a PostgreSQL database every migration has run on: EAX_MIGRATED_TEST_DSN, for example
postgresql+psycopg://postgres@127.0.0.1:55432/eaxmig. Without it they are skipped (the code tests in
test_r5_5_1_decisions.py run anywhere)."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


class U:
    def __init__(self, name, roles):
        self.username, self.roles, self.break_glass = name, list(roles), False


SA, BOARD, PLAIN = U("sue_admin", ["super-admin"]), U("bob_board", ["architecture-board", "user"]), U("pat", ["user"])
ADR_FIELDS = {"context": "c", "options": "o", "decision": "d", "rationale": "r", "consequences": "q"}
DISP_FIELDS = {"waived": "w", "systems": "s", "justification": "j", "risks": "k", "remediation": "m"}


@pytest.fixture()
def conn(monkeypatch):
    from sqlalchemy import create_engine, text

    from eax import notify, settings
    told = []
    monkeypatch.setattr(notify, "create", lambda *a, **k: told.append(k) or 1)
    monkeypatch.setattr(settings, "values", lambda *a, **k: {})
    eng = create_engine(DSN)
    c = eng.connect()
    tx = c.begin()
    c.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
    c.told = told
    yield c
    tx.rollback()
    c.close()
    eng.dispose()


def _project(conn, name="Board test project"):
    from sqlalchemy import text
    return conn.execute(text("""INSERT INTO proj.projects (name, purpose, created_by) VALUES (:n, 'test', 'sue_admin')
                                RETURNING guid::text"""), {"n": name}).scalar()


def test_numbered_per_year_across_the_organisation(conn):
    from eax import decisions as dec
    from eax import governance as gv
    p = _project(conn)
    a = gv.add(conn, p, SA, {"kind": dec.ADR, "title": "One"})
    b = dec.org_add(conn, BOARD, {"kind": dec.ADR, "title": "Two"})
    d = dec.org_add(conn, BOARD, {"kind": dec.DISP, "title": "Waiver"})
    y = date.today().year
    assert a["ref"] == f"ADR-{y}-001" and b["ref"] == f"ADR-{y}-002" and d["ref"] == f"DISP-{y}-001"


def test_only_the_board_writes_the_organisations_log(conn):
    from eax import decisions as dec
    from eax.metamodel_edit import EditError
    with pytest.raises(EditError) as e:
        dec.org_add(conn, PLAIN, {"kind": dec.ADR, "title": "Not mine"})
    assert e.value.status == 403
    rid = dec.org_add(conn, BOARD, {"kind": dec.ADR, "title": "Mine"})["id"]
    with pytest.raises(EditError):
        dec.org_decide(conn, PLAIN, rid, "approved")
    assert dec.org_listing(conn, PLAIN)["may_accept"] is False


def test_accepting_needs_the_template_and_sets_accepted(conn):
    from eax import decisions as dec
    from eax.metamodel_edit import EditError
    rid = dec.org_add(conn, BOARD, {"kind": dec.ADR, "title": "Cloud first", "owner": "Chief Architect"})["id"]
    with pytest.raises(EditError) as e:
        dec.org_decide(conn, BOARD, rid, "approved")
    assert "record type" in str(e.value) and "Context and problem" in str(e.value)
    dec.org_update(conn, BOARD, rid, {"record_type": "Architecture", "fields": ADR_FIELDS})
    dec.org_decide(conn, BOARD, rid, "approved", "ok")
    r = next(x for x in dec.org_listing(conn, BOARD)["records"] if x["id"] == rid)
    assert r["status"] == "Accepted" and r["approval"] == "Approved" and r["approved_by"] == "bob_board"
    with pytest.raises(EditError):
        dec.org_decide(conn, BOARD, rid, "rejected", "")                  # a rejection says why


def test_a_project_record_is_accepted_through_its_sign_off(conn):
    from eax import decisions as dec
    from eax import governance as gv
    from eax.metamodel_edit import EditError
    p = _project(conn)
    rid = gv.add(conn, p, SA, {"kind": dec.DISP, "title": "Keep it on premises", "status": "Draft"})["id"]
    with pytest.raises(EditError):
        gv.send_for_approval(conn, p, SA, rid)                            # the template first
    gv.update(conn, p, SA, rid, {"owner": "o", "sponsor": "CIO", "expires_on": str(date.today() + timedelta(days=60)),
                                 "fields": DISP_FIELDS})
    gv.approve_with_evidence(conn, p, SA, rid, "Board minutes")
    r = next(x for x in gv.listing(conn, p, SA)["records"] if x["id"] == rid)
    assert r["status"] == "Accepted" and r["ref"].startswith("DISP-")


def test_a_dispensation_needs_its_end_date(conn):
    from eax import decisions as dec
    from eax.metamodel_edit import EditError
    with pytest.raises(EditError) as e:
        dec.org_add(conn, BOARD, {"kind": dec.DISP, "title": "x", "status": "Accepted"})
    assert "expiry" in str(e.value)


def test_superseding_marks_the_older_one_and_links_show_both_ways(conn):
    from eax import decisions as dec
    old = dec.org_add(conn, BOARD, {"kind": dec.ADR, "title": "Old", "owner": "o", "record_type": "Data", "fields": ADR_FIELDS})["id"]
    dec.org_decide(conn, BOARD, old, "approved")
    new = dec.org_add(conn, BOARD, {"kind": dec.ADR, "title": "New"})["id"]
    dec.add_link(conn, BOARD, new, {"kind": "record", "relation": "supersedes", "target": old})
    assert next(x for x in dec.org_listing(conn, BOARD)["records"] if x["id"] == old)["status"] == "Superseded"
    back = dec.links(conn, BOARD, old)["linked_from"]
    assert back and back[0]["relation"] == "superseded-by" and back[0]["id"] == new


def test_ending_warned_once_then_expired_on_the_day(conn):
    from eax import decisions as dec
    today = date.today()
    rid = dec.org_add(conn, BOARD, {"kind": dec.DISP, "title": "Ends soon", "owner": "o", "sponsor": "CIO", "fields": DISP_FIELDS,
                                    "expires_on": str(today + timedelta(days=10))})["id"]
    dec.org_decide(conn, BOARD, rid, "approved")
    conn.told.clear()
    assert dec.run_ending(conn, today)["warned"] and len(conn.told) == 1
    assert dec.run_ending(conn, today)["warned"] == []                    # once
    out = dec.run_ending(conn, today + timedelta(days=10))
    assert out["ended"] and conn.told[-1]["needs_action"] is True
    r = next(x for x in dec.org_listing(conn, BOARD)["records"] if x["id"] == rid)
    assert r["status"] == "Expired"
    assert dec.run_ending(conn, today + timedelta(days=11))["ended"] == []  # told once


def test_the_report_rows_leave_test_data_out(conn):
    from sqlalchemy import text

    from eax import decisions as dec
    from eax import governance as gv
    real, test = _project(conn, "Real project"), _project(conn, "self_test_abc_1")
    gv.add(conn, real, SA, {"kind": dec.ADR, "title": "Counted"})
    gv.add(conn, test, SA, {"kind": dec.ADR, "title": "Left out"})
    dec.org_add(conn, BOARD, {"kind": dec.ADR, "title": "Org one"})
    assert dec.refresh_report(conn) == 2
    titles = {r[0] for r in conn.execute(text("SELECT title FROM rpt.v_governance_decisions"))}
    assert titles == {"Counted", "Org one"}
    assert {r[0] for r in conn.execute(text("SELECT project_name FROM rpt.v_governance_decisions"))} == {"Real project", "Organisation"}
    s = dec.summary(dec.report_rows(conn, SA))
    assert s["decisions_by_status"] == {"Draft": 2}
