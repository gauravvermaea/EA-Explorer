"""Documents' OCR, off unless chosen (D903; owner, 23 Nov 2026, 22:45: "In the whole thing can OCR be turned off by
default. We should be able to turn it on in a setting in admin. It can be part of startup?"; 22:47: existing documents
read too when it is switched on; 22:48: "Make this turning on OCR part of the initial setup on start page"). The night
before, Documents read the 97 pack files' thousands of pages as pictures after a clean restart and starved the full
test."""

from __future__ import annotations

import fnmatch
import re
import socketserver
import threading
from datetime import time
from pathlib import Path

import pytest

from eax import documents_ocr as docr
from eax import first_run, mayan
from eax import settings as S

API = Path(__file__).resolve().parents[1]
WEB = API.parent / "web" / "src"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_off_by_default_a_system_setting():
    group, label, typ, default, _choices, help_ = S.REGISTRY["documents_ocr"]
    assert (group, typ, default) == ("documents", "bool", False)          # its own tab: System Admin › Documents
    assert label == "Documents: read scanned pages (OCR)"
    assert "documents already there" in help_ and "still extracted and searched" in help_


def test_changing_it_applies_it_in_the_background():
    src = _src(API / "eax" / "settings.py")
    assert 'if "documents_ocr" in clean:' in src and "documents_ocr.defer(on=bool(clean[\"documents_ocr\"]))" in src
    jobs = _src(API / "eax" / "jobs.py")
    assert '@app.task(name="eax.documents_ocr", queue="default", queueing_lock="documents_ocr", lock="documents_ocr")' in jobs
    assert "n = mayan.ocr_existing()" in jobs and "docr.started(conn, n)" in jobs      # on: the documents already there too
    assert "n = docr.clear()" in jobs and "docr.stopped(conn, n)" in jobs             # off: every job, held ones too
    assert '@app.task(name="eax.documents_ocr_tick"' in jobs and jobs.index('@app.periodic(cron="* * * * *")\n@app.task(name="eax.documents_ocr_tick"') > 0
    assert '"eax.documents_ocr": "Switch Documents\' OCR on or off"' in _src(API / "eax" / "jobqueue.py")   # its name in words


def test_start_up_applies_it_before_a_single_pack_file_goes_in():
    src = _src(API / "eax" / "industry_packs.py")
    body = src[src.index("def load_shipped_each("):]
    apply, load = body.index("mayan.apply_ocr(ocr_on)"), body.index("out = load_folder(")
    assert apply < load
    assert 'ocr_on = bool(S.values(c).get("documents_ocr", False))' in body


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple] = []
    types = [{"id": 1, "label": "Default"}, {"id": 4, "label": "EA Explorer project document"}]
    docs = {1: [{"id": 10}, {"id": 11}], 2: [{"id": 12}]}

    def fake(method, path, body=None):
        seen.append((method, path, body))
        if path.startswith("/document_types/?"):
            return {"results": types}
        if path.startswith("/documents/?"):
            page = int(re.search(r"page=(\d+)", path).group(1))
            return {"results": docs[page], "next": "more" if page == 1 else None}
        if path.endswith("/ocr/settings/") and path.startswith("/document_types/4"):
            err = mayan.MayanError("not here", 502)
            err.http = 404                       # another version of Documents: its other path
            raise err
        return {}
    monkeypatch.setattr(mayan, "_json", fake)
    return seen


def test_every_document_type_is_set_on_whichever_path_documents_has(calls):
    assert mayan.set_auto_ocr(False) == 2
    patches = [(p, b) for m, p, b in calls if m == "PATCH"]
    assert patches == [("/document_types/1/ocr/settings/", {"auto_ocr": False}),
                       ("/document_types/4/ocr/settings/", {"auto_ocr": False}),
                       ("/document_types/4/ocr_settings/", {"auto_ocr": False})]


def test_switching_on_asks_documents_to_read_every_document_already_there(calls):
    assert mayan.ocr_existing() == 3
    assert [p for m, p, _ in calls if m == "POST"] == ["/documents/10/ocr/submit/", "/documents/11/ocr/submit/",
                                                        "/documents/12/ocr/submit/"]


