"""R5.9 (owner, 14 Nov 2026: "We need an alerts system like nagios"; 15 Nov 2026, D689: in EA Explorer and a webhook,
"add email with 1"): checks with Nagios's states, thresholds, holding, flapping, telling people, silences, email."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import alerts as A  # noqa: E402


def test_each_check_reaches_warning_and_critical_at_its_levels_and_back():
    assert [A.state_of(v, 80, 90) for v in (50, 80, 89, 90, 99)] == ["OK", "WARNING", "WARNING", "CRITICAL", "CRITICAL"]
    assert [A.state_of(v, 21, 7, higher_is_worse=False) for v in (60, 21, 8, 7)] == ["OK", "WARNING", "WARNING", "CRITICAL"]
    assert A.state_of(None, 1, 2) == "UNKNOWN"


def test_a_short_blip_gives_no_alert_and_a_held_state_does():
    row = A.step(None, "CRITICAL")
    assert row["state"] == "OK" and not row["changed"]                  # one bad answer: nothing yet
    row = A.step(row, "OK")
    assert row["state"] == "OK"
    row = A.step(A.step(row, "CRITICAL"), "CRITICAL")
    assert row["state"] == "CRITICAL" and row["changed"]
    row = A.step(row, "CRITICAL")
    assert not row["changed"]


def test_flapping_is_noticed():
    row = None
    for seen in ["CRITICAL", "CRITICAL", "OK", "OK", "CRITICAL", "CRITICAL", "OK", "OK"]:
        row = A.step(row, seen)
    assert row["flapping"]


def test_email_goes_through_the_organisations_mail_server(monkeypatch):
    class Fake:
        def __init__(self):
            self.sent = []

        def send_message(self, m):
            self.sent.append(m)

        def quit(self):
            pass
    monkeypatch.setenv("EAX_SMTP_HOST", "mail.example.org")
    monkeypatch.setenv("EAX_SMTP_FROM", "ea@example.org")
    f = Fake()
    assert A.send_email(["it@example.org"], "Alert: disk is CRITICAL", "body", smtp=f) == ""
    assert f.sent[0]["To"] == "it@example.org" and f.sent[0]["From"] == "ea@example.org"
    assert "no address" in A.send_email([], "x", "y", smtp=f)
    monkeypatch.setenv("EAX_SMTP_HOST", "")
    assert "no mail server" in A.send_email(["a@b.c"], "x", "y")


def test_email_is_for_alerts_only_and_set_in_the_config_file():
    for t in ("eaexplorer.laptop.env", "eaexplorer.server.env"):
        text = (REPO / "deploy/templates" / t).read_text()
        assert "\nEAX_SMTP_HOST=\n" in text and "EAX_SMTP_SECURITY=starttls" in text
    import eax
    sends = [p.name for p in Path(eax.__file__).parent.rglob("*.py") if "smtplib" in p.read_text(encoding="utf-8")]
    assert sends == ["alerts.py"], sends                         # D689: email for alerts only


def test_custom_checks_are_checked_before_they_are_kept():
    class Conn:
        pass
    for body, why in (({"key": "x", "kind": "url", "target": "ftp://a"}, "http"),
                      ({"key": "x", "kind": "sql", "target": "delete from core.models"}, "SELECT"),
                      ({"key": "", "kind": "url"}, "key")):
        try:
            A.add_custom(Conn(), body, "ann")
        except ValueError as exc:
            assert why in str(exc)
        else:
            raise AssertionError(body)


def test_it_runs_every_minute_and_is_on_the_page_and_in_mcp():
    assert 'name="eax.alerts_run"' in (REPO / "services/api/eax/jobs.py").read_text()
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    for r in ('"/admin/alerting"', '"/admin/alerting/summary"', '"/admin/alerting/silence"', '"/admin/alerting/custom"',
              '"/admin/alerting/history"', '"/admin/alerting/test-email"'):
        assert r in admin
    assert "async def ops_alerts()" in (REPO / "services/api/eax/mcp_operations.py").read_text()
    sql = (REPO / "services/api/migrations/sql/0080_r5_alerts.sql").read_text()
    for t in ("alert_checks", "alert_history", "alert_silences", "alert_config", "alert_custom"):
        assert f"core.{t}" in sql
    assert "CREATE FUNCTION" not in sql and "TRIGGER" not in sql                     # D248
    assert '["alerts", "Alerts"' in (REPO / "services/web/src/Admin.jsx").read_text()
