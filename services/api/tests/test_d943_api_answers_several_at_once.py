"""D943: the API's workers answer several requests at once (owner, 26 Nov 2026: "please start fixing the ui issues").
Runs 17 to 19: with two gunicorn workers of one request each, the project page stayed on "Loading..." for 35 s and its
Library tab waited until the library service said the API does not answer; the model pages beside them opened at once."""

from __future__ import annotations

import re
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "entrypoint.sh"


def _gunicorn_lines() -> list[str]:
    text = ENTRY.read_text(encoding="utf-8").replace("\\\n", " ")
    return [ln for ln in text.splitlines() if re.match(r"\s*(exec )?gunicorn ", ln)]


def test_the_main_api_answers_eight_at_a_time_per_worker():
    main = [ln for ln in _gunicorn_lines() if "0.0.0.0:8000" in ln]
    assert len(main) == 1
    assert "--worker-class gthread" in main[0] and '--threads "${EAX_API_THREADS:-8}"' in main[0]
    assert '--workers "${EAX_API_WORKERS:-2}"' in main[0] and '--timeout "${EAX_API_TIMEOUT:-120}"' in main[0]


def test_the_operations_and_personal_services_too():
    svc = [ln for ln in _gunicorn_lines() if "${PORT}" in ln]
    assert len(svc) == 1
    assert "--worker-class gthread" in svc[0] and '--threads "${EAX_SERVICE_THREADS:-4}"' in svc[0]


def test_every_gunicorn_of_the_api_has_threads():
    lines = _gunicorn_lines()
    assert lines and all("--threads" in ln for ln in lines)


def test_no_request_state_kept_in_module_globals():
    """Threads share a worker's modules: what belongs to one request lives in flask.g, never in a module's globals."""
    root = Path(__file__).resolve().parents[1] / "eax"
    found = []
    for f in root.rglob("*.py"):
        if "testing" in f.parts:
            continue
        for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.fullmatch(r"\s+global \w+(\s*,\s*\w+)*\s*", ln):
                found.append(f"{f.relative_to(root)}:{n}: {ln.strip()}")
    assert found == ["operations.py:78: global _last_flush"], found      # a flush time, the same for every request
