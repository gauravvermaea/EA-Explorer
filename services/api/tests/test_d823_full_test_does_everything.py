"""D823 (owner, 21 Nov 2026, 13:03 and 13:06: "make attack part of full test suite from command line"; "can dev check
be part pf full test along with sonar this way one full test will do everything excpt performance ttest. Its ok if we
can only do this from command line"): `eax test full` from the command line runs the dev check, the self-test (with
the attack test where it may run), the backup and restore test and the SonarQube scan, each whatever the one before
found, and ends with a list of every step. --no-dev-check, --no-attack and --no-sonar leave one out; --ci only the
self-test. The attack test's own cases are in test_r8_2_attack.py."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import main as M  # noqa: E402
from eaxcli.core import Failure  # noqa: E402


def test_a_step_that_breaks_never_stops_the_next(capsys):
    steps = [M.full_step("dev check", lambda: 1), M.full_step("self", lambda: 0),
             M.full_step("boom", lambda: (_ for _ in ()).throw(RuntimeError("Docker went away"))),
             M.full_step("sonar", lambda: (_ for _ in ()).throw(Failure("SonarQube is not ready")))]
    assert steps == [("dev check", False, "ended with 1"), ("self", True, ""), ("boom", False, "RuntimeError: Docker went away"),
                     ("sonar", False, "SonarQube is not ready")]
    assert M.full_summary(steps) == 1
    out = capsys.readouterr().out
    assert "The full test, step by step:" in out and "FAILED dev check: ended with 1" in out and "ok     self" in out
    assert M.full_summary([("a", True, ""), ("b", True, "")]) == 0


def test_the_order_and_the_options():
    src = (REPO / "eaxcli/main.py").read_text(encoding="utf-8")
    body = src.split('last = "full" in rest and "--ci" not in rest', 1)[1].split("elif command ==", 1)[0]
    order = [body.index(w) for w in ('full_step("dev check"', 'stack.interactive([*ops, "test"]',
                                     'full_step("backup and restore test"', 'full_step("SonarQube scan"', "full_summary(steps, began)")]
    assert order == sorted(order)
    assert 'if last and "--no-dev-check" not in rest:' in body and "if not no_sonar and not part:" in body
    assert 'rest = [a for a in rest if a not in ("--no-dev-check", "--no-sonar", "--no-dr")]' in body   # not passed to the helper


def test_the_help_and_the_fields_say_so():
    helptext = (REPO / "eaxcli/help.txt").read_text(encoding="utf-8")
    assert "everything but the benchmark (D823): first eax dev check" in helptext and "--no-sonar leaves it out" in helptext
    cmds = (REPO / "eaxcli/commands.py").read_text(encoding="utf-8")
    for flag in ("--no-attack", "--no-dev-check", "--no-sonar"):
        assert f'{{"key": "{flag}", "type": "flag", "required": False}}' in cmds
    assert "eax test full                the dev check, the self-test with the attack test" in (REPO / "docs/testing.md").read_text(encoding="utf-8")
