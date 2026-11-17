"""eax maintenance status|clear (the owner, 17 Nov 2026, 11:19: "add another feature in eax that removes the mantainance
page, just in case something crashed in backup or DR run"): what a cut-off backup, restore, test, drill or DR pack
leaves - the maintenance page, a restore's record, the paused background - shown, and cleared unless a backup or a
restore is still running in the backup container (--force clears anyway; nothing is ever stopped)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import stack  # noqa: E402
from eaxcli.core import Failure  # noqa: E402


@pytest.fixture()
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(stack, "WORK", tmp_path)
    (tmp_path / "proxy").mkdir()
    (tmp_path / "proxy" / "maintenance").write_text("A backup is being taken (x)\n")
    (tmp_path / "maintenance.json").write_text('{"what": "restore of B1"}')
    (tmp_path / "quiet.json").write_text('{"by": "eax test backup-restore"}')
    said = []
    monkeypatch.setattr(stack, "say", lambda m, *a: said.append(m))
    return tmp_path, said


def test_status_shows_what_was_left_and_changes_nothing(work, monkeypatch):
    w, said = work
    monkeypatch.setattr(stack, "compose_out", lambda a: [])
    stack.maintenance("status")
    text = "\n".join(said)
    assert "the maintenance page" in text and "A backup is being taken" in text and "restore of B1" in text
    assert "the background paused" in text and "maintenance clear" in text
    assert all((w / f).exists() for f in ("proxy/maintenance", "maintenance.json", "quiet.json"))


def test_clear_removes_all_three_unless_a_backup_still_runs(work, monkeypatch):
    w, said = work
    monkeypatch.setattr(stack, "compose_out", lambda a: ["412 /bin/sh /app/backup.sh nightly"])
    with pytest.raises(Failure, match="still running"):
        stack.maintenance("clear")
    assert (w / "quiet.json").exists()                                         # nothing cleared, nothing stopped
    stack.maintenance("clear", ["--force"])
    assert not any((w / f).exists() for f in ("proxy/maintenance", "maintenance.json", "quiet.json"))
    monkeypatch.setattr(stack, "compose_out", lambda a: [])
    said.clear()
    stack.maintenance("clear")
    assert "Nothing is left" in said[0]


def test_every_form_has_it():
    assert 'status|clear) shift; exec "$BASH" ./eaxpy.sh maintenance "$@"' in (REPO / "eax.sh").read_text()
    assert '$RestArgs[0] -in @("status", "clear")' in (REPO / "eax.ps1").read_text()
    assert "### maintenance on|off|status|clear [--force]" in (REPO / "eaxcli/help.txt").read_text()
    assert 'stack.maintenance(rest[0] if rest else "", rest[1:])' in (REPO / "eaxcli/main.py").read_text()
