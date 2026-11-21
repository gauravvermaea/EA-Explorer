"""eax dev check without ruff or pytest on the computer (owner's laptop, 19 Nov 2026, 06:41: "No module named ruff",
"No module named pytest"; D794): lint and tests run in the test runner, whose image has requirements-dev.txt, with the
repository mounted, so nothing is installed on the computer and the code checked is the code there."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _dev():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import dev_cli
    return dev_cli


def test_with_the_tools_here_lint_and_tests_run_here_as_before():
    d = _dev()
    steps = d.commands(quick=True, local=True, py="python")
    assert [s[0] for s in steps] == ["lint", "tests"]
    assert steps[0][1][:4] == ["python", "-m", "ruff", "check"] and steps[0][2] == d.API
    assert steps[1][1][:6] == ["python", "-m", "pytest", "-q", "-p", "no:randomly"] and "-x" in steps[1][1]
    # measured (D807) only when pytest-cov is here, its flags after the rest (dev check, 21 Nov 2026: -x was no longer last)
    import importlib.util
    cov = d.cover(str(ROOT / d.UNIT_COVERAGE))
    if importlib.util.find_spec("pytest_cov"):
        assert steps[1][1][-len(cov):] == cov
    else:
        assert "--cov" not in steps[1][1] and steps[1][1][-1] == "-x"


def test_without_them_lint_and_tests_run_in_the_test_runner_on_this_folder():
    d = _dev()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import core
    # core's own compose_args, its config file aside: the whole command, docker compose included
    real = lambda a: ["docker", "compose", "--env-file", core.ENV_REL, "-f", "docker-compose.yml", *a]   # noqa: E731
    steps = d.commands(quick=False, local=False, compose_args=real)
    lint, tests = steps[0][1], steps[1][1]
    for cmd in (lint, tests):
        assert cmd[:2] == ["docker", "compose"] and cmd.count("docker") == 1    # never "docker docker" (06:45)
        assert "testrunner" in cmd and "--no-deps" in cmd and "--rm" in cmd
        i = cmd.index("-v")
        assert cmd[i + 1].endswith(":/repo")                       # this folder's code, not the image's copy
        assert cmd[cmd.index("-w") + 1] == "/repo/services/api"
    assert lint[lint.index("testrunner") + 1:][:3] == ["-m", "ruff", "check"] and "--no-cache" in lint
    assert tests[tests.index("testrunner") + 1:][:2] == ["-m", "pytest"] and "no:cacheprovider" in tests
    assert "-x" not in tests


def test_core_compose_args_is_the_whole_command(monkeypatch):
    """The fault on the owner's laptop: dev check put docker before compose_args, which starts with docker itself."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import core
    monkeypatch.setattr(core, "_build_env", lambda: None)
    monkeypatch.setattr(core, "setting", lambda name, default="": default)
    monkeypatch.setattr(core, "kind", lambda: "laptop")
    got = core._compose_base(["ps"])
    assert got[:2] == ["docker", "compose"] and got[-1] == "ps"
    d = _dev()
    step = d.commands(quick=False, local=False, compose_args=core._compose_base)[1][1]
    assert step[:2] == ["docker", "compose"] and step.count("docker") == 1


def test_the_test_runner_image_has_the_tools():
    docker = (ROOT / "services/api/Dockerfile.test").read_text(encoding="utf-8")
    assert "requirements-dev.txt" in docker
    dev = (ROOT / "services/api/requirements-dev.txt").read_text(encoding="utf-8")
    assert "pytest" in dev and "ruff" in dev


def test_one_file_that_cannot_be_collected_does_not_stop_the_others():
    """The owner's laptop, 07:09: a stale import in test_viewpoints.py interrupted the whole run, so no test ran."""
    d = _dev()
    for local in (True, False):
        tests = d.commands(quick=False, local=local, py="python", compose_args=lambda a: ["docker", "compose", *a])[1][1]
        assert "--continue-on-collection-errors" in tests and "-rfE" in tests


def test_the_check_is_saved_for_before_and_after(tmp_path, capsys):
    d = _dev()
    d.LOG.clear()
    d.say("== lint")
    d.say("FAILED tests: exit 1")
    out = d.save_log(root=tmp_path, now=0)
    assert out.parent == tmp_path / "work" / "tests" and out.name.startswith("dev-check-") and out.suffix == ".log"
    assert out.read_text(encoding="utf-8").splitlines() == ["== lint", "FAILED tests: exit 1"]
    assert "== lint" in capsys.readouterr().out
