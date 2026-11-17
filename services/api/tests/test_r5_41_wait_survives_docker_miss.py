"""R5.41: a clean restart stopped with "Program 'docker.exe' failed to run: The paging file is too small" (owner,
16 Nov 2026, 06:43). One look at the containers while waiting for the API could not start docker.exe and the whole
clean-restart ended. Each look is now in try/catch: a failed look is said (once a minute) and the wait goes on."""
import re
from pathlib import Path

PS1 = (Path(__file__).resolve().parents[3] / "eax.ps1").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = PS1.index(f"function {name}")
    return PS1[start:PS1.index("\nfunction ", start + 1)]


def test_every_look_while_waiting_survives_docker_not_starting():
    for fn in ("Wait-Core", "Wait-All"):
        body = _body(fn)
        looks = [ln for ln in body.splitlines() if "& docker" in ln or "Invoke-Quiet docker" in ln]   # R5.6: Invoke-Quiet
        assert looks, fn
        for ln in looks:
            assert re.match(r"\s*try \{", ln), (fn, ln.strip())
        assert "catch {" in body and "Write-DockerMiss $_" in body, fn


def test_the_miss_says_what_helps_and_stays_ascii():
    body = _body("Write-DockerMiss")
    assert "trying again" in body and "Virtual memory" in body
    PS1.encode("ascii")
