"""The heartbeat's answer carries everything the screens read from it (found 17 Nov 2026 while taking the video's
screenshots: the view put the build and the self-test in its answer, but the answer's schema did not name them, so
they were dropped: the top left always said "build dev" and the self-test banner, R2.51, never showed). With Release
6.5 it also carries the site's purpose and whether this site is a DR copy."""

from __future__ import annotations


def test_the_heartbeat_keeps_the_build_the_self_test_the_purpose_and_the_dr_copy(client, monkeypatch):
    from eax.api import heartbeat as hb
    monkeypatch.setenv("EAX_BUILD", "abc1234")
    monkeypatch.setattr(hb, "check_database", lambda: ({"reachable": True, "latency_ms": 1.0, "version": "x",
                                                        "schema_version": "x", "error": None}, {"waiting": 0, "failed": 0}))
    monkeypatch.setattr(hb, "version_warning", lambda v: None)
    monkeypatch.setattr(hb, "_test_in_progress", lambda: {"id": 7, "by": "eaadmin"})
    monkeypatch.setattr(hb, "_purpose", lambda: "UAT")
    monkeypatch.setattr(hb, "_dr", lambda: {"from": "Site 1"})
    body = client.get("/api/v1/heartbeat").get_json()
    assert body["build"] == "abc1234"
    assert body["test_in_progress"] == {"id": 7, "by": "eaadmin"}
    assert body["site_purpose"] == "UAT" and body["dr_copy"] == {"from": "Site 1"}
