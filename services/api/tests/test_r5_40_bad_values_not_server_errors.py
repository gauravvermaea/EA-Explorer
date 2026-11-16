"""R5.40: the security scan of the full test (16 Nov 2026) got server errors (500) for values a caller got wrong:
the change log with model=model (DataError: not an identifier), a model's framework preview with a map that is not
JSON (JSONDecodeError), and a package with a content it does not know (EditError). Each is now a 400."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

M = "/api/v1/models/00000000-0000-4000-8000-00000000dead"


def _app(monkeypatch):
    from eax import auth
    from eax.app import create_app
    user = auth.User(username="t", roles=["super-admin"])
    monkeypatch.setattr(auth, "current_user", lambda: user)
    return create_app(testing=True)


def test_a_value_the_database_cannot_take_is_a_400(monkeypatch):
    from sqlalchemy.exc import DataError

    from eax.api import change_log as api_cl

    def bad(fn, write=False):
        raise DataError("SELECT", {}, Exception('invalid input syntax for type uuid: "model"'))
    monkeypatch.setattr(api_cl, "_run", bad)
    r = _app(monkeypatch).test_client().get("/api/v1/change-log?model=model")
    assert r.status_code == 400, r.get_data(as_text=True)[:200]
    assert "not valid" in r.get_json()["message"]


def test_a_map_that_is_not_json_is_a_400(monkeypatch):
    from eax.api import models as api_m
    monkeypatch.setattr(api_m, "get_engine", lambda: (_ for _ in ()).throw(AssertionError("reached the database")))
    c = _app(monkeypatch).test_client()
    for m in ("map", "[1,2]"):
        r = c.get(f"{M}/framework-preview?target=t&map={m}")
        assert r.status_code == 400, (m, r.status_code, r.get_data(as_text=True)[:200])


def test_an_edit_error_raised_anywhere_answers_with_its_status(monkeypatch):
    from eax.api import models as api_m
    from eax.metamodel_edit import EditError

    def refuse(*a, **k):
        raise EditError("Content is metamodel, content or history.")

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Engine:
        def connect(self):
            return Conn()
    monkeypatch.setattr(api_m, "get_engine", lambda: Engine())
    monkeypatch.setattr(api_m.mo, "export_package", refuse)
    r = _app(monkeypatch).test_client().get(f"{M}/package?format=zip&content=content")
    assert r.status_code == 400 and "Content is" in r.get_json()["message"], r.get_data(as_text=True)[:200]
