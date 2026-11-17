"""R6-R1, R6-T1, R6-S1, R6-D1 and init (owner, 17 Nov 2026, 18:39 to 18:55; D743, D745): passwords rotate by themselves
every 90 days on a server, what needs a person is alerted at 30, 14 and 7 days, the Secrets tab shows it all, every
restore resets the database's logins to the config file in use, and eax init asks certificate or password once."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
sys.path.insert(0, str(REPO))

from eaxcli import main as M  # noqa: E402
from eaxcli import secrets as S  # noqa: E402
from eaxcli import secretsrot as R  # noqa: E402
from eaxcli.core import Failure  # noqa: E402


def test_ages_due_and_warnings():
    now = datetime(2026, 11, 17, tzinfo=UTC)
    at = lambda d: (now - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    values = {"EAX_DB_PASSWORD": "x", "EAX_SMTP_PASSWORD": "y", "EAX_OPS_TOKEN": "z", "EAX_DMS_BROKER_PASSWORD_URLENC": "u"}
    state = {"EAX_DB_PASSWORD": {"changed": at(91)}, "EAX_SMTP_PASSWORD": {"changed": at(80)}, "EAX_OPS_TOKEN": {"changed": at(1)}}
    rows = {r["key"]: r for r in R.rows(values, state, 90, now)}
    assert "EAX_DMS_BROKER_PASSWORD_URLENC" not in rows                         # a derived copy is not its own
    assert rows["EAX_DB_PASSWORD"]["due"] and rows["EAX_DB_PASSWORD"]["kind"] == "database" and rows["EAX_DB_PASSWORD"]["auto"]
    assert rows["EAX_SMTP_PASSWORD"]["warn"] == 14 and not rows["EAX_SMTP_PASSWORD"]["auto"] and rows["EAX_SMTP_PASSWORD"]["why"]
    assert not rows["EAX_OPS_TOKEN"]["due"] and rows["EAX_OPS_TOKEN"]["warn"] is None


def test_the_services_made_again_are_those_given_the_secret():
    compose = (REPO / "docker-compose.yml").read_text()
    assert "dms-broker" in R.users_of("EAX_DMS_BROKER_PASSWORD", compose) and "keycloak" not in R.users_of("EAX_DMS_BROKER_PASSWORD", compose)
    assert set(R.users_of("EAX_LIBRARY_KEY", compose)) >= {"api", "library"}


def test_a_rotation_changes_the_database_then_the_file_then_the_services(tmp_path, monkeypatch):
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DEPLOYMENT=server\nEAX_DB_PASSWORD=old\nEAX_DMS_BROKER_PASSWORD=b\nEAX_DMS_BROKER_PASSWORD_URLENC=b\n")
    calls = []
    monkeypatch.setattr(R, "ENV_FILE", env)
    monkeypatch.setattr(R, "_compose", lambda args, stdin="", check=True: calls.append((args, stdin)) or "")
    monkeypatch.setattr(R, "dated_copy", lambda text: tmp_path / "copy")
    monkeypatch.setattr(R, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.setattr(R, "say", lambda *a, **k: None)
    import eaxcli.deploy as D
    monkeypatch.setattr(D, "secret_values", lambda text: {k: v for k, v in (ln.split("=", 1) for ln in text.splitlines())
                                                         if k != "EAX_DEPLOYMENT"})
    out = R.rotate("EAX_DB_PASSWORD", "tester")
    assert out["rotated"] == ["EAX_DB_PASSWORD"]
    alter = calls[0]
    assert alter[0][:3] == ["exec", "-T", "db"] and 'ALTER ROLE "eax_app" PASSWORD' in alter[1] and "old" not in alter[1]
    new = [ln for ln in env.read_text().splitlines() if ln.startswith("EAX_DB_PASSWORD=")][0].split("=", 1)[1]
    assert new != "old" and len(new) == 40 and new in alter[1]                   # the same value in both places
    assert calls[-1][0][:4] == ["up", "-d", "--no-deps", "--force-recreate"] and "api" in calls[-1][0]
    assert R.read_state()["EAX_DB_PASSWORD"]["by"] == "tester"
    calls.clear()
    R.rotate("EAX_DMS_BROKER_PASSWORD", "tester")                                 # the URL-encoded copy changes with it
    text = env.read_text()
    a = [ln for ln in text.splitlines() if ln.startswith("EAX_DMS_BROKER_PASSWORD=")][0].split("=", 1)[1]
    assert f"EAX_DMS_BROKER_PASSWORD_URLENC={a}" in text and "dms" in calls[-1][0]
    with pytest.raises(Failure, match="not rotated by eax"):
        R.rotate_one("EAX_SMTP_PASSWORD", {}, "t")


def test_a_laptop_keeps_its_passwords_unless_asked(tmp_path, monkeypatch):
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DEPLOYMENT=laptop\nEAX_DB_PASSWORD=P^55w0rd1234&\n")
    monkeypatch.setattr(R, "ENV_FILE", env)
    assert R.rotate("--due", "schedule")["skipped"]


def test_init_asks_once_and_a_server_gets_strong_passwords(tmp_path, monkeypatch):
    import eaxcli.persist as P
    monkeypatch.setattr(P, "folder", lambda root=None: tmp_path / "persist")
    monkeypatch.setattr(M, "say", lambda *a, **k: None)
    assert M.auth_mode(["--certificate"], "laptop") == ("certificate", "given")
    assert M.auth_mode([], "laptop", tty=False) == ("password", "the default")
    assert M.auth_mode([], "server", tty=False) == ("certificate", "the default")
    assert M.auth_mode([], "server", ask=lambda q: "2", tty=True) == ("password", "asked")
    with pytest.raises(Failure):
        M.auth_mode(["--certificate", "--password"], "server")
    env = tmp_path / "work" / "eaexplorer.env"
    monkeypatch.setattr(M, "ENV_FILE", env)
    monkeypatch.setattr(M, "WORK", tmp_path / "work")
    monkeypatch.setattr(M, "_ask_base_folder", lambda: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    M.init(["server", "--certificate"])
    text = env.read_text()
    assert "=change-me" not in text and "EAX_AUTH_MODE=certificate" in text
    assert M.auth_mode([], "server", tty=True, ask=lambda q: (_ for _ in ()).throw(AssertionError("asked again"))) == \
        ("certificate", "as chosen before")                                       # a clean restart does not ask again


def test_restores_reset_the_logins_and_the_alert_counts_what_needs_a_person():
    ops = (REPO / "services/ops/ops.py").read_text()
    assert "reset_db_passwords(lambda m: rlog(rec, m))" in ops and "def reset_db_passwords" in ops
    for k, login in S.DB_LOGINS.items():
        assert f'"{k}": "{login}"' in ops.split("DB_LOGINS = {")[1].split("}")[0], k     # the same table in both
    from eax import alerts
    listing = {"secrets": [{"key": "EAX_SMTP_PASSWORD", "days_left": 12, "auto": False},
                           {"key": "EAX_DB_PASSWORD", "days_left": 40, "auto": True}],
               "certificates": [{"name": "authority", "days_left": 3000, "auto": False}]}
    v, msg = alerts.measure_secrets(listing)
    assert v == 12 and "EAX_SMTP_PASSWORD" in msg
    v, msg = alerts.measure_secrets({"secrets": [{"key": "EAX_DB_PASSWORD", "days_left": -3, "auto": True}]})
    assert v == 0 and "did not rotate by itself" in msg
    assert "secrets" in alerts.DEFAULTS


def test_the_schedules_and_the_tab():
    cc = (REPO / "services/ops/commandcentre.py").read_text()
    assert '["secrets", "rotate", "--due"]' in cc and '["certs", "renew"]' in cc
    web = (REPO / "services/web/src/Secrets.jsx").read_text()
    assert "never a value" in web and "/api/v1/admin/secrets/rotate" in web
    assert '["secrets", "Secrets", () => can("system.operate")' in (REPO / "services/web/src/Admin.jsx").read_text()


def test_eax_up_adds_what_a_newer_release_brought(tmp_path, monkeypatch):
    """Updating needs no hand editing: settings the newer template has are added, a server's passwords made here."""
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DEPLOYMENT=server\nEAX_DB_PASSWORD=kept\n")
    monkeypatch.setattr(S, "dated_copy", lambda text: tmp_path / "copy")
    added = S.fill(env)
    text = env.read_text()
    assert "EAX_CONSOLE_IT_PASSWORD" in added and "EAX_DB_PASSWORD" not in added and "EAX_DB_PASSWORD=kept" in text
    pw = [ln for ln in text.splitlines() if ln.startswith("EAX_CONSOLE_IT_PASSWORD=")][0].split("=", 1)[1]
    assert len(pw) == 40 and "change-me" not in pw
    assert "EAX_AUTH_MODE=password" in text            # an installation from before stays as it was until switched
    assert S.fill(env) == []                                                     # nothing twice
    for form in ("eax.ps1", "eax.sh"):
        assert "secrets fill" in (REPO / form).read_text(), form
