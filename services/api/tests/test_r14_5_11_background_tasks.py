"""Every background task (eax/background.py) run in the unit tests, with what each calls stood in for (owner, 25 Nov 2026,
17:02: "On background.py why dont you add tests to unit tests and mock the DB etc, it will just give you answers by
calling?"): the job runner's part of each slow button, its words and its result, without a database or the job runner.
Each task is called twice: with no parameters, and with every parameter it reads set (the other branch). The modules a
task imports are replaced by stand-ins that answer anything (Answer); a function whose result the task unpacks into a
tuple (data, name, ctype = ...) answers a tuple of that length, found in the task's own code. The unit tests' coverage is
joined with the self-test's (D807), so this counts toward the background jobs' figure (D926)."""

import ast
import sys
import types
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

import eax  # noqa: E402
from eax import background as bg  # noqa: E402
from eax.metamodel_edit import EditError  # noqa: E402

SOURCE = (API / "eax/background.py").read_text(encoding="utf-8")
# the modules the tasks import (from . import X / from .X import Y); EditError's module stays real (it is raised and caught)
STOOD_IN = ("model_ops", "projects", "commons", "merge", "gaps", "project_work", "model_wizards", "merge_back", "archive",
            "db", "tags", "repo_tags", "pushdown", "project_backup", "compare", "jobs", "tasks", "repository", "quality",
            "permissions", "change_log")


class Answer(dict):
    """Answers anything a task asks of it: a missing key or attribute is another Answer, a call gives an Answer, it is
    a context manager and falsy when empty (so "x or {}" and "if x:" take their plain branch)."""
    def __missing__(self, key):
        return Answer(NAMED)

    def get(self, key, default=None, *_a):
        if key in self:
            return self[key]
        return default if default is not None else Answer(NAMED)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Answer()

    def __call__(self, *a, **k):
        return Answer(NAMED)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __str__(self):
        return "x"

    def __int__(self):
        return 0

    def __hash__(self):
        return id(self)


NAMED = {"name": "x", "id": "x", "note": "done"}      # what a result is named, known by and says, as the tasks read them
# what a task takes from a call as it is, not as a dict: words, or the (words, result) a task returns unchanged
AS_IS = {"write_pending_goals": "the goals written", "backup": ("Backed up.", {"file": "x"})}


class Value(str):
    """A parameter's value: text that also answers .get (a parameter that is itself a dict)."""
    def get(self, key, default=None, *_a):
        return Value("1")


class Everything(dict):
    """A task's parameters with every one set: any key reads as a value, so the branch for a given option runs."""
    def __missing__(self, key):
        return Value("1")

    def get(self, key, default=None, *_a):
        return self[key] if key in self else Value("1")


def _unpacked() -> dict[str, int]:
    """Each function a task unpacks (a, b, c = mod.f(...)) with how many values it gives."""
    out: dict[str, int] = {}
    for n in ast.walk(ast.parse(SOURCE)):
        if isinstance(n, (ast.Assign, ast.With)) and isinstance(getattr(n, "value", None), ast.Call):
            t = n.targets[0]
            f = n.value.func
            if isinstance(t, ast.Tuple) and isinstance(f, ast.Attribute):
                out[f.attr] = len(t.elts)
    return out


UNPACKED = _unpacked()


def _stand_in(name: str) -> types.ModuleType:
    mod = types.ModuleType(f"eax.{name}")

    def attr(fn):
        if fn.startswith("__"):
            raise AttributeError(fn)
        n = UNPACKED.get(fn)
        if fn in AS_IS:
            return lambda *a, **k: AS_IS[fn]
        if fn == "input_of":
            return lambda *a, **k: (b"data", "file.zip")
        if n:
            return lambda *a, **k: tuple(b"data" if i == 0 else "name" for i in range(n))
        return Answer(NAMED)
    mod.__getattr__ = attr
    return mod


@pytest.fixture()
def stood_in(monkeypatch):
    calls = []
    for name in STOOD_IN:
        fake = _stand_in(name)
        monkeypatch.setitem(sys.modules, f"eax.{name}", fake)
        monkeypatch.setattr(eax, name, fake, raising=False)
    fake_tk = _stand_in("tasks")
    fake_tk.add_file = lambda conn, tid, data, name, ctype: calls.append(("file", name, ctype))
    fake_tk.progress = lambda *a, **k: calls.append(("progress",) + a)
    monkeypatch.setattr(bg, "tk", fake_tk)
    return calls


