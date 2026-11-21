"""D801: /api/v1/sync/status answers the other site of a DR pairing, which signs with the pairing key, not a person's
token. A person's valid token gets 401 there, which is right; the self-test's API matrix failed it (19 Nov 2026 full
test: "401 with a valid token" for every role)."""

from __future__ import annotations

from eax.testing import api_matrix as M


def test_a_401_to_a_persons_token_on_sync_status_is_right():
    key = M.OWN_KEY.get("/api/v1/sync/status", "")
    assert M.judge_role(401, "")[0] == "failed"          # before: judged as a person's endpoint
    assert key and M.judge_role(401, key)[0] == "passed"  # after: it takes its own key


def test_a_server_error_there_still_fails():
    assert M.judge_role(500, M.OWN_KEY["/api/v1/sync/status"])[0] == "failed"


def test_every_own_key_endpoint_really_takes_its_own_key():
    from pathlib import Path
    pairing = (Path(M.__file__).resolve().parents[1] / "api" / "pairing.py").read_text(encoding="utf-8")
    assert '@blp.route("/sync/status")' in pairing and "Pairing <key>" in pairing
