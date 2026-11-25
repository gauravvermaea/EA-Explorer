"""Release 14.5 (D923): the API's coverage counts EA Explorer's own code only. The first reading (run 9, 25 Nov 2026)
counted the unit tests' copies of eaxcli in pytest's folders (/tmp/pytest-of-eax/pytest-0/...) and the test runner's
/tmp/repo/eaxcli as 8,689 lines of "our code", most of them not run: 53.2% shown where our code stood at 56.5%."""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax import coverage_probe as P  # noqa: E402


def _f(n, hit):
    return {"summary": {"num_statements": n, "covered_lines": hit}, "executed_lines": list(range(1, hit + 1)),
            "missing_lines": list(range(hit + 1, n + 1))}


def test_only_the_eax_package_is_ours():
    assert P.ours("/app/eax/api/models.py") == "eax/api/models.py"                 # the live run, in the container
    assert P.ours("eax/repository.py") == "eax/repository.py"                      # the unit tests, in the runner
    assert P.ours("/tmp/repo/services/api/eax/merge.py") == "eax/merge.py"
    assert P.ours("C:\\repo\\services\\api\\eax\\jobs.py") == "eax/jobs.py"
    for not_ours in ("/tmp/pytest-of-eax/pytest-0/test_cleanup_asks_for_yes0/eaxcli/help.py", "/tmp/repo/eaxcli/core.py",
                     "eaxcli/stack.py", "/app/eax/testing/run.py", "eax/testing/ui_flows.py", ""):
        assert P.ours(not_ours) is None, not_ours


def test_the_copies_no_longer_pull_the_figure_down():
    got = P.summarise({"/app/eax/merge.py": _f(100, 60), "eax/api/projects.py": _f(100, 80),
                       "/tmp/pytest-of-eax/pytest-0/t0/eaxcli/stack.py": _f(1000, 100),
                       "/tmp/repo/eaxcli/core.py": _f(500, 50)})
    assert (got["lines"], got["run"], got["percent"]) == (200, 140, 70.0)
    assert {f["file"] for f in got["files"]} == {"eax/merge.py", "eax/api/projects.py"}
    assert {a["area"] for a in got["areas"]} == {"core", "api"}


def test_the_live_and_unit_figures_still_join_line_by_line():
    live = P.summarise({"/app/eax/merge.py": _f(10, 4)})
    unit = P.summarise({"eax/merge.py": {"summary": {"num_statements": 10, "covered_lines": 3},
                                         "executed_lines": [5, 6, 7], "missing_lines": [1, 2, 3, 4, 8, 9, 10]},
                        "/tmp/pytest-of-eax/pytest-0/t/eaxcli/help.py": _f(50, 1)})
    got = P.combine(live, unit)
    assert (got["lines"], got["run"], got["joined"]) == (10, 7, 1)


# the goal is measured on the API's own code (owner, 25 Nov 2026, 10:56: "our goals need to be for API and UI nothing
# else"; the API is "Route layer eax/api/"): the rest of the server is shown, not judged

AREAS = [{"area": "api", "percent": 91.0, "lines": 1000, "run": 910}, {"area": "core", "percent": 50.0, "lines": 4000, "run": 2000}]


def test_the_goal_is_judged_on_eax_api_only():
    from eax.testing import run as R
    c = {"percent": 58.2, "areas": AREAS}
    c.update(R.goal_figures(c))
    assert (c["goal_area"], c["goal_percent"], c["goal_lines"], c["goal_run"]) == ("api", 91.0, 1000, 910)
    assert R.coverage_gate(c, None, 90.0)[0] == "passed"                 # all the code at 58.2% does not matter
    c2 = {"percent": 95.0, "areas": [{"area": "api", "percent": 71.2}, {"area": "core", "percent": 99.0}]}
    c2.update(R.goal_figures(c2))
    out, why = R.coverage_gate(c2, None, 90.0)
    assert out == "warning" and "18.8 points" in why


def test_only_the_api_falling_fails_the_check():
    from eax.testing import run as R
    c = {"percent": 58.2, "areas": AREAS}
    c.update(R.goal_figures(c))
    assert R.coverage_gate(c, {"areas": [{"area": "core", "percent": 70.0}]}, 90.0)[0] == "passed"
    out, why = R.coverage_gate(c, {"areas": [{"area": "api", "percent": 95.0}]}, 90.0)
    assert out == "failed" and "api 95.0% to 91.0%" in why
    assert R.goal_figures({"areas": [{"area": "core", "percent": 1.0}]}) == {}


def test_the_summary_and_the_summary_page_show_the_api_figure():
    from eax.testing import run_summary
    got = run_summary.coverage({"percent": 58.2, "goal": 90, "goal_percent": 91.0, "goal_lines": 1000, "goal_run": 910})
    assert (got["api"], got["api_lines"], got["api_run"], got["percent"]) == (91.0, 1000, 910, 58.2)
    sys.path.insert(0, str(API.parents[1]))
    from eaxcli import fullreport
    page = "".join(fullreport.cards({"selftest": {"coverage": got}}))
    assert "the API (eax/api), the goal&#x27;s measure" in page and "91.0% (910 of 1000 lines)" in page
    assert "all the server&#x27;s code" in page and "The goal is measured on the API (eax/api)" in page


def test_the_background_jobs_have_their_own_figure():
    """Owner, 25 Nov 2026, 10:57: "background jobs testing should also be done"; 10:58: triggered through the API and
    their results looked for. Their code is measured in the same run (the job runner too, D810) and shown on its own."""
    from eax.testing import run as R
    c = {"percent": 58.2, "areas": AREAS,
         "files": [{"file": "eax/background.py", "lines": 400, "run": 100}, {"file": "eax/jobs.py", "lines": 100, "run": 50},
                   {"file": "eax/merge.py", "lines": 999, "run": 0}]}
    got = R.goal_figures(c)
    assert (got["jobs_percent"], got["jobs_lines"], got["jobs_run"]) == (30.0, 500, 150)
    assert R.coverage_gate(c | got, None, 90.0)[0] == "passed"           # shown, not judged
    from eax.testing import run_summary
    s = run_summary.coverage(c | got)
    assert (s["jobs"], s["jobs_lines"], s["jobs_run"]) == (30.0, 500, 150)
    from eaxcli import fullreport
    page = "".join(fullreport.cards({"selftest": {"coverage": s}}))
    assert "the background jobs" in page and "30.0% (150 of 500 lines)" in page