def _task(params) -> dict:
    return {"id": "t1", "kind": "x", "params": params, "model_guid": "11111111-1111-1111-1111-111111111111"}


USER = types.SimpleNamespace(username="self-test", roles=("super-admin",), can=lambda *_a: True)

def _registry() -> dict:
    found = [v for v in vars(bg).values() if isinstance(v, dict) and "merge.analyse" in v and callable(v["merge.analyse"])]
    assert found, "background.py keeps its kinds in a dict of kind to function"
    return found[0]


REGISTRY = _registry()


def test_every_kind_has_words_and_a_function():
    words = next(v for k, v in vars(bg).items() if k == "KINDS")
    assert set(REGISTRY) <= set(words), set(REGISTRY) - set(words)
    for kind, fn in REGISTRY.items():
        assert fn.__doc__ and fn.__doc__.strip(), kind                   # each says what it does


@pytest.mark.parametrize("kind", sorted(REGISTRY))
@pytest.mark.parametrize("params", ["none", "every"])
def test_each_task_runs_to_its_words_and_result(kind, params, stood_in):
    if kind == "quality.recheck_type":              # it reads rows: its own test below
        return
    fn = REGISTRY[kind]
    conn = Answer()
    try:
        said, result = fn(conn, _task({} if params == "none" else Everything()), USER)
    except EditError as exc:                       # a task may refuse what it is given, in words (never a crash)
        assert str(exc), kind
        return
    except (KeyError, TypeError) as exc:           # a required parameter missing: only with none given
        assert params == "none", f"{kind}: {exc!r}"
        return
    assert isinstance(said, (str, Answer)) and str(said).strip(), kind     # its words (or those of what it called)
    assert isinstance(result, dict), kind
    for x in ("_action", "_details"):
        if x in result:
            assert result[x] == "-" or result[x], kind


def test_a_task_that_makes_a_file_keeps_it_with_the_task(stood_in):
    said, result = REGISTRY["merge.sample"](Answer(), _task({"format": "xlsx"}), USER)
    assert ("file", "name", "name") in stood_in
    assert result["file"] == "name" and result["_action"] == "-" and "is ready" in said


def test_a_damaged_package_is_refused_in_words(stood_in, monkeypatch):
    def broken(*_a, **_k):
        raise ValueError("not a zip")
    monkeypatch.setattr(sys.modules["eax.model_ops"], "read_package", broken, raising=False)
    with pytest.raises(EditError) as got:
        REGISTRY["package.analyse"](Answer(), _task({}), USER)
    assert "could not be read as a package" in str(got.value)


def test_the_helpers():
    assert bg._safe("a/b:c?") == "a-b-c-" and bg._safe("") == "download" and len(bg._safe("x" * 300)) == 120
    assert bg._plain(None) is None and bg._plain({"a": 1, "_id": 2}) == {"a": 1}


def test_every_entity_of_a_type_rechecked_in_batches(stood_in, monkeypatch):
    q = sys.modules["eax.quality"]
    rows = iter([[{"id": 7, "name": "Application Component"}], [{"g": f"e{i}"} for i in range(450)]])
    batches = []
    monkeypatch.setattr(q, "_rows", lambda *a, **k: next(rows), raising=False)
    monkeypatch.setattr(q, "refresh_entities", lambda conn, m, guids: batches.append(len(guids)) or len(guids), raising=False)
    said, result = REGISTRY["quality.recheck_type"](Answer(), _task({"entity_type": "ApplicationComponent"}), USER)
    assert batches == [200, 200, 50] and result == {"rechecked": 450, "_action": "-"}
    assert said == "450 Application Component entities rechecked."
    monkeypatch.setattr(q, "_rows", lambda *a, **k: [], raising=False)
    with pytest.raises(EditError) as got:
        REGISTRY["quality.recheck_type"](Answer(), _task({"entity_type": "Nothing"}), USER)
    assert got.value.status == 404 and "No entity type Nothing" in str(got.value)
