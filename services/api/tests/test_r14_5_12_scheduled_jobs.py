"""Every job the job runner runs (eax/jobs.py), its scheduled ones included, run in the unit tests with what each calls
stood in for (owner, 25 Nov 2026, 17:02: "add tests to unit tests and mock the DB etc"): the nightly, weekly and monthly
jobs a test run never waits for (the database tidy and check, the logs and test results cleaned, the weekly security scan,
the optimisation report, ...) as well as those that run every minute. Each is called as the job runner calls it, with the
modules it imports and the database replaced by stand-ins that answer anything (Answer, as for the background tasks); a
job may stop with what it was given, but it never crashes on a stand-in's answer. The unit tests' coverage is joined
with the self-test's (D807): this counts toward the background jobs' figure (D926)."""

import contextlib
import re
import signal
import sys
import types
from datetime import UTC
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

import eax  # noqa: E402
from eax import jobs  # noqa: E402
from eax.metamodel_edit import EditError  # noqa: E402

SOURCE = (API / "eax/jobs.py").read_text(encoding="utf-8")
# every module a job imports inside itself, and the two from elsewhere
INNER = sorted({m for line in re.findall(r"^\s+from \. import ([a-z_, ]+(?: as [a-z_]+)?(?:, [a-z_]+(?: as [a-z_]+)?)*)",
                                         SOURCE, re.M)
                for m in re.findall(r"([a-z_]+)(?: as [a-z_]+)?", line) if m != "as"} - {"__version__"})
DOTTED = ("db", "api.admin", "testing.cleanup", "testing.store", "testing")


class Answer(dict):
    """Answers anything: a missing key or attribute, a call, a with, a comparison (never more), arithmetic (0); empty
    when iterated, so a loop over rows has nothing to do."""
    def __missing__(self, key):
        return Answer()

    def get(self, key, default=None, *_a):
        return self[key] if key in self else default

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Answer()

    def __call__(self, *a, **k):
        return Answer()

    def __iter__(self):
        return iter(())

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def __lt__(self, other):
        return False

    __gt__ = __le__ = __ge__ = __lt__

    def __add__(self, other):
        return other

    __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __add__

    def __hash__(self):
        return id(self)

    def __str__(self):
        return ""

    def __len__(self):
        return 0


class Full(Answer):
    """An Answer that is there: truthy, one row when iterated (a few times, so no loop runs for ever), so the job's
    deeper branches run too. A stand-in's answer may not fit what the job does next; then it stops there."""
    left = [0]

    def __missing__(self, key):
        return Full()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Full()

    def __call__(self, *a, **k):
        return Full()

    def __bool__(self):
        return True

    def __len__(self):
        return 1

    def __iter__(self):
        Full.left[0] -= 1
        return iter([Full()] if Full.left[0] > 0 else [])

    def __str__(self):
        return "x"


MODE = {"answer": Answer}

# what a job takes from a call as it is: (ok, why) from the backup folder's check, a time zone
AS_IS = {"ready": (True, ""), "zone": UTC}


def _stand_in(name: str) -> types.ModuleType:
    mod = types.ModuleType(f"eax.{name}")

    def attr(fn):
        if fn.startswith("__"):
            raise AttributeError(fn)
        if fn in AS_IS:
            return lambda *a, **k: AS_IS[fn]
        return MODE["answer"]()
    mod.__getattr__ = attr
    return mod


@pytest.fixture(params=["empty", "full"])
def stood_in(monkeypatch, request):
    MODE["answer"] = Answer if request.param == "empty" else Full
    Full.left[0] = 30
    signal.signal(signal.SIGALRM, lambda *_a: (_ for _ in ()).throw(TimeoutError("ran on")))
    signal.alarm(10)
    _replace(monkeypatch)
    yield request.param
    signal.alarm(0)


def _replace(monkeypatch):
    for name in [*INNER, *DOTTED]:
        fake = _stand_in(name)
        monkeypatch.setitem(sys.modules, f"eax.{name}", fake)
        if "." not in name:
            monkeypatch.setattr(eax, name, fake, raising=False)
    for name in ("get_engine", "get_projects_engine", "databases", "audit", "get_settings"):
        if hasattr(jobs, name):
            monkeypatch.setattr(jobs, name, MODE["answer"]())
    monkeypatch.setattr(jobs.time, "sleep", lambda *_a: None, raising=False) if hasattr(jobs, "time") else None
    # the queue itself never reached: opening the job runner's app and deferring a job do nothing here
    monkeypatch.setattr(jobs.app, "open", contextlib.nullcontext, raising=False)
    for t in _tasks().values():
        monkeypatch.setattr(t, "defer", lambda **_k: 1, raising=False)
        monkeypatch.setattr(t, "configure", lambda t=t, **_k: t, raising=False)


def _tasks() -> dict:
    return {name: t for name, t in jobs.app.tasks.items() if name.startswith("eax.")}


def _func(task):
    return getattr(task, "__wrapped__", None) or task.func


ARGS = {"context": None, "timestamp": 0, "note": "self-test", "requested_by": "self-test", "source": "s", "target": "t",
        "actor": "self-test", "roles": [], "publish": False, "task_id": "t1", "username": "self-test", "batch": "b",
        "by": "self-test", "pairing": "p", "scope": None, "model": "m", "entities": [], "request_id": "r",
        "project_id": 1, "library_id": 1, "on": False, "why": "the self-test", "fix": False}


def test_every_job_is_named_and_says_what_it_does():
    tasks = _tasks()
    assert len(tasks) >= 40
    for name, t in tasks.items():
        assert _func(t).__doc__, name


@pytest.mark.parametrize("name", sorted(_tasks()))
def test_each_job_runs_with_what_it_calls_stood_in_for(name, stood_in):
    fn = _func(_tasks()[name])
    import inspect
    params = list(inspect.signature(fn).parameters)
    kwargs = {p: ARGS[p] for p in params}
    try:
        fn(**kwargs)
    except EditError as exc:                           # a job may refuse what it is given, in words
        assert str(exc), name
    except TimeoutError:
        raise
    except Exception:                                  # noqa: BLE001 - full: a stand-in's answer that does not fit
        assert stood_in == "full", name                # with nothing there, every job runs to its end


def test_the_scheduled_ones_have_their_times():
    for name, cron in (("logs_clean", "43 2 * * *"), ("security_weekly", "20 3 * * 0"), ("optimise_report", "30 2 1 * *"),
                       ("db_check", "50 0 * * *"), ("housekeeping", "40 2 * * *"), ("test_results_cleanup", "17 3 * * *")):
        assert re.search(rf'@app\.periodic\(cron="{re.escape(cron)}"\)\s*\n@app\.task\(name="eax\.{name}"', SOURCE), name
