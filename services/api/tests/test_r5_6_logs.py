"""R5.6 and R5.7 (owner, 14 Nov 2026: levels, info by default, rotation, the web log and its debug, a page, cleaning,
clean-run, 7 days; D688: "Our own page only"): the logs, the web log and their page."""

import gzip
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services/api"))

from eaxcli import logkeep as K  # noqa: E402

from eax import settings as st  # noqa: E402
from eax import weblog  # noqa: E402

NGINX = (REPO / "deploy/proxy/templates/default.conf.template").read_text()
TODAY = datetime.now(UTC).strftime("%Y-%m-%d")


def test_info_by_default_everywhere_and_critical_is_a_level():
    assert st.default_of("log_level") == "INFO" and "CRITICAL" in st.REGISTRY["log_level"][4]
    assert st.default_of("logs_keep_days") == 7 and K.default_keep_days("server") == K.default_keep_days("laptop") == 7
    assert K.level_of("FATAL: the database is gone") == "critical" and K.level_of("ERROR x") == "error"
    assert "KC_LOG_LEVEL: ${EAX_KC_LOG_LEVEL:-info}" in (REPO / "docker-compose.yml").read_text()


def test_a_file_rotates_at_its_size_and_closed_files_are_compressed(tmp_path):
    f = tmp_path / "containers" / "api" / f"{TODAY}.log"
    f.parent.mkdir(parents=True)
    f.write_text("x" * 2000)
    closed = K.rotate(f, limit=1000)
    assert closed.name == f"{TODAY}.1.log.gz" and not f.exists() and gzip.open(closed, "rt").read() == "x" * 2000
    old = f.parent / "2020-01-01.log"
    old.write_text("2020-01-01T00:00:00Z old\n")
    assert K.compress_closed(tmp_path) == 1 and (f.parent / "2020-01-01.log.gz").exists()
    f.write_text(f"{TODAY}T10:00:00Z now\n")
    lines = K.read(tmp_path, ["api"], TODAY)["lines"]                 # the closed part and the open one, read together
    assert len(lines) == 2 and K.files(tmp_path, "api")[0]["size"] > 0        # the closed part's line and the new one


def write_web(tmp_path, rows, day=TODAY):
    d = tmp_path / "web"
    d.mkdir(exist_ok=True)
    with open(d / f"{day}.log", "a") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def web(t, who, path, status, seconds, method="GET"):
    return {"time": f"{TODAY}T{t}:00+00:00", "address": "10.0.0.5", "who": who, "method": method, "path": path,
            "status": str(status), "seconds": str(seconds), "bytes": "120", "request_id": "r1", "host": "ea"}


def test_the_web_log_is_read_filtered_sorted_and_summed(tmp_path):
    write_web(tmp_path, [web("09:00", "ann", "/api/v1/models", 200, 0.05), web("09:05", "bob", "/api/v1/models/1234/entities", 500, 2.5),
                         web("10:00", "ann", "/mcp", 403, 0.01, "POST"), web("11:00", "svc-x (a key)", "/api/v1/models/99/entities", 200, 0.8)])
    out = K.web_read(tmp_path, TODAY)
    assert out["total"] == 4 and out["rows"][0]["who"] == "ann"
    assert K.web_read(tmp_path, TODAY, who="ann")["total"] == 2
    assert K.web_read(tmp_path, TODAY, status="errors")["total"] == 2 and K.web_read(tmp_path, TODAY, status="5xx")["total"] == 1
    assert K.web_read(tmp_path, TODAY, since="09:30", until="10:30")["total"] == 1
    assert K.web_read(tmp_path, TODAY, sort="slowest")["rows"][0]["seconds"] == 2.5
    s = out["summary"]
    assert s["calls"] == 4 and s["errors"] == 1 and s["failing"][0]["route"] == "GET /api/v1/models/<id>/entities"
    csv = K.web_csv(out["rows"])
    assert csv.splitlines()[0] == ",".join(K.WEB_FIELDS) and len(csv.splitlines()) == 5
    assert K.web_files(tmp_path)[0] == {"day": TODAY, "debug": False, "size": (tmp_path / "web" / f"{TODAY}.log").stat().st_size}
    assert K.web_zip(tmp_path, TODAY, TODAY)[:2] == b"PK"


