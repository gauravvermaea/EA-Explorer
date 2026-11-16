"""R5.39: Operations and Personal data kept showing "starting, running, not answering yet" (owner, 15 Nov 2026, 23:28:
"why do these two keep shutting down and starting"). Served by the API itself, they were checked by the API calling
itself over HTTP with 3 seconds to answer; with its two workers busy the call waited too long. Nothing had stopped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import health  # noqa: E402


class Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        return None


class Engine:
    def connect(self):
        return Conn()


def _no_http(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the API must not call itself to check a part it serves")
    monkeypatch.setattr(health, "_http", refuse)


def test_parts_in_the_api_are_checked_without_calling_itself(monkeypatch):
    from eax import databases
    for k in ("EAX_OPERATIONS_INTERNAL_URL", "EAX_PERSONAL_INTERNAL_URL"):
        monkeypatch.delenv(k, raising=False)
    _no_http(monkeypatch)
    monkeypatch.setattr(databases, "engine_for", lambda part: Engine())
    assert health.check_operations()["status"] == "up"
    assert health.check_personal()["status"] == "up"


def test_a_schema_not_reachable_is_down(monkeypatch):
    from eax import databases
    monkeypatch.delenv("EAX_OPERATIONS_INTERNAL_URL", raising=False)
    _no_http(monkeypatch)

    def broken(part):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(databases, "engine_for", broken)
    r = health.check_operations()
    assert r["status"] == "down" and "connection refused" in r["detail"]


def test_a_part_in_its_own_container_is_still_asked_over_http(monkeypatch):
    monkeypatch.setenv("EAX_OPERATIONS_INTERNAL_URL", "http://operations:8000")
    asked = []
    monkeypatch.setattr(health, "_http", lambda *a, **k: asked.append(a) or {"status": "up"})
    health.check_operations()
    assert asked and asked[0][2] == "operations"
