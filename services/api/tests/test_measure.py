"""`eax measure` (Release 3.5, R3.5-M1): every step run in turn and checked, safe on a server, carried on with --from,
and one summary at the end."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import measure  # noqa: E402


@pytest.fixture
def m(tmp_path, monkeypatch):
    monkeypatch.setattr(measure, "ROOT", tmp_path)
    monkeypatch.setattr(measure, "WORK", tmp_path / "work")
    monkeypatch.setattr(measure, "FOOT", tmp_path / "work" / "footprint")
    monkeypatch.setattr(measure, "TESTS", tmp_path / "work" / "tests")
    monkeypatch.setattr(measure, "PROGRESS", tmp_path / "work" / "footprint" / "measure-progress.json")
    monkeypatch.setattr(measure, "argv_for", lambda line: ["eax", *line])
    monkeypatch.setattr(measure, "address", lambda: "https://localhost:8443/")
    return measure


def _deploy(monkeypatch, kind):
    monkeypatch.setattr(measure, "deployment", lambda: kind)


def _watch(folder: Path, label: str, peak: float, paged=False):
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%dT%H%M%S')}{len(list(folder.glob('*')))}-memory.json"
    (folder / name).write_text(json.dumps({
        "label": label, "total_peak_mb": peak, "total_average_mb": peak * 0.8, "target_mb": 10240.0,
        "containers": [{"container": "api", "peak_mb": peak / 2}, {"container": "testrunner", "peak_mb": peak / 4}],
        "host": {"total_mb": 16000.0, "least_available_mb": 900.0, "paged": paged}}))


class Runner:
    """Stands in for the eax commands: records them; a test run leaves a measured run folder as the real one does."""

    def __init__(self, m, fail: str = "", measured: bool = True):
        self.m, self.fail, self.measured, self.lines = m, fail, measured, []

    def __call__(self, argv, cwd=None):
        line = argv[1:]
        self.lines.append(line)
        if self.fail and line[0] == self.fail:
            return 3
        if line[0] == "test":
            run = self.m.TESTS / f"2026111{len(self.lines)}T000000Z"
            run.mkdir(parents=True)
            if self.measured:
                (run / "memory.json").write_text("{}")
                _watch(self.m.FOOT, f"self-test 1 {'smoke' if 'smoke' in line else 'detailed'} api", 6000)
        if line[:2] == ["footprint", "--watch"]:
            _watch(self.m.FOOT, line[3], {"start-up": 5000, "at-rest": 4000, "using-it": 7000}[line[3]])
        return 0


def test_a_laptop_with_a_clean_restart_runs_every_step_in_order(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    run, opened, out = Runner(m), [], []
    assert m.main(["--clean-restart"], run=run, ask=lambda q: "yes", open_browser=opened.append, out=out.append) == 0
    assert run.lines == [["clean-restart"], ["footprint", "--watch", "20", "start-up"], ["footprint", "snapshot"],
                         ["test", "smoke"], ["footprint", "--watch", "10", "at-rest"], ["footprint", "--watch", "20", "using-it"],
                         ["test", "full", "--yes"]]
    assert opened == ["https://localhost:8443/", "https://localhost:8443/"]     # in use, and during the full test
    text = "\n".join(out)
    assert "| 4.9 | 3.9 |" in text and "| Full test |" in text and "| In use |" in text and "| 6.8 | 5.5 |" in text
    assert "**Highest once started: 6.8 GB (In use)**, within the guide of 10.0 GB" in text
    assert list((m.FOOT).glob("measure-*.md")) and not m.PROGRESS.exists()


def test_without_a_restart_it_measures_it_as_it_is(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    run = Runner(m)
    m.main(["--yes"], run=run, open_browser=lambda u: None, out=lambda t: None)
    assert ["clean-restart"] not in run.lines and ["restart"] not in run.lines
    assert ["footprint", "--watch", "20", "start-up"] not in run.lines            # start-up only after a restart


def test_a_server_is_safe_by_default(m, monkeypatch):
    _deploy(monkeypatch, "server")
    out = []
    assert m.main(["--clean-restart", "--yes"], run=Runner(m), out=out.append) == 2
    assert "refused on a server installation" in out[0]                         # never deletes a server
    run, opened = Runner(m), []
    m.main(["--yes"], run=run, open_browser=opened.append, out=lambda t: None)
    assert not any(line[:2] == ["test", "full"] for line in run.lines) and opened == []   # no full test, no browser
    run = Runner(m)
    m.main(["--yes", "--full", "--restart"], run=run, out=lambda t: None)
    assert ["restart"] in run.lines and ["test", "full"] in run.lines            # restore part asked there (no --yes)


def test_it_asks_first_unless_yes(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    run, out = Runner(m), []
    assert m.main([], run=run, ask=lambda q: "no", out=out.append) == 1
    assert run.lines == [] and out[-1] == "Nothing done."


def test_a_failed_step_stops_with_the_command_to_carry_on(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    run, out = Runner(m, fail="test"), []
    assert m.main(["--clean-restart", "--yes"], run=run, open_browser=lambda u: None, out=out.append) == 3
    assert run.lines[-1] == ["test", "smoke"]
    assert "Step 4 (smoke) did not finish (exit code 3)" in out[-1] and "eax measure --clean-restart --yes --from 4" in out[-1]
    run2 = Runner(m)
    m.main(["--clean-restart", "--yes", "--from", "4"], run=run2, open_browser=lambda u: None, out=lambda t: None)
    assert run2.lines[0] == ["test", "smoke"] and ["clean-restart"] not in run2.lines   # the steps before are not run again


def test_a_test_that_was_not_measured_stops_it(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    out = []
    assert m.main(["--yes"], run=Runner(m, measured=False), open_browser=lambda u: None, out=out.append) == 1
    assert "was not measured" in out[-1] and "eax logs ops" in out[-1] and "--from 4" in out[-1]


def test_unattended_opens_nothing_and_skips_the_in_use_step(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    run, opened = Runner(m), []
    m.main(["--yes", "--unattended", "--use-minutes", "45"], run=run, open_browser=opened.append, out=lambda t: None)
    assert opened == [] and not any("using-it" in line for line in run.lines) and ["test", "full", "--yes"] in run.lines


def test_paging_is_called_out(m):
    text = m.summary([{"label": "using-it", "total_peak_mb": 12000.0, "total_average_mb": 9000.0, "target_mb": 10240.0,
                       "containers": [], "host": {"total_mb": 12288.0, "least_available_mb": 100.0, "paged": True}}], "laptop")
    assert "| In use | - | 11.7 | 8.8 | **yes** | 0.1 |" in text and "above the guide" in text
    assert "**It paged once started**: memory ran short in In use." in text


def test_bad_choices_are_refused(m, monkeypatch):
    _deploy(monkeypatch, "laptop")
    out = []
    assert m.main(["--from", "x"], out=out.append) == 2 and "--from takes a number" in out[0]
    assert m.main(["--bogus"], out=out.append) == 2 and "Not known: --bogus" in out[-1]


def test_wired_in_every_form():
    assert 'if ($Command -eq "measure") {' in (REPO / "eax.ps1").read_text()
    assert 'measure) EAX_FORM=sh exec "$BASH" ./eaxpy.sh "$@" ;;' in (REPO / "eax.sh").read_text()
    main = (REPO / "eaxcli/main.py").read_text()
    assert 'if command == "measure":' in main and "return measure.main(argv[1:])" in main
    assert "### measure [--restart|--clean-restart] [--full|--no-full] [--unattended]" in (REPO / "eaxcli/help.txt").read_text()


def test_no_full_leaves_the_full_test_out_and_still_sums_up(m, monkeypatch):
    """Owner, 14 Nov 2026: "can we just check memory after step 4, I dont want to do a full test"."""
    _deploy(monkeypatch, "laptop")
    run, out = Runner(m), []
    assert m.main(["--yes", "--no-full", "--from", "5"], run=run, open_browser=lambda u: None, out=out.append) == 0
    assert run.lines == [["footprint", "--watch", "10", "at-rest"], ["footprint", "--watch", "20", "using-it"]]
    assert any("[--no-full]" in line for line in out) and "| 3.9 | 3.1 |" in "\n".join(out)


def _m(label, peak, at, paged=False):
    return {"label": label, "total_peak_mb": peak, "total_average_mb": peak, "target_mb": 10240.0, "containers": [],
            "at": f"2026-11-14T{at}:00+00:00", "until": f"2026-11-14T{at}:30+00:00",
            "host": {"total_mb": 11878.0, "least_available_mb": 5000.0, "paged": paged}}


def test_a_measure_carried_on_lists_only_the_newest_attempt_of_each_step():
    """Bug (owner's measure of 14 Nov 2026): carried on with --from after a failed smoke step, the summary listed the smoke
    test four times, the failed attempt's paging among them, and said it paged."""
    text = measure.summary([_m("start-up", 6400, "13:15", paged=True), _m("self-test 1 smoke api", 6500, "13:28", paged=True),
                            _m("self-test 2 smoke api", 4800, "13:54"), _m("self-test 3 smoke api", 5300, "14:01"),
                            _m("at-rest", 4900, "14:36"), _m("self-test 4 smoke api", 5100, "14:28")], "laptop")
    rows = [line for line in text.splitlines() if line.startswith("| ") and "Situation" not in line]
    assert [r.split(" | ")[0] for r in rows] == ["| Starting up", "| Smoke test", "| At rest"]
    assert "| Smoke test | 14:28-14:28 | 5.0 |" in text                     # the newest smoke run, not the first
    assert "**Highest once started: 5.0 GB (Smoke test)**" in text
    assert "It paged only while starting up" in text and "It paged once started" not in text