def test_the_front_door_writes_one_line_per_call_with_its_person_and_no_query():
    assert "log_format eax_web escape=json" in NGINX and '"who":"$upstream_http_x_eax_actor"' in NGINX
    assert '"path":"$uri"' in NGINX and "$request_uri" not in NGINX.split("log_format eax_web")[1].split(";")[0]
    assert "access_log /var/log/eax-web/$eax_day.log eax_web if=$eax_web_logged;" in NGINX
    assert "proxy_hide_header X-EAX-Actor;" in NGINX
    assert 'response.headers["X-EAX-Actor"]' in (REPO / "services/api/eax/app.py").read_text()
    assert "x-eax-actor" in (REPO / "services/api/eax/mcp_server.py").read_text()
    compose = (REPO / "docker-compose.yml").read_text()
    assert "${EAX_LOGS_DIR:-./logs}/web:/var/log/eax-web" in compose and "${EAX_LOGS_DIR:-./logs}/web:/eax-web" in compose


def test_web_log_debug_is_off_by_default_and_masks_when_on(monkeypatch):
    assert st.default_of("web_log_debug_until") == ""
    monkeypatch.setattr(weblog, "until", lambda: "")
    assert not weblog.on()
    soon = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    monkeypatch.setattr(weblog, "until", lambda: soon)
    assert weblog.on()
    masked = weblog.mask({"name": "Ann", "password": "s3cret", "email": "ann@example.org", "nested": {"api_key": "k"},
                          "note": "call +27 82 555 1234 or mail bob@example.org; Bearer abcdefghijkl"})
    assert masked["password"] == "****" and masked["email"] == "****" and masked["nested"]["api_key"] == "****"
    assert "555" not in masked["note"] and "bob@" not in masked["note"] and "abcdefghijkl" not in masked["note"]
    line = json.loads(weblog.line("POST", "/api/v1/x", 201, "ann", "r1", {"a": "x" * 5000}, None))
    assert line["status"] == 201 and len(json.dumps(line["input"])) < 4200


def test_cleaning_from_the_page_and_in_clean_run(tmp_path):
    for day in ("2026-01-01", "2026-01-05", "2026-01-09"):
        (tmp_path / "containers" / "api").mkdir(parents=True, exist_ok=True)
        (tmp_path / "containers" / "api" / f"{day}.log").write_text("x\n")
        write_web(tmp_path, [web("09:00", "a", "/api", 200, 0.1)], day)
    out = K.clean_range(tmp_path, "period", "2026-01-04", "2026-01-06")
    assert out["deleted"] == ["containers/api/2026-01-05.log", "web/2026-01-05.log"]
    assert len(K.clean_range(tmp_path, "before", "2026-01-09")["deleted"]) == 2
    with pytest.raises(ValueError):
        K.clean_range(tmp_path, "period", "bad", "")
    assert K.clear(tmp_path) == ["containers", "web"] and not (tmp_path / "web").exists()
    for f, s in (("eax.sh", "--then-clear"), ("eax.ps1", "--then-clear"), ("eaxcli/main.py", "logkeep.clear(base)"),
                 ("eaxcli/logs_cli.py", '"--then-clear" in rest')):
        assert s in (REPO / f).read_text(), f


def test_the_nightly_clean_takes_the_web_log_too(tmp_path):
    write_web(tmp_path, [web("09:00", "a", "/api", 200, 0.1)], "2020-01-01")
    (tmp_path / "web" / "debug-2020-01-01.log").write_text("{}\n")
    out = K.clean(tmp_path, tmp_path / "own", tmp_path / "zips", 7, now=time.time())
    assert "web/2020-01-01.log" in out["deleted"] and "web/debug-2020-01-01.log" in out["deleted"]


def test_the_page_and_its_api():
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    for route in ('"/admin/logs/web"', '"/admin/logs/web/<any(files, csv, zip):what>"', '"/admin/logs/clean-range"', '"/admin/logs/web-debug"'):
        assert route in admin
    assert '@require_auth("settings.manage")\n    def post(self, data):\n        """Deletes the container logs' in admin
    jsx = (REPO / "services/web/src/Logs.jsx").read_text()
    assert "Web log" in jsx and "Download CSV" in jsx and "Slowest first" in jsx
    assert '["logs", "Logs"' in (REPO / "services/web/src/Admin.jsx").read_text()
