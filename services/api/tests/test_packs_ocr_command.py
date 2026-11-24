"""eax packs ocr [--clear] (owner, 23 Nov 2026, 22:31: "add in eax something to stop the dms queue and ocr so that we can
[do it] from it"; D902): after a clean restart Documents reads every page of the 97 pack files as a picture for an hour
or more on a laptop, starving the full test. `packs ocr` shows the OCR jobs waiting in Documents' broker; `--clear`
deletes them, and only them. The words go to Docker as a list, never through a Windows shell: PowerShell 5.1 dropped the
inner quotes of the same command typed by hand that evening."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eaxcli import core, packs  # noqa: E402


@pytest.fixture
def docker(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(core, "compose_args", lambda args: ["docker", "compose", *args])
    said: list[str] = []
    monkeypatch.setattr(packs, "say", lambda text, *a, **k: said.append(text))

    def run(answer: str, code: int = 0):
        def fake(args):
            calls.append(args)
            return code, answer
        return fake
    return calls, said, run


def test_it_shows_the_waiting_jobs_and_changes_nothing(docker):
    calls, said, run = docker
    assert packs.ocr(False, run("queue 120\nqueue 3\ndone\n")) == 123
    args = calls[-1]
    assert args[:6] == ["docker", "compose", "exec", "-T", "-e", "EAX_CLEAR=0"]       # look only
    assert args[6:9] == ["dms-broker", "sh", "-c"] and args[9] == packs.OCR_SCRIPT       # one word each: no shell between
    assert "123 job(s) waiting" in said[-1] and "packs ocr --clear" in said[-1]


def test_clear_deletes_only_the_ocr_queue(docker):
    calls, said, run = docker
    assert packs.ocr(True, run("queue 7\ndone\n")) == 7
    assert "EAX_CLEAR=1" in calls[-1]
    script = packs.OCR_SCRIPT
    assert '--scan --pattern "ocr*"' in script                                  # the OCR queue, nothing else
    assert '[ "$EAX_CLEAR" = 1 ] && valkey-cli -n 0 DEL "$k"' in script        # deleted only when asked
    assert "FLUSH" not in script.upper() and "-n 1" not in script and "-n 2" not in script   # results and locks untouched
    assert 'REDISCLI_AUTH="$(cat /run/secrets/EAX_DMS_BROKER_PASSWORD)"' in script         # the password from its file
    assert "7 job(s) waiting deleted" in said[-1] and "documents, their text and search stay" in said[-1]


def test_nothing_waiting_and_documents_not_running(docker):
    calls, said, run = docker
    assert packs.ocr(False, run("done\n")) == 0
    assert said[-1] == "Documents' OCR: 0 job(s) waiting."
    with pytest.raises(core.Failure, match="is EA Explorer running"):
        packs.ocr(False, run("service \"dms-broker\" is not running", code=1))


def test_it_is_a_packs_sub_command_in_every_form(docker, monkeypatch):
    calls, said, run = docker
    seen = []
    monkeypatch.setattr(packs, "ocr", lambda clear, run=None: seen.append(clear) or 0)
    assert packs.main(["ocr"]) == 0 and packs.main(["ocr", "--clear"]) == 0
    assert seen == [False, True]
    # eax.ps1 and eax.sh hand every packs command to this Python program (D331): nothing to keep in step there
    assert '"packs"' in (ROOT / "eax.ps1").read_text(encoding="utf-8") and "|packs|" in (ROOT / "eax.sh").read_text(encoding="utf-8")
    help_ = (ROOT / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "|status|ocr [--clear]|collect" in help_ and "$ {eax} packs ocr --clear" in help_
    # eax test commands runs the look only, never --clear
    from eaxcli import command_tests
    assert (["packs", "ocr"], ["ocr"], 120, False) in command_tests.CASES
    assert not [c for c in command_tests.CASES if c[0][:2] == ["packs", "ocr"] and "--clear" in c[0]]
