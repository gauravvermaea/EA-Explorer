"""D940: self-test 18 sat for hours after "from the screens", with nothing more in its log: deleting the Superset test
users calls Reports from inside the browser page (page.evaluate), which Playwright waits on for ever, and the starved
browser and Reports never answered. A call now gives up after CALL_MS and answers status 0."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax.testing import reports_check as R  # noqa: E402

NODE = shutil.which("node")


def _run(fetch_js: str, wait: int) -> list:
    script = (f"globalThis.fetch = {fetch_js};\nconst call = {R.FETCH_JS};\n"
              f"call(['GET', '/api/v1/x', {{}}, {wait}]).then((r) => console.log(JSON.stringify(r)));")
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


@pytest.mark.skipif(not NODE, reason="node is not here")
def test_a_call_that_never_answers_gives_up():
    hang = "(path, opts) => new Promise((ok, no) => opts.signal.addEventListener('abort', () => no(Object.assign(new Error('x'), {name: 'AbortError'}))))"
    assert _run(hang, 200) == [0, "no answer in 0 s (AbortError)"]


@pytest.mark.skipif(not NODE, reason="node is not here")
def test_an_answer_comes_back_as_before():
    ok = "async () => ({status: 200, text: async () => '{\"result\": 1}'})"
    assert _run(ok, 5000) == [200, '{"result": 1}']


def test_every_call_passes_the_limit():
    assert R.CALL_MS == 60000
    src = (Path(R.__file__)).read_text(encoding="utf-8")
    assert "self.page.evaluate(FETCH_JS, [method, path, headers or {}, CALL_MS])" in src
    assert src.count("page.evaluate(FETCH_JS") == 1
