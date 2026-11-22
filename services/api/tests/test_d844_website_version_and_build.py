"""D844: the website shows its version and build like the application (owner, 22 Nov 2026, 07:57: "Ensure website has
build number on it like the application when we publish it"; asked when: "When published"). The site is made on the
laptop before the commit, so the footer carries the version and the build is filled in where it is read: on GitHub
Pages from assets/build.json, written by the publish workflow from the commit it publishes; inside EA Explorer from
the application's public heartbeat; opened from a file, the version alone. Checked in a browser all three ways."""

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _site():
    spec = importlib.util.spec_from_file_location("build_website", REPO / "tools" / "build_website.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_website"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_every_page_footer_carries_the_version():
    w = _site()
    pages = w.collect()
    page = next(p for p in pages if p.out == "index.html")
    out = w.render(page, pages, {})
    foot = out[out.index('<footer class="foot">'):out.index("</footer>")]
    assert f'<span class="site-build" data-version="{w.version()}">Version {w.version()}</span>' in foot


def test_the_build_is_filled_in_where_the_site_is_read():
    js = (REPO / "docs/site/assets/site.js").read_text(encoding="utf-8")
    assert 'document.querySelector(".site-build")' in js
    assert '"assets/build.json"' in js and 'sget("/api/v1/heartbeat")' in js
    assert 'location.pathname.indexOf("/site/") === 0' in js           # the heartbeat only inside EA Explorer
    assert "b.version === sv" in js                                    # an older copy never shows today's build


def test_the_publish_workflow_writes_the_build_of_the_commit_it_publishes():
    wf = (REPO / ".github/workflows/static.yml").read_text(encoding="utf-8")
    stamp, upload = wf.index("name: Stamp the website with its build"), wf.index("name: Upload artifact")
    assert stamp < upload
    step = wf[stamp:upload]
    assert '"${GITHUB_SHA::7}"' in step and 'services/web/public/site/$v/assets' in step and "build.json" in step
    line = next(x.strip() for x in step.splitlines() if x.strip().startswith("v=$(sed"))
    got = subprocess.run(["bash", "-c", line + '; echo "$v"'], cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert got == _site().version()