class _Broker(socketserver.StreamRequestHandler):
    """A stand-in for Documents' broker: the Redis protocol, two OCR queues and one other in database 0."""
    db: dict[int, dict[str, int]] = {}
    log: list[list[str]] = []

    def handle(self):
        current = 0
        while True:
            line = self.rfile.readline()
            if not line:
                return
            n = int(line[1:])
            parts = []
            for _ in range(n):
                size = int(self.rfile.readline()[1:])
                parts.append(self.rfile.read(size + 2)[:-2].decode("latin-1"))
            self.log.append(parts)
            cmd = parts[0].upper()
            store = self.db.setdefault(current, {})
            if cmd == "AUTH":
                self.wfile.write(b"+OK\r\n" if parts[1] == "pw" else b"-WRONGPASS\r\n")
            elif cmd == "SELECT":
                current = int(parts[1])
                self.wfile.write(b"+OK\r\n")
            elif cmd == "SCAN":
                keys = [k for k in store if fnmatch.fnmatchcase(k, parts[3])]
                body = b"".join(f"${len(k)}\r\n{k}\r\n".encode("latin-1") for k in keys)
                self.wfile.write(b"*2\r\n$1\r\n0\r\n" + f"*{len(keys)}\r\n".encode() + body)
            elif cmd == "LLEN":
                self.wfile.write(f":{store.get(parts[1], 0)}\r\n".encode())
            elif cmd == "EXISTS":
                self.wfile.write(f":{int(parts[1] in store)}\r\n".encode())
            elif cmd == "RENAME":
                store[parts[2]] = store.pop(parts[1])
                self.wfile.write(b"+OK\r\n")
            elif cmd == "LMOVE":
                store[parts[1]] -= 1
                store[parts[2]] = store.get(parts[2], 0) + 1
                if not store[parts[1]]:
                    del store[parts[1]]
                self.wfile.write(b"$3\r\njob\r\n")
            elif cmd == "DEL":
                gone = sum(1 for k in parts[1:] if store.pop(k, None) is not None)
                self.wfile.write(f":{gone}\r\n".encode())


@pytest.fixture
def broker(monkeypatch):
    _Broker.db = {0: {"ocr": 7400, "ocr\x06\x163": 45, "converters": 9}, 1: {"ocr-result": 1}}
    _Broker.log = []
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Broker)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("EAX_DMS_BROKER_HOST", "127.0.0.1")
    monkeypatch.setenv("EAX_DMS_BROKER_PORT", str(server.server_address[1]))
    monkeypatch.setenv("EAX_DMS_BROKER_PASSWORD", "pw")
    yield _Broker
    server.shutdown()


def test_the_ocr_queue_counted_and_cleared_and_nothing_else(broker):
    assert mayan.ocr_queue() == 7445
    assert "ocr" in broker.db[0]                                   # looking deletes nothing
    assert mayan.ocr_queue(clear=True) == 7445
    assert broker.db[0] == {"converters": 9} and broker.db[1] == {"ocr-result": 1}   # only the OCR queues went
    assert mayan.ocr_queue() == 0


def test_switching_off_sets_every_type_and_clears_the_queue(broker, calls):
    said = mayan.apply_ocr(False)
    assert said == "OCR off for 2 document type(s); 7445 OCR job(s) waiting cleared"
    assert "ocr" not in broker.db[0]
    assert not [c for c in calls if c[0] == "POST"]                # nothing asked to be read


def test_switching_on_sets_every_type_and_reads_the_existing(calls):
    assert mayan.apply_ocr(True, existing=True) == ("OCR on for 2 document type(s); 3 document(s) already there "
                                                     "asked to be read")
    assert mayan.apply_ocr(True) == "OCR on for 2 document type(s)"   # at start-up: the types only


def test_it_is_a_step_of_the_first_run_setup_on_the_start_page():
    step = next(s for s in first_run.STEPS if s[0] == "ocr")
    assert step[1] == "Documents: read scanned pages (OCR) (optional)" and step[3] == "#/admin/system"
    src = _src(API / "eax" / "first_run.py")
    assert 'seen["ocr"] = any(s.get("key") == "documents_ocr" and s.get("modified_by") for s in st.describe(conn)["documents"])' in src
    web = _src(WEB / "GuidedWizards.jsx")
    assert '(r.documents || []).find((x) => x.key === "documents_ocr")' in web
    assert 'body: JSON.stringify({ documents_ocr: v })' in web          # saved as System settings saves it
    assert '{s.key === "ocr" && <OcrChoice' in web


def test_a_browser_journey_sees_the_setting_and_the_step_without_switching_it():
    from eax.testing.ui_flows import JOURNEYS
    j = next(x for x in JOURNEYS if x["name"].startswith("documents ocr:"))
    assert [s.get("open") for s in j["steps"] if "open" in s] == ["#/admin/documents", "#/admin/wizards"]
    assert not [s for s in j["steps"] if "choose" in s or "Save" in str(s.get("click", ""))]   # never switched


