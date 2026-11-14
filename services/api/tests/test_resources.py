"""The resource history (Release 3.5, R3.5-M8; owner, 14 Nov 2026, 17:14: "instrument memory CPU disk cache etc every
15 min configurable from admin screen and have it available and can be deleted. We should be able to run this while
testing or working and keeping it").

Checked on PostgreSQL 16 on 14 Nov 2026 (migration 0073 applied, the operations helper answered by a stand-in): the job's
minute took a sample, said "not due" five minutes later and took the next at fifteen; six samples ten days old became two
hour rows (average and peak kept) and one 100 days old was deleted; the history over 30 days summed the peaks, CPU as a
share of the host's 8 processors, the database's cache hit rate (92.8%), size and connections; the CSV had a line per
container and one for the host; the settings were saved with a shorter interval for an hour, a detail period longer
than the history was refused; a period, everything before a date and all of it were deleted, a reversed period refused."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)


def _s(at, containers, host=None, db=None, activity=(), samples=1):
    return {"at": at, "samples": samples, "activity": list(activity), "containers": containers, "host": host or {},
            "disks": [{"label": "Docker's disk", "used_percent": 40.0, "used_gb": 40, "total_gb": 100}], "database": db or {}}


# ---------------------------------------------------------------- how often
def test_every_fifteen_minutes_unless_set_and_off_at_zero():
    from eax import resources as rs
    from eax import settings as st
    assert st.default_of("resource_every_minutes") == 15 and st.default_of("resource_keep_days") == 90
    assert st.default_of("resource_detail_days") == 7
    assert rs.interval({"resource_every_minutes": 15}, NOW) == (15, None)
    assert rs.due(None, 15, NOW) and not rs.due(NOW - timedelta(minutes=10), 15, NOW)
    assert rs.due(NOW - timedelta(minutes=14, seconds=45), 15, NOW)            # the job's minute is not exact
    assert not rs.due(None, 0, NOW)                                               # 0: off


def test_a_shorter_interval_for_a_while_goes_back_by_itself():
    from eax import resources as rs
    v = {"resource_every_minutes": 15, "resource_boost_every": 1, "resource_boost_until": (NOW + timedelta(hours=1)).isoformat()}
    assert rs.interval(v, NOW) == (1, {"every": 1, "until": "2026-11-14T16:00:00+00:00"})
    assert rs.interval(v, NOW + timedelta(hours=2)) == (15, None)                 # over: back to every 15 minutes
    assert rs.interval({**v, "resource_every_minutes": 0}, NOW)[0] == 1           # a test can be sampled while it is off


def test_the_settings_are_on_the_settings_page_but_the_shorter_interval_only_on_footprint():
    src = (REPO / "services/api/eax/settings.py").read_text()
    assert 'if group == "hidden":' in src
    from eax import settings as st
    assert st.REGISTRY["resource_every_minutes"][0] == "system" and st.REGISTRY["resource_boost_until"][0] == "hidden"


# ---------------------------------------------------------------- an hour of samples as one, and a long chart's points
def test_merging_keeps_averages_and_peaks():
    from eax import resources as rs
    m = rs.merge([
        _s("2026-11-04T10:00:00+00:00", [{"container": "api", "memory_mb": 100, "cpu_percent": 10, "net_in_mb": 1}],
           {"total_mb": 12000, "available_mb": 6000, "swap_used_mb": 0}, {"all_connections": 5, "blocks_hit": 10}, ["self-test smoke"]),
        _s("2026-11-04T10:15:00+00:00", [{"container": "api", "memory_mb": 300, "cpu_percent": 50, "net_in_mb": 3},
                                         {"container": "dms", "memory_mb": 900}],
           {"total_mb": 12000, "available_mb": 4000, "swap_used_mb": 20}, {"all_connections": 9, "blocks_hit": 30}, ["backup"]),
    ])
    api = next(c for c in m["containers"] if c["container"] == "api")
    assert api == {"container": "api", "memory_mb": 200.0, "memory_peak_mb": 300, "cpu_percent": 30.0, "cpu_peak_percent": 50, "net_in_mb": 3}
    assert m["samples"] == 2 and m["activity"] == ["backup", "self-test smoke"]
    assert m["host"]["least_available_mb"] == 4000 and m["host"]["most_swap_used_mb"] == 20 and m["host"]["available_mb"] == 5000.0
    assert m["database"]["blocks_hit"] == 30 and m["database"]["most_connections"] == 9


def test_hour_rows_weigh_by_how_many_samples_they_stand_for():
    from eax import resources as rs
    m = rs.merge([_s("a", [{"container": "x", "memory_mb": 100}], samples=3), _s("b", [{"container": "x", "memory_mb": 500}])])
    assert m["containers"][0]["memory_mb"] == 200.0 and m["samples"] == 4


def test_a_long_period_is_charted_in_at_most_400_points():
    from eax import resources as rs
    rows = [_s((NOW + timedelta(minutes=15 * i)).isoformat(), [{"container": "api", "memory_mb": float(i)}]) for i in range(1000)]
    pts = rs.points(rows)
    assert len(pts) <= 400 and sum(p["samples"] for p in pts) == 1000
    assert max(c["memory_peak_mb"] for p in pts for c in p["containers"]) == 999.0      # the peak survives


# ---------------------------------------------------------------- reading
def test_the_history_sums_the_installation_and_tells_paging_and_the_cache():
    from eax import resources as rs
    h = rs.history([
        _s("2026-11-14T10:00:00+00:00", [{"container": "api", "memory_mb": 500, "cpu_percent": 80}, {"container": "dms", "memory_mb": 2000, "cpu_percent": 40}],
           {"total_mb": 11878, "available_mb": 6000, "swap_used_mb": 0, "cpus": 8}, {"blocks_hit": 1000, "blocks_read": 1000, "cache_hit_percent": 50.0}),
        _s("2026-11-14T10:15:00+00:00", [{"container": "api", "memory_mb": 700, "cpu_percent": 160}, {"container": "dms", "memory_mb": 2600, "cpu_percent": 0}],
           {"total_mb": 11878, "available_mb": 3000, "swap_used_mb": 200, "cpus": 8}, {"blocks_hit": 1990, "blocks_read": 1010},
           ["self-test full"]),
    ])
    p0, p1 = h["points"]
    assert p0["memory_mb"] == 2500 and p1["memory_peak_mb"] == 3300 and p1["cpu_percent"] == 20.0      # 160% of one core of 8
    assert p1["paged"] and not p0["paged"]                                                             # the swap grew
    assert p1["cache_hit_percent"] == 99.0                                       # between the two samples: 990 of 1000
    s = h["summary"]
    assert s["memory_peak_mb"] == 3300 and s["least_available_mb"] == 3000 and s["paged"] and s["biggest"] == ["dms", "api"]
    assert s["activity"] == ["self-test full"] and h["containers"]["dms"][1]["memory_mb"] == 2600


def test_the_csv_has_a_line_per_container_and_one_for_the_host():
    from eax import resources as rs
    text_ = rs.csv_text([_s("2026-11-14T10:00:00+00:00", [{"container": "api", "memory_mb": 500, "cpu_percent": 8}],
                            {"available_mb": 6000, "swap_used_mb": 0}, {"cache_hit_percent": 99.1, "size_mb": 500})])
    lines = text_.strip().splitlines()
    assert lines[0].startswith("at,resolution,samples,activity,container,memory_mb")
    assert lines[1].startswith("2026-11-14T10:00:00+00:00,sample,1,,api,500,500,,8,") and ",(host),500," in lines[2]
    assert lines[2].endswith(",6000,0,99.1,500,")


def test_a_period_must_run_forwards():
    from eax import resources as rs
    from eax.metamodel_edit import EditError
    a, b = rs.period(days=7, now=NOW)
    assert b - a == timedelta(days=7)
    with pytest.raises(EditError):
        rs.period("2026-11-14T10:00:00Z", "2026-11-14T09:00:00Z")


def test_the_command_line_summary():
    from eax import resources as rs
    h = rs.history([_s("2026-11-14T10:00:00+00:00", [{"container": "api", "memory_mb": 1024, "cpu_percent": 8}],
                       {"total_mb": 11878, "available_mb": 6144, "swap_used_mb": 0, "cpus": 8})])
    out = rs.text_summary(h, 1, NOW - timedelta(days=1), NOW)
    assert "peak 1.0 GB" in out and "Paging: none" in out and "api" in out and "Docker's disk: 40 of 100 GB used" in out
    assert "No resource history" in rs.text_summary(rs.history([]), 1, NOW - timedelta(days=1), NOW)


# ---------------------------------------------------------------- the operations helper's sample
def _fp(tmp_path, monkeypatch):
    monkeypatch.setenv("EAX_WORK_MOUNT", str(tmp_path))
    spec = importlib.util.spec_from_file_location("footprint_r", REPO / "services/ops/footprint.py")
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    return fp


def test_the_sample_reads_memory_cpu_network_and_disk_with_one_stats_call(tmp_path, monkeypatch):
    from test_footprint import _ops_size
    fp = _fp(tmp_path, monkeypatch)
    stats = "\n".join(json.dumps(x) for x in [
        {"Name": "eaexplorer-api-1", "MemUsage": "512MiB / 4GiB", "CPUPerc": "12.5%", "NetIO": "1.5MB / 3MB", "BlockIO": "10MB / 2MB"},
        {"Name": "eaexplorer-dms-1", "MemUsage": "1GiB / 4GiB", "CPUPerc": "--", "NetIO": "0B / 0B", "BlockIO": "0B / 0B"},
        {"Name": "other-web-1", "MemUsage": "9GiB / 9GiB", "CPUPerc": "99%", "NetIO": "", "BlockIO": ""}])
    ps = "\n".join(json.dumps(x) for x in [{"Names": "eaexplorer-api-1", "State": "running", "Status": "Up 2 hours (healthy)"},
                                           {"Names": "eaexplorer-dms-1", "State": "running", "Status": "Up 3 minutes (health: starting)"},
                                           {"Names": "eaexplorer-reports-1", "State": "exited", "Status": "Exited (0) 1 hour ago"}])
    calls = []
    fp.hooks.update(docker=lambda *a, timeout=60: calls.append(a[0]) or (stats if a[0] == "stats" else ps), project=lambda: "eaexplorer",
                    _size=_ops_size, cpus=lambda: 8, volumes=lambda: {"eax_db": 2e9}, mounts=lambda: {"eaexplorer-api-1": ["eax_db"]},
                    filesystems=lambda: [{"label": "Docker's disk", "total_bytes": 100e9, "used_bytes": 40e9, "free_bytes": 60e9, "used_percent": 40.0},
                                         {"label": "Work folder", "same_as": "Docker's disk"}],
                    tests=lambda: {"busy": True, "level": "smoke"}, restore=lambda: {"active": False}, backing_up=lambda: False)
    s = fp.resources()
    assert calls == ["ps", "stats"]                                         # one light call each, nothing slower
    api = next(c for c in s["containers"] if c["container"] == "api")
    assert api["memory_mb"] == round(512 * 1.024 ** 2, 1) and api["cpu_percent"] == 12.5 and api["net_in_mb"] == 1.5
    assert api["disk_read_mb"] == 10.0 and api["volumes_mb"] == 2000.0 and api["memory_limit_mb"] > 4000
    assert next(c for c in s["containers"] if c["container"] == "dms")["cpu_percent"] == 0.0
    assert {"container": "reports", "state": "exited"} in s["containers"] and "web" not in {c["container"] for c in s["containers"]}
    assert s["host"]["cpus"] == 8 and s["disks"] == [{"label": "Docker's disk", "total_gb": 100.0, "used_gb": 40.0, "free_gb": 60.0, "used_percent": 40.0}]
    assert s["activity"] == ["self-test smoke", "start-up"]                 # dms still starting


def test_what_was_happening(tmp_path, monkeypatch):
    fp = _fp(tmp_path, monkeypatch)
    fp.hooks.update(tests=lambda: {}, restore=lambda: {"active": True}, backing_up=lambda: True)
    assert fp.activity([{"service": "api", "status": "Up 2 hours (healthy)"}]) == ["restore"]
    fp.hooks.update(restore=lambda: {})
    assert fp.activity([{"service": "api", "status": "Up 4 minutes (healthy)"}]) == ["backup", "start-up"]
    assert fp.uptime_seconds("Up About an hour") == 3600 and fp.uptime_seconds("Up Less than a second") == 0.5
    assert fp.uptime_seconds("Exited (0) 2 hours ago") is None


# ---------------------------------------------------------------- wired in
def test_wired_in_everywhere():
    sql = (REPO / "services/api/migrations/sql/0073_resource_history.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS operations.resource_samples" in sql and "TRIGGER" not in sql.upper().replace("NO TRIGGERS", "")
    assert 'down_revision = "0072_release_3_0_0"' in (REPO / "services/api/migrations/versions/0073_resource_history.py").read_text()
    from eax import databases
    assert "operations.resource_samples" in databases.TABLES["operations"]
    jobs = (REPO / "services/api/eax/jobs.py").read_text()
    assert '@app.task(name="eax.resource_sample", queue="default", queueing_lock="resource_sample")' in jobs
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    for route in ('"/admin/resources"', '"/admin/resources/csv"', '"/admin/resources/sample"', '"/admin/resources/settings"'):
        assert f"@blp.route({route})" in admin
    assert 'abort(403, message="Only a Super Admin deletes the resource history.")' in admin and 'action="resources.delete"' in admin
    ops = (REPO / "services/ops/ops.py").read_text()
    assert 'if self.path == "/resources":' in ops and "tests=lambda: dict(testruns.current)" in ops
    assert 'if [ "${1:-}" = "--history" ]; then shift; compose exec api python -m eax.resources history "$@"' in (REPO / "eax.sh").read_text()
    assert 'Invoke-Interactive @("api", "python", "-m", "eax.resources", "history") @($RestArgs | Select-Object -Skip 1)' in (REPO / "eax.ps1").read_text()
    assert 'stack.interactive(["api", "python", "-m", "eax.resources", "history"], rest[1:])' in (REPO / "eaxcli/main.py").read_text()
    assert "### footprint [label] | --watch [minutes] [label] | --history [days]" in (REPO / "eaxcli/help.txt").read_text()
    page = (REPO / "services/web/src/Footprint.jsx").read_text()
    assert "<ResourceHistory />" in page and "/api/v1/admin/resources/settings" in page and "data.may_delete &&" in page


# ---------------------------------------------------------------- the page's charts (resourceChart.js, run with node)
def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("no node here")
    src = REPO / "services/web/src/resourceChart.js"
    script = f"import({json.dumps(src.as_uri())}).then(m => console.log(JSON.stringify({expr})))"
    out = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_chart_lines_break_at_a_gap_and_shade_a_test():
    pts = [{"at": f"2026-11-14T10:{m:02d}:00Z", "memory_mb": v, "activity": a} for m, v, a in
           ((0, 100, []), (15, 200, ["self-test smoke"]), (30, 300, ["self-test smoke"]), (45, None, []))]
    pts.append({"at": "2026-11-14T14:00:00Z", "memory_mb": 400, "activity": []})            # hours later: a gap
    got = _node(f"m.lines({json.dumps(pts)}, [['memory_mb', 'average']], {{width: 720, height: 140}})")
    d = got["paths"][0]["d"]
    assert d.count("M") == 2 and got["top"] == 500                                        # broken at the gap
    assert len(got["bands"]) == 1 and got["bands"][0]["what"] == "self-test smoke"
    assert _node("[m.niceTop(0), m.niceTop(7), m.niceTop(130), m.niceTop(2600)]") == [1, 10, 200, 5000]


def test_the_page_choices():
    assert _node("m.PERIODS.map(p => p[0])") == ["6h", "1d", "7d", "30d", "90d"]
    assert _node("m.periodQuery('7d')") == "days=7" and _node("m.periodQuery('nonsense')") == "days=1"
    assert _node("m.deleteChoice('all', {})") == ["", "the whole resource history"]
    assert _node("m.deleteChoice('before', {}, '')") is None                               # a date first
    assert _node("m.containerTable({a: [{memory_mb: 1, memory_peak_mb: 5}], b: [{memory_mb: 9, memory_peak_mb: 9, cpu_percent: 3}]})")[0]["name"] == "b"
