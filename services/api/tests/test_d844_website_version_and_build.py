"""D844: the website shows its version and build like the application (owner, 22 Nov 2026, 07:57: "Ensure website has
build number on it like the application when we publish it"; asked when: "When published"). The site is made on the
laptop before the commit, so the footer carries the version and the build is filled in where it is read: inside EA
Explorer from the application's public heartbeat; on GitHub Pages from assets/build.json if the publishing writes one
(it does not: owner, 22 Nov 2026, 08:46, the workflow left as it is), else the version alone, as from a file. Checked in a browser all three ways."""

import importlib.util
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