# ---------------------------------------------------------------- the window, held and put back (owner, 22:54)
def test_the_window_passes_midnight_and_empty_is_any_time():
    night = docr.window({"documents_ocr_from": "22:00", "documents_ocr_to": "06:00"})
    assert docr.inside(night, time(23, 30)) and docr.inside(night, time(5, 59)) and not docr.inside(night, time(12, 0))
    day = docr.window({"documents_ocr_from": "09:00", "documents_ocr_to": "17:00"})
    assert docr.inside(day, time(9, 0)) and not docr.inside(day, time(17, 0))
    assert docr.window({}) is None and docr.window({"documents_ocr_from": "25:00", "documents_ocr_to": "06:00"}) is None
    assert docr.inside(None, time(12, 0))
    src = _src(API / "eax" / "settings.py")
    assert '"documents_ocr_from": ("documents", "OCR runs from (HH:MM)", "text", "", (0, 5),' in src
    assert 'raise EditError(f"{REGISTRY[k][1]}: a time as HH:MM (22:00), or empty for any time.")' in src


def test_outside_the_window_the_pages_are_held_and_inside_put_back(broker):
    held = docr.park("20261123T120000")
    assert held == 7445 and not [k for k in broker.db[0] if k.startswith("ocr")]
    assert docr.queue() == {"waiting": 0, "parked": 7445} and broker.db[0]["converters"] == 9
    broker.db[0]["ocr"] = 2                                       # new pages queued meanwhile, inside the window
    assert docr.unpark() == 7445
    assert broker.db[0]["ocr"] == 7402 and broker.db[0]["ocr\x06\x163"] == 45
    assert docr.queue() == {"waiting": 7447, "parked": 0}


def test_clearing_takes_the_held_pages_too(broker):
    docr.park("20261123T120000")
    broker.db[0]["ocr"] = 5
    assert docr.clear() == 7450
    assert broker.db[0] == {"converters": 9}


class _Conn:
    """A stand-in connection keeping core.settings' one row."""
    def __init__(self):
        self.row = None

    def execute(self, sql, params=None):
        if params and "v" in params:          # the write (INSERT ... :v); a read has only :k
            self.row = params["v"]
            return self
        self._out = self.row
        return self

    def scalar(self):
        return self._out


def test_the_progress_every_minute_and_what_everyone_sees(broker):
    conn = _Conn()
    on = {"documents_ocr": True}
    docr.started(conn, 97)
    st = docr.tick(conn, on, time(12, 0))
    assert st["state"] == "running" and st["peak"] == 7445
    broker.db[0]["ocr"] = 3700                                    # half the pages read
    docr.tick(conn, on, time(12, 1))
    seen = docr.status(conn, on)
    assert seen["percent"] == 50 and seen["documents"] == 97 and seen["words"] == "50% done, 3745 page(s) to go"
    night = {**on, "documents_ocr_from": "22:00", "documents_ocr_to": "06:00"}
    st = docr.tick(conn, night, time(12, 2))                      # outside the window: held
    assert st["state"] == "parked" and docr.status(conn, night)["words"] == "waiting for the window (22:00 to 06:00)"
    docr.tick(conn, night, time(23, 0))                           # inside: put back
    assert docr.queue()["parked"] == 0
    assert docr.status(conn, {"documents_ocr": False})["state"] == "off"


def test_everyone_signed_in_sees_it_and_admins_have_a_documents_tab():
    route = _src(API / "eax" / "api" / "startup.py")
    assert '@blp.route("/documents-ocr")' in route and route.count("@require_auth()") >= 2   # signed in, any role
    nav = _src(WEB / "adminNav.js")
    assert '{ key: "documents", label: "Documents", ok: () => ops() || can("settings.manage"), roles: IT },' in nav
    assert 't[0] === "documents" ? <DocumentsAdminPage />' in _src(WEB / "Admin.jsx")
    app = _src(WEB / "App.jsx")
    assert "{signedIn && <OcrStatus />}" in app
    page = _src(WEB / "DocumentsAdmin.jsx")
    assert 'apiFetch("/api/v1/documents-ocr")' in page and "useOcr(5000)" in page and "useOcr(30000)" in page
    assert 'disabled={!mine}' in page                             # only a Super Admin changes it
