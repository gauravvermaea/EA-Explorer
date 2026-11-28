"""D975 (owner, 28 Nov 2026, 10:02 and 10:03): eax logins and eax logins --admins show the passwords on the screen, on a
laptop and (after YES) on a server, never in a log; on a server who looked is kept in the audit log."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import core, info  # noqa: E402

SECRETS = {"EAX_FIRST_ADMIN_PASSWORD": "Adm1n-pass-xyz", "EAX_BREAK_GLASS_PASSWORD": "Br3ak-glass-xyz",
           "EAX_DB_MIGRATOR_PASSWORD": "M1grator-pass-xyz", "EAX_KC_ADMIN_PASSWORD": "Kc-adm1n-xyz"}


def _setup(monkeypatch, tmp_path, kind):
    log = tmp_path / "eax.log"
    monkeypatch.setattr(info, "kind", lambda: kind)
    monkeypatch.setattr(info, "setting", lambda k, d="": SECRETS.get(k, d))
    monkeypatch.setattr(info, "capture", lambda args: (0, ""))
    monkeypatch.setattr(info, "compose_args", lambda args: args)
    f = open(log, "w", encoding="utf-8")
    monkeypatch.setitem(core._log, "file", f)
    return log, f


def test_a_laptop_shows_every_login_on_the_screen_and_none_in_the_log(monkeypatch, tmp_path, capsys):
    log, f = _setup(monkeypatch, tmp_path, "laptop")
    info.show_logins()
    f.close()
    out, text = capsys.readouterr().out, log.read_text(encoding="utf-8")
    assert all(v in out for v in SECRETS.values()) and "DEVELOPMENT LOGINS" in out
    assert not any(v in text for v in SECRETS.values()) and "not written here" in text


def test_admins_only_shows_the_admin_and_break_glass_accounts(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, "laptop")
    info.show_logins(admins_only=True, asked=True)
    out = capsys.readouterr().out
    assert "Break-glass account" in out and "Keycloak administrator" in out and SECRETS["EAX_BREAK_GLASS_PASSWORD"] in out
    assert "PostgreSQL installer" not in out and SECRETS["EAX_DB_MIGRATOR_PASSWORD"] not in out and "Test user" not in out


def test_a_server_shows_them_only_when_asked_with_yes_and_audits_it(monkeypatch, tmp_path, capsys):
    log, f = _setup(monkeypatch, tmp_path, "server")
    calls = []
    monkeypatch.setattr(info, "capture", lambda args: calls.append(args) or (0, ""))
    info.show_logins()                                      # eax up on a server: nothing
    assert SECRETS["EAX_BREAK_GLASS_PASSWORD"] not in capsys.readouterr().out and not calls
    monkeypatch.setenv("EAX_NONINTERACTIVE", "1")
    info.show_logins(asked=True, args=[])                    # nobody there to type YES: said how, nothing shown
    assert "--yes" in capsys.readouterr().out and not calls
    info.show_logins(admins_only=True, asked=True, args=["--admins", "--yes"])
    f.close()
    out, text = capsys.readouterr().out, log.read_text(encoding="utf-8")
    assert SECRETS["EAX_BREAK_GLASS_PASSWORD"] in out and "ADMIN LOGINS" in out
    assert not any(v in text for v in SECRETS.values())
    assert calls and "eax.audit_cli" in calls[0] and "installation.logins_shown" in calls[0]


def test_the_launchers_send_logins_to_eaxpy_and_never_log_the_passwords():
    ps1 = (REPO / "eax.ps1").read_text(encoding="utf-8")
    body = ps1[ps1.index("function Show-Logins"):ps1.index("function Show-PartUrls")]
    assert 'Write-Log ("{0,-38}' not in body and 'Write-Host ("{0,-38}' in body
    assert '"eaxpy.ps1") logins @RestArgs' in ps1
    sh = (REPO / "eax.sh").read_text(encoding="utf-8")
    assert "show_logins_on_screen >&3" in sh and 'exec "$BASH" ./eaxpy.sh logins "$@"' in sh
