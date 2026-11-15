"""R5.27 (owner, 15 Nov 2026, 19:17, D700): "Service desk UI is really bad can we first select broad level grouing, then
the catalogue. Tiket gets assigned to Super admin always. They can assign it to someone else. There needs to be other
which is something that doesnt exist. Reports are not needed. Those people will do themselvs. Help is not needed";
approvals: "No, Super Admin decides"."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import permissions as P  # noqa: E402
from eax import servicedesk as sd  # noqa: E402

SQL = (REPO / "services/api/migrations/sql/0087_r5_service_desk_groups.sql").read_text()
JSX = (REPO / "services/web/src/ServiceDesk.jsx").read_text()


class Conn:
    """Just enough of a connection for people() and assignment checks."""
    def __init__(self, users):
        self.users = users

    def execute(self, stmt, params=None):
        sql = str(stmt)
        rows = [{"u": u} for u in self.users] if "known_users" in sql else []

        class R:
            def mappings(self_inner):
                class M(list):
                    def first(self2):
                        return self2[0] if self2 else None
                return M(rows)
        return R()


def test_the_groups_in_order_with_other_last():
    types = [{"key": "a", "area": "Models"}, {"key": "b", "area": "Access"}, {"key": "c", "area": "Projects"},
             {"key": "d", "area": "Our own"}, {"key": sd.OTHER, "area": "Other"}]
    names = [g["name"] for g in sd.groups(types)]
    assert names == ["Models", "Projects", "Access", "Our own", "Other"]
    assert all(g["about"] for g in sd.groups(types) if g["name"] != "Our own")
    assert next(g for g in sd.groups(types) if g["name"] == "Other")["types"] == 0     # "Something else" is not counted
    # a group with nothing left in it (Reports, Help switched off) is not shown
    assert "Reports" not in [g["name"] for g in sd.groups([{"key": sd.OTHER, "area": "Other"}])]


def test_reports_and_help_switched_off_other_its_own_group_and_no_approvals():
    assert "enabled = false" in SQL and "area IN ('Reports', 'Help') AND key <> 'other'" in SQL
    assert "SET area = 'Other', name = 'Something else'" in SQL
    assert "SET team = 'super-admin', approval = ''" in SQL
    assert "DELETE FROM" not in SQL.upper() and "CREATE FUNCTION" not in SQL and "TRIGGER" not in SQL   # D248, kept for old requests
    v = (REPO / "services/api/migrations/versions/0087_r5_service_desk_groups.py").read_text()
    assert 'down_revision = "0086_r5_live_browser"' in v


def _ticket(**kw):
    t = {"id": 7, "status": "new", "raised_by": "ann", "assigned_to": None, "team": P.SUPER_ADMIN, "approval": "",
         "due_at": None, "created_at": None, "updated_at": None, "closed_at": None, "approved_at": None}
    t.update(kw)
    return t


def test_super_admins_assign_the_person_assigned_works_on_it():
    boss = sd._shape(None, _ticket(), "sue", [P.SUPER_ADMIN])
    assert boss["can_assign"] and boss["can_work"] and not boss["can_approve"]
    it_admin = sd._shape(None, _ticket(), "ian", [P.IT_ADMIN])                  # a team no longer works it
    assert not it_admin["can_work"] and not it_admin["can_assign"]
    mine = sd._shape(None, _ticket(assigned_to="bob"), "bob", [P.USER])
    assert mine["assigned_to_me"] and mine["can_work"] and not mine["can_assign"]
    asker = sd._shape(None, _ticket(), "ann", [P.USER])
    assert asker["mine"] and not asker["can_work"]


def test_people_to_assign_to_leave_out_service_accounts():
    assert sd.people(Conn(["ann", "svc-self-test-1-architect", "bob", "service-account-x"])) == ["ann", "bob"]


def test_only_a_super_admin_assigns(monkeypatch):
    t = sd._shape(None, _ticket(assigned_to="bob"), "bob", [P.USER])
    monkeypatch.setattr(sd, "get", lambda conn, ident, me, roles: t)
    with pytest.raises(sd.DeskError, match="Only a Super Admin assigns"):
        sd.act(None, 7, "bob", [P.USER], "assign", {"to": "cat"})


def test_the_catalogue_page_has_the_steps_and_the_assigning():
    for s in ("desk-steps", "Something not listed here", "Send to the Super Admins", "/api/v1/service-desk/people",
              "Assign to someone else", "Hand it back to the Super Admins", "the Super Admins"):
        assert s in JSX
    assert "cat.teams" not in JSX and "Approval <select" not in JSX
    api = (REPO / "services/api/eax/api/servicedesk.py").read_text()
    assert '@blp.route("/people")' in api and '"groups": sd.groups(types)' in api
