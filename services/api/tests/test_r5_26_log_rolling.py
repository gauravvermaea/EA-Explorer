"""R5.26 (owner, 15 Nov 2026, 19:03: "The logs in the entire system should be configurable form a log page. Default being
rolling with 100kb size"; "7 days, any number"; 19:31: Docker's own copy included): every log file rolls at a size set
on System Admin > Logs, 100 KB by default; Docker's own copy of each container's output too, from the next eax up."""
import gzip
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import logkeep as K  # noqa: E402


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    for k in ("EAX_LOG_FILE_KB", "EAX_LOG_FILE_MB", "EAX_DOCKER_LOG_KB"):
        monkeypatch.delenv(k, raising=False)


def test_100_kb_by_default_for_ours_and_docker_s():
    r = K.rolling(None)
    assert r["file_kb"] == 100 and r["docker_kb"] == 100 and K.max_bytes() == 100 * 1024


def test_the_logs_page_s_sizes_are_kept_in_the_logs_folder_and_win(tmp_path, monkeypatch):
    monkeypatch.setenv("EAX_LOG_FILE_MB", "50")                       # R5.6's config file setting, older
    assert K.rolling(tmp_path)["file_kb"] == 50 * 1024
    out = K.set_rolling(tmp_path, 250, "300", "sue")
    assert out["file_kb"] == 250 and out["docker_kb"] == 300 and out["set_by"] == "sue"
    assert json.loads((tmp_path / K.ROLLING).read_text())["file_kb"] == 250
    assert K.max_bytes(tmp_path) == 250 * 1024
    for bad in ((5, 100), (100, 2 * 1024 * 1024), ("big", 100)):
        with pytest.raises(ValueError):
            K.set_rolling(tmp_path, *bad, "sue")
    assert K.rolling(tmp_path)["file_kb"] == 250                     # a refused change changes nothing


def test_a_container_s_lines_roll_at_the_size(tmp_path):
    K.set_rolling(tmp_path, 10, 100, "sue")
    lines = [f"2026-11-15T10:{i // 60:02d}:{i % 60:02d}.000000000Z line {i} " + "x" * 200 for i in range(120)]
    K.ship(tmp_path, [{"id": "c1", "service": "api"}], lambda cid, since: lines, now=1794736500)
    files = sorted(p.name for p in (tmp_path / "containers" / "api").iterdir())
    assert any(f.endswith(".log.gz") for f in files) and "2026-11-15.log" in files
    assert (tmp_path / "containers" / "api" / "2026-11-15.log").stat().st_size < 10 * 1024 + 400
    first = next(p for p in (tmp_path / "containers" / "api").iterdir() if p.name == "2026-11-15.1.log.gz")
    assert gzip.open(first, "rt").read().startswith("2026-11-15T10:00:00")


def test_the_web_log_rolls_and_is_read_whole(tmp_path):
    K.set_rolling(tmp_path, 10, 100, "sue")
    web = tmp_path / "web"
    web.mkdir()
    row = {"time": "2026-11-15T10:00:00+00:00", "address": "1.2.3.4", "who": "ann", "method": "GET", "path": "/api/v1/x",
           "status": "200", "seconds": "0.01", "bytes": "10", "request_id": "r", "host": "h"}
    (web / "2026-11-15.log").write_text("".join(json.dumps(row) + "\n" for _ in range(100)))
    assert K.roll_web(tmp_path, now=1794780000) == 1
    assert (web / "2026-11-15.1.log").exists() and not (web / "2026-11-15.log").exists()   # not compressed: nginx may still write
    (web / "2026-11-15.log").write_text(json.dumps(row) + "\n")
    assert len(K.web_rows(tmp_path, "2026-11-15")) == 101


def test_docker_s_copy_its_config_and_the_page():
    compose = (REPO / "docker-compose.yml").read_text()
    assert 'max-size: "${EAX_DOCKER_LOG_KB:-100}k"' in compose and 'max-size: "10m"' not in compose
    ops = (REPO / "services/ops/logsops.py").read_text()
    assert 'hooks["set_config"]("EAX_DOCKER_LOG_KB"' in ops
    assert 'if self.path == "/logs/rolling":' in (REPO / "services/ops/ops.py").read_text()
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    assert '@blp.route("/admin/logs/rolling")' in admin and 'action="logs.rolling"' in admin
    jsx = (REPO / "services/web/src/Logs.jsx").read_text()
    assert '["rolling", "Size and keeping"]' in jsx and "/api/v1/admin/logs/rolling" in jsx
    for t in ("eaexplorer.laptop.env", "eaexplorer.server.env"):
        assert "# EAX_DOCKER_LOG_KB=100" in (REPO / "deploy/templates" / t).read_text()
