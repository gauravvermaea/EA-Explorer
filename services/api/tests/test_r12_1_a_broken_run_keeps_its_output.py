"""R12.1 (Release 12, stabilisation; owner, 21 Nov 2026, 10:44: "Fix what you can here"): the full test of 21 Nov 2026
stopped in the reports suite and left no report, no runner-output.log and its signed-in ZAP scan's token
(zap-auth.txt) in the run's folder; the reason was only in the console. Now the helper writes the runner's output to
the run's folder line by line as it comes (runner-output.log.part, replaced by the whole runner-output.log at the end),
keeps its own lines in helper.log, and deletes every token file left for its scans however the run ends."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _ops():
    spec = importlib.util.spec_from_file_location("ops_testruns_r121", REPO / "services/ops/testruns.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Logs:
    def __init__(self, lines):
        self.stdout = io.StringIO("".join(f"{x}\n" for x in lines))

    def wait(self):
        return 0


def test_the_output_is_on_disk_before_the_wait_breaks(tmp_path, monkeypatch):
    T = _ops()
    monkeypatch.setattr(T.subprocess, "Popen", lambda *a, **k: _Logs(["RUN_ID=7", "reports: every dashboard"]))

    def docker(*args, **kw):
        raise RuntimeError("Cannot connect to the Docker daemon")       # the helper loses the runner
    T.H["docker"] = docker
    part = tmp_path / "runner-output.log.part"
    shown = []
    try:
        T._wait("cid", shown.append, to_file=str(part))
    except RuntimeError:
        pass
    assert part.read_text() == "RUN_ID=7\nreports: every dashboard\n"   # kept, though the wait broke
    assert shown == ["RUN_ID=7", "reports: every dashboard"]


def test_with_no_console_the_output_is_still_streamed_to_the_file(tmp_path, monkeypatch):
    T = _ops()
    monkeypatch.setattr(T.subprocess, "Popen", lambda *a, **k: _Logs(["one", "two"]))
    T.H["docker"] = lambda *a, **k: "0"
    code, out = T._wait("cid", None, to_file=str(tmp_path / "o.part"))
    assert code == 0 and out == "one\ntwo\n" and (tmp_path / "o.part").read_text() == out


def test_before_the_change_a_run_without_a_console_kept_nothing_until_the_end(monkeypatch):
    T = _ops()
    calls = []
    T.H["docker"] = lambda *a, **k: calls.append(a) or ("0" if a[0] == "wait" else "all of it")
    code, out = T._wait("cid", None)                                   # no file asked for: as before
    assert out == "all of it" and [c[0] for c in calls] == ["wait", "logs"]


def test_every_token_file_is_deleted_however_the_run_ends(tmp_path):
    T = _ops()
    for name in ("zap-auth.txt", "attack-auth.txt", "bench-tokens.txt", "zap-openapi.json"):
        (tmp_path / name).write_text("x")
    T.forget_tokens(str(tmp_path))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["zap-openapi.json"]
    T.forget_tokens(str(tmp_path))                                     # nothing left: no error


def test_the_helper_s_own_lines_are_kept_with_their_time(tmp_path):
    T = _ops()
    shown = []
    say = T.helper_log(str(tmp_path), shown.append)
    say("ZAP: the signed-in scan")
    say("Trivy scan of eaexplorer/api:7.9.0")
    lines = (tmp_path / "helper.log").read_text().splitlines()
    assert [x[9:] for x in lines] == ["ZAP: the signed-in scan", "Trivy scan of eaexplorer/api:7.9.0"]
    assert all(x[2] == ":" and x[5] == ":" for x in lines) and shown == ["ZAP: the signed-in scan", "Trivy scan of eaexplorer/api:7.9.0"]


def test_the_run_uses_them():
    src = (REPO / "services/ops/testruns.py").read_text()
    body = src.split("def run_sequence", 1)[1].split("\ndef ", 1)[0]
    assert 'say = helper_log(f"{WORK}/tests/{folder}", say)' in body
    assert 'to_file=f"{WORK}/tests/{folder}/runner-output.log.part"' in body
    assert 'forget_tokens(f"{WORK}/tests/{folder}")' in body.split("finally:", 1)[1]
