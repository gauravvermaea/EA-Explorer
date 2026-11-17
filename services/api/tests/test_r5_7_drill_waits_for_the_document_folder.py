"""The owner's restore drill, 17 Nov 2026, 18:53: "not made: a document with its file: The project's repository is not
built yet in Documents". The test project's repository copies its templates first (more than a hundred documents) and
the new document class's folder is made after them; after the smoke test Documents was busy and the five minutes the
upload waited were not enough. The upload now follows the build itself (the class's folder in the database) for up to
half an hour, saying how it stands, before it uploads."""
from __future__ import annotations

import inspect

from eax.testing import backup_restore as br


class _Api:
    def __init__(self):
        self.calls = 0

    def upload(self, path, name, content):
        self.calls += 1
        return 201, {"id": 7}


def test_the_upload_waits_for_the_folder_however_long_the_build_takes(monkeypatch):
    states = iter([(False, "the project's documents: building (try 1)")] * 60 + [(True, "ready")])
    clock = {"t": 0.0}
    monkeypatch.setattr(br, "folder_ready", lambda item: next(states))
    monkeypatch.setattr(br.time, "time", lambda: clock["t"])
    monkeypatch.setattr(br.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(br, "say", lambda msg: None)
    a = _Api()
    s, d = br._upload_waiting(a, "/x", "f.txt", b"x", item=5)
    assert (s, a.calls) == (201, 1)          # ten minutes of building, more than the old five, then one upload
    assert clock["t"] >= 600


def test_a_build_that_never_finishes_is_named_in_the_failure(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(br, "folder_ready", lambda item: (False, "the project's documents: failed (try 5): Documents is down"))
    monkeypatch.setattr(br.time, "time", lambda: clock["t"])
    monkeypatch.setattr(br.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    monkeypatch.setattr(br, "say", lambda msg: None)
    a = _Api()
    s, d = br._upload_waiting(a, "/x", "f.txt", b"x", item=5)
    assert s == 409 and a.calls == 0 and "Documents is down" in d["detail"]


def test_both_uploads_of_the_test_wait_for_the_folder():
    src = inspect.getsource(br)
    assert src.count("_upload_waiting(") == 3                   # the helper and its two uses
    assert src.count("item=item)") + src.count('item=ids.get("item"))') == 2
    assert br.FOLDER_WAIT >= 1800


def test_the_folder_is_looked_up_by_the_guid_the_api_gives(monkeypatch):
    """The owner's drill, 19:45: the class's id from the API is its guid; int() of it failed."""
    seen = {}

    class _Conn:
        def execute(self, sql, params):
            seen.update(sql=str(sql), params=params)

            class _R:
                def mappings(self):
                    return self

                def first(self):
                    return {"mayan_cabinet_id": 12, "repo_state": "ready", "repo_note": "", "repo_tries": 1}
            return _R()

    class _Begin:
        def __enter__(self):
            return _Conn()

        def __exit__(self, *a):
            return False

    class _Eng:
        def begin(self):
            return _Begin()

    import eax.db as db
    monkeypatch.setattr(db, "get_projects_engine", lambda: _Eng())
    assert br.folder_ready("ff46f97a-25da-4b88-8e14-84d808fee0a8") == (True, "ready")
    assert seen["params"] == {"i": "ff46f97a-25da-4b88-8e14-84d808fee0a8"} and "guid::text" in seen["sql"]
