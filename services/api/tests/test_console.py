"""The console (D330): the application's part (eax.console_cli) and the operations helper's (services/ops/console.py)."""
import importlib
import sys
from pathlib import Path

import pytest

from eax import console_cli as cc

OPS = Path(__file__).resolve().parents[2] / "ops"


def test_console_cli_usage_and_remote_needs_a_server(capsys):
    assert cc.main([]) == 2
    assert cc.main(["remote"]) == 2
    assert "--server" in capsys.readouterr().out


def test_confirm_needs_yes_exactly(monkeypatch):
    for typed, want in (("YES", True), ("yes", False), ("", False)):
        monkeypatch.setattr("builtins.input", lambda _p, t=typed: t)
        assert cc.confirm("Go?") is want


def test_choose_back_and_numbers(monkeypatch):
    answers = iter(["9", "2"])
    monkeypatch.setattr("builtins.input", lambda _p: next(answers))
    assert cc.choose("Pick", ["a", "b"]) == 1
    monkeypatch.setattr("builtins.input", lambda _p: "b")
    assert cc.choose("Pick", ["a"]) is None


@pytest.fixture
def ops_console(tmp_path, monkeypatch):
    monkeypatch.setenv("EAX_WORK_MOUNT", str(tmp_path))
    monkeypatch.syspath_prepend(str(OPS))
    for m in ("ops", "console"):
        sys.modules.pop(m, None)
    (tmp_path / "eaexplorer.env").write_text("EAX_DEPLOYMENT=laptop\nEAX_BREAK_GLASS_PASSWORD=old\n", encoding="utf-8")
    return importlib.import_module("console"), tmp_path


def test_menu_has_the_fifteen_items(ops_console):
    con, _ = ops_console
    assert len(con.MENU) == 15 and con.MENU[7].startswith("Reset a password")
    assert con.MENU[14].startswith("Test this installation")       # D953


@pytest.mark.parametrize(("answers", "code"), [(["15", "1"], 26), (["15", "2"], 27), (["15", "3", "YES"], 28),
                                               (["15", "4"], 29)])
def test_the_tests_are_handed_to_the_machine(ops_console, monkeypatch, answers, code):
    """D953 (owner, 27 Nov 2026: "When running full test from console there is no command for risky option")."""
    con, _ = ops_console
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _p: next(it))
    assert con.menu("14.0.0", "laptop") == code


def test_the_risky_suite_needs_yes(ops_console, monkeypatch):
    con, _ = ops_console
    it = iter(["15", "3", "no", ""])
    monkeypatch.setattr("builtins.input", lambda _p: next(it))
    assert con.menu("14.0.0", "laptop") == -1


def test_every_form_runs_the_test_chosen_and_names_them_in_its_prompt():
    root = Path(__file__).resolve().parents[3]
    ps1, sh = (root / "eax.ps1").read_text(encoding="utf-8"), (root / "eax.sh").read_text(encoding="utf-8")
    assert "@(0, 20, 21, 23, 25, 26, 27, 28, 29)" in ps1 and "0|20|21|23|25|26|27|28|29)" in sh
    assert "28 { & $PSCommandPath test full --risky }" in ps1 and '28) "$BASH" "$self" test full --risky || true ;;' in sh
    for text in (ps1, sh):
        assert "for example: test, test full, test full --risky, test failed, logs api" in text


def test_passwords_are_long_and_plain(ops_console):
    con, _ = ops_console
    pw = con.new_password()
    assert len(pw) == 24 and pw.isalnum()


def test_set_config_keeps_a_dated_copy(ops_console):
    con, work = ops_console
    con.set_config("EAX_BREAK_GLASS_PASSWORD", "NewOne123456789", "test")
    con.set_config("EAX_NEW_KEY", "x", "test-2")
    text = (work / "eaexplorer.env").read_text(encoding="utf-8")
    assert "EAX_BREAK_GLASS_PASSWORD=NewOne123456789" in text and "EAX_NEW_KEY=x" in text and "=old" not in text
    assert len(list((work / "config-history").iterdir())) == 2


def test_stop_needs_yes(ops_console, monkeypatch):
    con, _ = ops_console
    answers = iter(["4", "no", ""])
    monkeypatch.setattr("builtins.input", lambda _p: next(answers))
    assert con.menu("0.15.1", "laptop") == -1
    answers = iter(["4", "YES"])
    monkeypatch.setattr("builtins.input", lambda _p: next(answers))
    assert con.menu("0.15.1", "laptop") == con.STOP
